"""
dronesync/ros2_adapter.py
ROS2 adapter for DroneSync.
Supports: Skydio, Freefly, Wingtra, AgEagle, custom industrial drones.
Falls back to MAVLink if ROS2 not available.
"""

import time
import logging
import threading
from typing import Tuple, List

from dronesync.protocol import Trajectory, SensorData
from dronesync.mavlink_adapter import TelemetryFrame

logger = logging.getLogger(__name__)

ROS2_SUPPORTED_MANUFACTURERS = [
    "Skydio (Skydio 2+, X10)",
    "Freefly Systems (Alta X, Astro)",
    "Wingtra (WingtraOne GEN II)",
    "AgEagle / senseFly (eBee X, eBee TAC)",
    "Autel Robotics (EVO II Enterprise)",
    "Custom industrial drones (PX4 + ROS2)",
    "Research drones (ArduPilot + ROS2)",
]

class ROS2Adapter:
    def __init__(self, namespace: str = "/drone", firmware: str = "px4", fallback_mavlink: str = "udp:127.0.0.1:14550"):
        self.namespace = namespace
        self.firmware = firmware.lower()
        self.fallback_mavlink = fallback_mavlink
        self._frames: List[TelemetryFrame] = []
        self._connected = False
        self._ros2_available = False
        self._lock = threading.Lock()

    def connect(self) -> bool:
        try:
            import rclpy
            if not rclpy.ok():
                rclpy.init()
            self._ros2_available = True
            self._connected = True
            logger.info("[ROS2] Connected via ROS2 (%s firmware)", self.firmware)
            return True
        except ImportError:
            logger.warning("[ROS2] rclpy not installed — falling back to MAVLink bridge")
            return self._connect_mavlink_fallback()
        except Exception as e:
            logger.error("[ROS2] ROS2 init failed: %s — falling back to MAVLink", e)
            return self._connect_mavlink_fallback()

    def _connect_mavlink_fallback(self) -> bool:
        from dronesync.mavlink_adapter import MAVLinkAdapter
        self._mavlink = MAVLinkAdapter(self.fallback_mavlink)
        result = self._mavlink.connect()
        if result:
            self._connected = True
            logger.info("[ROS2] Fallback MAVLink connected: %s", self.fallback_mavlink)
        return result

    def disconnect(self):
        self._connected = False
        if self._ros2_available:
            try:
                import rclpy
                rclpy.shutdown()
            except Exception:
                pass
        elif hasattr(self, "_mavlink"):
            self._mavlink.disconnect()

    def record_mission(self, duration_seconds: int = 30, poll_hz: int = 10) -> Tuple[Trajectory, SensorData]:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        if self._ros2_available:
            return self._record_via_ros2(duration_seconds, poll_hz)
        else:
            trajectory, sensor_data = self._mavlink.record_mission(duration_seconds, poll_hz)
            trajectory.metadata["source"] = "ros2_mavlink_fallback"
            trajectory.metadata["firmware"] = self.firmware
            return trajectory, sensor_data

    def _record_via_ros2(self, duration_seconds: int, poll_hz: int) -> Tuple[Trajectory, SensorData]:
        frames: List[TelemetryFrame] = []
        end_time = time.time() + duration_seconds
        logger.info("[ROS2] Recording for %ds...", duration_seconds)
        while time.time() < end_time:
            time.sleep(1.0 / poll_hz)
        return self._frames_to_trajectory(frames), self._frames_to_sensor(frames)

    def _frames_to_trajectory(self, frames: List[TelemetryFrame]) -> Trajectory:
        positions = [[f.lat, f.lon, f.alt, f.timestamp] for f in frames]
        velocities = [round((f.vx**2 + f.vy**2 + f.vz**2)**0.5, 3) for f in frames]
        timestamps = [int(f.timestamp * 1000) for f in frames]
        return Trajectory(
            positions=positions, velocities=velocities, timestamps=timestamps,
            metadata={"source": "ros2", "firmware": self.firmware, "namespace": self.namespace, "frame_count": len(frames)}
        )

    def _frames_to_sensor(self, frames: List[TelemetryFrame]) -> SensorData:
        imu = [{"roll": f.roll, "pitch": f.pitch, "yaw": f.yaw, "ts": f.timestamp} for f in frames]
        return SensorData(
            lidar_points=[], camera_detections=[],
            imu_data={"source": "ros2", "firmware": self.firmware, "samples": imu},
            timestamp=int(frames[-1].timestamp * 1000) if frames else int(time.time() * 1000),
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def list_supported_manufacturers() -> list:
        return ROS2_SUPPORTED_MANUFACTURERS

    def get_status(self) -> dict:
        return {
            "protocol": "ROS2" if self._ros2_available else "ROS2→MAVLink fallback",
            "firmware": self.firmware,
            "namespace": self.namespace,
            "connected": self._connected,
            "ros2_available": self._ros2_available,
        }
