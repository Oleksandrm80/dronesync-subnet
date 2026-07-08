"""
dronesync/dji_adapter.py
DJI drone adapter via MAVLink bridge (no DJI SDK registration required).
"""

import time
import logging
from typing import Tuple

from dronesync.protocol import Trajectory, SensorData
from dronesync.mavlink_adapter import MAVLinkAdapter, TelemetryFrame

logger = logging.getLogger(__name__)

DJI_SUPPORTED_MODELS = [
    "Matrice 300 RTK", "Matrice 350 RTK", "Matrice 30 / 30T",
    "Matrice 210 / 210 RTK", "Phantom 4 / 4 Pro / 4 RTK",
    "Mavic 2 Enterprise", "Mavic 3 Enterprise",
    "Mavic 3 Multispectral", "Mini 3 / Mini 3 Pro",
    "Agras T40 / T20P",
]

DJI_BRIDGE_PORTS = {
    "usb":    "serial:/dev/ttyUSB0:57600",
    "udp":    "udp:127.0.0.1:14550",
    "serial": "serial:/dev/ttyACM0:115200",
    "tcp":    "tcp:192.168.1.1:14550",
}

class DJIAdapter:
    def __init__(self, connection_string: str = "udp:127.0.0.1:14550", model: str = "DJI Drone"):
        self.connection_string = connection_string
        self.model = model
        self._adapter = MAVLinkAdapter(connection_string)
        self._connected = False
        self._bridge_info = self._detect_bridge_type(connection_string)

    def _detect_bridge_type(self, conn: str) -> dict:
        if conn.startswith("serial") or conn.startswith("/dev"):
            return {"type": "USB/Serial", "note": "Direct USB via DJI Assistant 2"}
        elif conn.startswith("udp"):
            return {"type": "UDP", "note": "WiFi/Network bridge"}
        elif conn.startswith("tcp"):
            return {"type": "TCP", "note": "DJI Onboard SDK bridge"}
        return {"type": "Unknown", "note": "Custom bridge"}

    def connect(self) -> bool:
        logger.info("[DJI] Connecting to %s via MAVLink bridge (%s)...", self.model, self._bridge_info["type"])
        result = self._adapter.connect()
        if result:
            self._connected = True
            logger.info("[DJI] Connected to %s", self.model)
        else:
            logger.error("[DJI] Connection failed. Ensure DJI MAVLink bridge is running.")
        return result

    def disconnect(self):
        self._adapter.disconnect()
        self._connected = False

    def record_mission(self, duration_seconds: int = 30, poll_hz: int = 5) -> Tuple[Trajectory, SensorData]:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        trajectory, sensor_data = self._adapter.record_mission(duration_seconds, poll_hz)
        trajectory.metadata["source"] = "dji_mavlink_bridge"
        trajectory.metadata["drone_model"] = self.model
        trajectory.metadata["bridge_type"] = self._bridge_info["type"]
        sensor_data.imu_data["source"] = "dji_mavlink_bridge"
        sensor_data.imu_data["drone_model"] = self.model
        return trajectory, sensor_data

    @property
    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def list_supported_models() -> list:
        return DJI_SUPPORTED_MODELS

    @staticmethod
    def get_connection_string(method: str = "udp") -> str:
        return DJI_BRIDGE_PORTS.get(method, DJI_BRIDGE_PORTS["udp"])

    def get_status(self) -> dict:
        return {
            "manufacturer": "DJI",
            "model": self.model,
            "connected": self._connected,
            "connection": self.connection_string,
            "bridge": self._bridge_info,
            "protocol": "MAVLink 2.0 (via bridge)",
        }
