"""
dronesync/drone_connector.py

Universal drone connector for DroneSync.
Auto-detects drone manufacturer and connects via the right protocol.

Supported:
  - MAVLink (ArduPilot, PX4, Pixhawk, Holybro, Cuav, Parrot, AgEagle, 3DR)
  - DJI (via MAVLink bridge — no DJI SDK registration required)
  - ROS2 (Skydio, Freefly, Wingtra, custom industrial)

Camera AI:
  - RTSP / USB / MAVLink / File / ROS2 camera sources
  - YOLOv8 object detection + GPT-4o Vision for complex scenes
"""

import logging
from typing import Tuple, Optional

from dronesync.protocol import Trajectory, SensorData
from dronesync.pipeline import MissionPipeline
from dronesync.protocol import MissionInstruction, MissionType, Waypoint
from dronesync.camera_adapter import CameraAdapter, CameraConfig
from dronesync.vision_engine import VisionEngine

logger = logging.getLogger(__name__)


MANUFACTURERS = {
    "mavlink": [
        "ArduPilot", "PX4", "Pixhawk", "Holybro", "Cuav",
        "Parrot (ANAFI)", "AgEagle / senseFly", "3DR Solo",
        "Emlid", "mRobotics", "Matek", "CubePilot",
    ],
    "dji": [
        "DJI Matrice 300 RTK", "DJI Matrice 350 RTK",
        "DJI Matrice 30 / 30T", "DJI Phantom 4 / 4 Pro / 4 RTK",
        "DJI Mavic 2 Enterprise", "DJI Mavic 3 Enterprise",
        "DJI Mavic 3 Multispectral", "DJI Mini 3 / Mini 3 Pro",
        "DJI Agras T40 / T20P",
    ],
    "ros2": [
        "Skydio 2+ / X10", "Freefly Alta X / Astro",
        "Wingtra WingtraOne GEN II", "Autel EVO II Enterprise",
        "Custom industrial (PX4+ROS2)", "Research (ArduPilot+ROS2)",
    ],
}

CONNECTION_METHODS = {
    "usb":    "serial:/dev/ttyUSB0:57600",
    "serial": "serial:/dev/ttyACM0:115200",
    "udp":    "udp:127.0.0.1:14550",
    "tcp":    "tcp:192.168.1.1:14550",
    "wifi":   "udp:192.168.1.1:14550",
}


