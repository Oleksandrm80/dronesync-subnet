"""
dronesync/mavlink_adapter.py

MAVLink adapter for PX4 SITL / ArduPilot SITL.
Reads real telemetry (GPS, IMU, battery) and converts
to DroneSync Trajectory + SensorData for PoPW generation.
"""

import time
import logging
from typing import List, Tuple, Optional

from dronesync.protocol import Trajectory, SensorData

logger = logging.getLogger(__name__)


class TelemetryFrame:

    def __init__(self):
        self.timestamp: float = time.time()
        self.lat: float = 0.0
        self.lon: float = 0.0
        self.alt: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.vz: float = 0.0
        self.roll: float = 0.0
        self.pitch: float = 0.0
        self.yaw: float = 0.0
        self.battery_voltage: float = 0.0
        self.battery_remaining: int = 100
        self.groundspeed: float = 0.0
        self.heading: float = 0.0
        self.armed: bool = False


class MAVLinkAdapter:

    def __init__(self, connection_string: str = "udp:127.0.0.1:14550"):
        self.connection_string = connection_string
        self._mav = None
        self._frames: List[TelemetryFrame] = []
        self._connected = False

    def connect(self) -> bool:
        try:
            from pymavlink import mavutil
            self._mav = mavutil.mavlink_connection(self.connection_string)
            logger.info("Waiting for heartbeat...")
            self._mav.wait_heartbeat(timeout=10)
            self._connected = True
            logger.info("Connected to drone")
            return True
        except ImportError:
            logger.error("pymavlink not installed. Run: pip install pymavlink")
            return False
        except Exception as e:
            logger.error("Connection failed: %s", e)
            return False

    def disconnect(self):
        if self._mav:
            self._mav.close()
            self._connected = False

    def _poll_frame(self) -> Optional[TelemetryFrame]:
        if not self._mav:
            return None
        frame = TelemetryFrame()
        frame.timestamp = time.time()
        gps = self._mav.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if gps:
            frame.lat = gps.lat / 1e7
            frame.lon = gps.lon / 1e7
            frame.alt = gps.alt / 1000.0
            frame.vx = gps.vx / 100.0
            frame.vy = gps.vy / 100.0
            frame.vz = gps.vz / 100.0
        att = self._mav.recv_match(type="ATTITUDE", blocking=False)
        if att:
            frame.roll = att.roll
            frame.pitch = att.pitch
            frame.yaw = att.yaw
        bat = self._mav.recv_match(type="BATTERY_STATUS", blocking=False)
        if bat:
            frame.battery_voltage = bat.voltages[0] / 1000.0 if bat.voltages else 0.0
            frame.battery_remaining = bat.battery_remaining
        hb = self._mav.recv_match(type="HEARTBEAT", blocking=False)
        if hb:
            frame.armed = bool(hb.base_mode & 0x80)
        return frame

    def record_mission(self, duration_seconds: int = 30,
                       poll_hz: int = 5) -> Tuple[Trajectory, SensorData]:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        self._frames = []
        interval = 1.0 / poll_hz
        end_time = time.time() + duration_seconds
        logger.info("Recording telemetry for %ds...", duration_seconds)
        while time.time() < end_time:
            frame = self._poll_frame()
            if frame and frame.lat != 0.0:
                self._frames.append(frame)
            time.sleep(interval)
        logger.info("Recorded %d frames", len(self._frames))
        return self._to_trajectory(), self._to_sensor_data()

    def _to_trajectory(self) -> Trajectory:
        positions = []
        velocities = []
        timestamps = []
        for f in self._frames:
            speed = (f.vx ** 2 + f.vy ** 2 + f.vz ** 2) ** 0.5
            positions.append([f.lat, f.lon, f.alt, f.timestamp])
            velocities.append(round(speed, 3))
            timestamps.append(int(f.timestamp * 1000))
        metadata = {
            "source": "mavlink",
            "connection": self.connection_string,
            "frame_count": len(self._frames),
            "duration_s": (self._frames[-1].timestamp - self._frames[0].timestamp)
                          if len(self._frames) >= 2 else 0,
            "avg_battery": sum(f.battery_remaining for f in self._frames) / len(self._frames)
                           if self._frames else 0,
            "max_altitude": max((f.alt for f in self._frames), default=0),
            "max_speed": max(velocities, default=0),
        }
        return Trajectory(positions=positions, velocities=velocities,
                          timestamps=timestamps, metadata=metadata)

    def _to_sensor_data(self) -> SensorData:
        if not self._frames:
            return SensorData(lidar_points=[], camera_detections=[],
                              imu_data={}, timestamp=int(time.time() * 1000))
        imu_samples = [
            {"roll": f.roll, "pitch": f.pitch, "yaw": f.yaw, "ts": f.timestamp}
            for f in self._frames
        ]
        battery_samples = [
            {"voltage": f.battery_voltage, "remaining_pct": f.battery_remaining, "ts": f.timestamp}
            for f in self._frames
        ]
        return SensorData(
            lidar_points=[],
            camera_detections=[],
            imu_data={
                "source": "mavlink_real",
                "samples": imu_samples,
                "battery": battery_samples,
                "armed_frames": sum(1 for f in self._frames if f.armed),
                "total_frames": len(self._frames),
            },
            timestamp=int(self._frames[-1].timestamp * 1000),
        )

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def is_connected(self) -> bool:
        return self._connected


class SITLReplay:

    def __init__(self, log_path: str):
        self.log_path = log_path

    def to_trajectory_and_sensor(self) -> Tuple[Trajectory, SensorData]:
        try:
            from pymavlink import mavutil
            mlog = mavutil.mavlink_connection(self.log_path)
        except ImportError:
            raise RuntimeError("pymavlink not installed. Run: pip install pymavlink")
        frames: List[TelemetryFrame] = []
        while True:
            msg = mlog.recv_match(blocking=False)
            if msg is None:
                break
            if msg.get_type() == "GLOBAL_POSITION_INT":
                f = TelemetryFrame()
                f.timestamp = msg._timestamp if hasattr(msg, "_timestamp") else time.time()
                f.lat = msg.lat / 1e7
                f.lon = msg.lon / 1e7
                f.alt = msg.alt / 1000.0
                f.vx = msg.vx / 100.0
                f.vy = msg.vy / 100.0
                f.vz = msg.vz / 100.0
                if f.lat != 0.0:
                    frames.append(f)
        adapter = MAVLinkAdapter.__new__(MAVLinkAdapter)
        adapter._frames = frames
        adapter.connection_string = f"replay:{self.log_path}"
        return adapter._to_trajectory(), adapter._to_sensor_data()
