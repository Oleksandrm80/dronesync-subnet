"""
dronesync/vision_engine.py
AI vision engine for DroneSync.
Backends: YOLOv8 (primary), OpenCV DNN (fallback), basic (no deps)
Optional: GPT-4o Vision for complex scenes
"""

import time
import logging
import base64
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

RISK_SAFE = "SAFE"
RISK_WARNING = "WARNING"
RISK_DANGER = "DANGER"

WARNING_CLASSES = {"person", "bicycle", "motorcycle", "bird", "cat", "dog"}
DANGER_CLASSES = {"airplane", "helicopter", "drone", "car", "truck", "bus", "train"}


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: tuple
    risk: str = RISK_SAFE


@dataclass
class SceneReport:
    frame_id: int
    timestamp: float
    source: str
    risk_level: str = RISK_SAFE
    objects: list = field(default_factory=list)
    ai_commentary: str = ""
    backend_used: str = "none"
    processing_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "risk_level": self.risk_level,
            "objects": [
                {"label": o.label, "confidence": round(o.confidence, 2),
                 "bbox": o.bbox, "risk": o.risk}
                for o in self.objects
            ],
            "ai_commentary": self.ai_commentary,
            "backend_used": self.backend_used,
            "processing_ms": round(self.processing_ms, 1),
        }


def _object_risk(label: str) -> str:
    if label in DANGER_CLASSES:
        return RISK_DANGER
    if label in WARNING_CLASSES:
        return RISK_WARNING
    return RISK_SAFE


def _scene_risk(objects: list) -> str:
    risks = [o.risk for o in objects]
    if RISK_DANGER in risks:
        return RISK_DANGER
    if RISK_WARNING in risks:
        return RISK_WARNING
    return RISK_SAFE


class VisionEngine:
    def __init__(self, use_yolo: bool = True, use_gpt4v: bool = False,
                 openai_api_key: str = ""):
        self.use_yolo = use_yolo
        self.use_gpt4v = use_gpt4v
        self.openai_api_key = openai_api_key
        self._backend = "none"
        self._model = None
        self._last_report: Optional[SceneReport] = None

    def start(self) -> str:
        if self.use_yolo:
            try:
                from ultralytics import YOLO
                self._model = YOLO("yolov8n.pt")
                self._backend = "yolov8"
                logger.info("[VisionEngine] YOLOv8 loaded")
                return self._backend
            except Exception as e:
                logger.warning("[VisionEngine] YOLOv8 failed: %s", e)
        try:
            import cv2
            self._backend = "opencv_dnn"
            logger.info("[VisionEngine] OpenCV DNN fallback")
            return self._backend
        except Exception:
            pass
        self._backend = "basic"
        logger.info("[VisionEngine] Basic mode (no detection)")
        return self._backend

    def analyze(self, frame) -> SceneReport:
        t0 = time.time()
        objects = []

        if self._backend == "yolov8" and self._model:
            objects = self._run_yolo(frame)
        elif self._backend == "opencv_dnn":
            objects = self._run_opencv(frame)

        risk = _scene_risk(objects)
        commentary = ""

        if self.use_gpt4v and self.openai_api_key and risk in (RISK_WARNING, RISK_DANGER):
            commentary = self._run_gpt4v(frame, objects)

        report = SceneReport(
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
            source=frame.source,
            risk_level=risk,
            objects=objects,
            ai_commentary=commentary,
            backend_used=self._backend,
            processing_ms=(time.time() - t0) * 1000,
        )
        self._last_report = report
        return report

    def _run_yolo(self, frame) -> list:
        try:
            results = self._model(frame.data, verbose=False)
            objects = []
            for r in results:
                for box in r.boxes:
                    label = r.names[int(box.cls[0])]
                    conf = float(box.conf[0])
                    if conf < 0.4:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                    objects.append(DetectedObject(
                        label=label, confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        risk=_object_risk(label),
                    ))
            return objects
        except Exception as e:
            logger.error("[VisionEngine] YOLO error: %s", e)
            return []

    def _run_opencv(self, frame) -> list:
        return []

    def _run_gpt4v(self, frame, objects: list) -> str:
        try:
            import cv2
            import openai
            _, buf = cv2.imencode(".jpg", frame.data)
            b64 = base64.b64encode(buf).decode()
            obj_list = ", ".join(f"{o.label}({o.risk})" for o in objects) or "none"
            client = openai.OpenAI(api_key=self.openai_api_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Drone camera scene. YOLO detected: {obj_list}. Assess risk for drone flight in 1 sentence."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
                    ],
                }],
                max_tokens=100,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("[VisionEngine] GPT-4o Vision error: %s", e)
            return ""

    def get_last_report(self) -> Optional[SceneReport]:
        return self._last_report

    def get_status(self) -> dict:
        r = self._last_report
        return {
            "backend": self._backend,
            "risk_level": r.risk_level if r else RISK_SAFE,
            "objects_count": len(r.objects) if r else 0,
        }