class DroneConnector:
    def __init__(self, manufacturer: str = "mavlink",
                 connection: str = "udp:127.0.0.1:14550",
                 model: str = "",
                 ros2_firmware: str = "px4",
                 camera_config: Optional[CameraConfig] = None,
                 use_gpt4v: bool = False,
                 openai_api_key: str = ""):
        self.manufacturer = manufacturer.lower()
        self.connection = connection
        self.model = model
        self.ros2_firmware = ros2_firmware
        self._adapter = None
        self._connected = False
        self._camera: Optional[CameraAdapter] = None
        self._vision: Optional[VisionEngine] = None
        self._camera_enabled = False
        self._build_adapter()
        if camera_config:
            self.attach_camera(camera_config, use_gpt4v=use_gpt4v,
                               openai_api_key=openai_api_key)

    def _build_adapter(self):
        if self.manufacturer == "dji":
            from dronesync.dji_adapter import DJIAdapter
            self._adapter = DJIAdapter(
                connection_string=self.connection,
                model=self.model or "DJI Drone"
            )
        elif self.manufacturer == "ros2":
            from dronesync.ros2_adapter import ROS2Adapter
            self._adapter = ROS2Adapter(
                fallback_mavlink=self.connection,
                firmware=self.ros2_firmware
            )
        else:
            from dronesync.mavlink_adapter import MAVLinkAdapter
            self._adapter = MAVLinkAdapter(connection_string=self.connection)

    def attach_camera(self, config: CameraConfig,
                      use_gpt4v: bool = False,
                      openai_api_key: str = "") -> bool:
        self._camera = CameraAdapter(config)
        self._vision = VisionEngine(
            use_yolo=True,
            use_gpt4v=use_gpt4v,
            openai_api_key=openai_api_key,
        )
        backend = self._vision.start()
        ok = self._camera.start()
        if ok:
            self._camera_enabled = True
            logger.info("[DroneConnector] Camera AI attached — backend: %s, source: %s",
                        backend, config.source_type)
        else:
            logger.error("[DroneConnector] Camera failed to start")
        return ok

    def detach_camera(self):
        if self._camera:
            self._camera.stop()
        self._camera = None
        self._vision = None
        self._camera_enabled = False

    def connect(self) -> bool:
        logger.info("[DroneConnector] Connecting %s via %s...",
                    self.manufacturer.upper(), self.connection)
        result = self._adapter.connect()
        self._connected = result
        return result

    def disconnect(self):
        if self._adapter:
            self._adapter.disconnect()
        self.detach_camera()
        self._connected = False

    def record_mission(self, duration_seconds: int = 30,
                       poll_hz: int = 5,
                       run_pipeline: bool = False,
                       mission_id: str = None,
                       score: int = 80) -> Tuple:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        trajectory, sensor_data = self._adapter.record_mission(duration_seconds, poll_hz)
        if self._camera_enabled and self._camera and self._vision:
            scene_reports = []
            for frame in self._camera.stream_frames(max_frames=duration_seconds * poll_hz):
                report = self._vision.analyze(frame)
                scene_reports.append(report.to_dict())
            sensor_data.camera_detections = scene_reports
            logger.info("[DroneConnector] Camera AI: %d scene reports collected",
                        len(scene_reports))
        if not run_pipeline:
            return trajectory, sensor_data
        import time, hashlib
        mid = mission_id or ("CONN_" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:12].upper())
        origin = trajectory.positions[0] if trajectory.positions else [0, 0, 50]
        dest = trajectory.positions[-1] if trajectory.positions else [0, 0, 50]
        mission = MissionInstruction(
            mission_id=mid,
            mission_type=MissionType.URBAN_DELIVERY,
            origin=Waypoint(lat=origin[0], lon=origin[1], alt=origin[2] if len(origin) > 2 else 50),
            destination=Waypoint(lat=dest[0], lon=dest[1], alt=dest[2] if len(dest) > 2 else 50),
        )
        pipeline = MissionPipeline()
        pipeline_result = pipeline.run(mission, trajectory, sensor_data, score)
        logger.info("[DroneConnector] Pipeline: on_chain_ready=%s zk=%s",
                    pipeline_result["on_chain_ready"],
                    pipeline_result.get("zk_proof") is not None)
        return trajectory, sensor_data, pipeline_result

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_last_scene(self):
        if self._vision:
            return self._vision.get_last_report()
        return None

    def get_status(self) -> dict:
        base = {
            "manufacturer": self.manufacturer,
            "connection": self.connection,
            "connected": self._connected,
        }
        if hasattr(self._adapter, "get_status"):
            base.update(self._adapter.get_status())
        if self._camera_enabled and self._camera:
            base["camera"] = self._camera.get_status()
        if self._vision:
            base["vision"] = self._vision.get_status()
        return base

    @staticmethod
    def list_all_supported() -> dict:
        return MANUFACTURERS

    @staticmethod
    def get_connection_string(method: str = "udp") -> str:
        return CONNECTION_METHODS.get(method, CONNECTION_METHODS["udp"])

    @staticmethod
    def from_ui(manufacturer: str, connection_method: str,
                custom_address: str = "", model: str = "") -> "DroneConnector":
        if connection_method == "custom" and custom_address:
            conn = custom_address
        else:
            conn = CONNECTION_METHODS.get(connection_method, CONNECTION_METHODS["udp"])
        return DroneConnector(
            manufacturer=manufacturer,
            connection=conn,
            model=model,
        )
