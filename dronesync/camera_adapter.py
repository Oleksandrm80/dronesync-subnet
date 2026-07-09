"""
dronesync/camera_adapter.py
Universal camera adapter for DroneSync.
Supports: RTSP, USB/Webcam, MAVLink camera feed, Video file, ROS2 topic
"""

import time
import logging
import threading
from dataclasses import dataclass
from typing import Optional, Callable, Iterator

logger = logging.getLogger(__name__)


@dataclass
class CameraFrame:
    frame_id: int
    timestamp: float
    source: str
    width: int
    height: int
    data: object


@dataclass
class CameraConfig:
    source_type: str = "usb"
    rtsp_url: str = ""
    usb_index: int = 0
    file_path: str = ""
    ros2_topic: str = "/camera/image_raw"
    mavlink_connection: str = "udp:127.0.0.1:14550"
    fps: int = 10
    width: int = 640
    height: int = 480

    @staticmethod
    def from_rtsp(url: str, fps: int = 10) -> "CameraConfig":
        return CameraConfig(source_type="rtsp", rtsp_url=url, fps=fps)

    @staticmethod
    def from_usb(index: int = 0, fps: int = 10) -> "CameraConfig":
        return CameraConfig(source_type="usb", usb_index=index, fps=fps)

    @staticmethod
    def from_file(path: str) -> "CameraConfig":
        return CameraConfig(source_type="file", file_path=path)

    @staticmethod
    def from_mavlink(connection: str = "udp:127.0.0.1:14550") -> "CameraConfig":
        return CameraConfig(source_type="mavlink", mavlink_connection=connection)

    @staticmethod
    def from_ros2(topic: str = "/camera/image_raw") -> "CameraConfig":
        return CameraConfig(source_type="ros2", ros2_topic=topic)


class CameraAdapter:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._cap = None
        self._running = False
        self._frame: Optional[CameraFrame] = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._callbacks: list = []

    def start(self) -> bool:
        try:
            import cv2
            src = self._resolve_source()
            self._cap = cv2.VideoCapture(src)
            if not self._cap.isOpened():
                logger.error("[CameraAdapter] Cannot open: %s", src)
                return False
            self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            logger.info("[CameraAdapter] Started: %s", src)
            return True
        except Exception as e:
            logger.error("[CameraAdapter] start error: %s", e)
            return False

    def _resolve_source(self):
        t = self.config.source_type
        if t == "rtsp":
            return self.config.rtsp_url
        if t == "usb":
            return self.config.usb_index
        if t == "file":
            return self.config.file_path
        if t == "mavlink":
            return self._get_mavlink_rtsp()
        return self.config.usb_index

    def _get_mavlink_rtsp(self) -> int:
        try:
            from pymavlink import mavutil
            mav = mavutil.mavlink_connection(self.config.mavlink_connection)
            mav.wait_heartbeat(timeout=5)
            mav.mav.command_long_send(
                mav.target_system, mav.target_component,
                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                0, 269, 1, 0, 0, 0, 0, 0
            )
            msg = mav.recv_match(type="VIDEO_STREAM_INFORMATION", blocking=True, timeout=5)
            if msg:
                from urllib.parse import urlparse
                parsed = urlparse(msg.uri)
                if parsed.scheme in ("rtsp", "rtsps") and parsed.hostname:
                    return msg.uri
                else:
                    logger.error("[CameraAdapter] Rejected untrusted URI: %s", msg.uri)
        except Exception as e:
            logger.warning("[CameraAdapter] MAVLink RTSP failed: %s", e)
        return self.config.usb_index

    def _capture_loop(self):
        import cv2
        delay = 1.0 / max(self.config.fps, 1)
        while self._running:
            try:
                ret, raw = self._cap.read()
                if not ret:
                    time.sleep(1.0)
                    continue
                h, w = raw.shape[:2]
                frame = CameraFrame(
                    frame_id=self._frame_id,
                    timestamp=time.time(),
                    source=self.config.source_type,
                    width=w, height=h, data=raw,
                )
                with self._lock:
                    self._frame = frame
                    self._frame_id += 1
                for cb in self._callbacks:
                    try:
                        cb(frame)
                    except Exception:
                        pass
                time.sleep(delay)
            except Exception as e:
                logger.error("[CameraAdapter] capture error: %s", e)
                time.sleep(1.0)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
        self._cap = None

    def get_frame(self) -> Optional[CameraFrame]:
        with self._lock:
            return self._frame

    def on_frame(self, callback: Callable):
        self._callbacks.append(callback)

    def stream_frames(self, max_frames: int = 100) -> Iterator[CameraFrame]:
        seen = -1
        count = 0
        while count < max_frames:
            with self._lock:
                f = self._frame
            if f and f.frame_id != seen:
                seen = f.frame_id
                count += 1
                yield f
            else:
                time.sleep(0.05)

    def get_status(self) -> dict:
        with self._lock:
            fid = self._frame.frame_id if self._frame else 0
        return {"source_type": self.config.source_type, "running": self._running, "frame_id": fid}
