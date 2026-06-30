"""
DroneSync - MAVLink Telemetry Emulator
Simulates real drone telemetry: GPS, battery, speed, altitude.
"""
import math
import time
import random


class MAVLinkEmulator:
    """
    Emulates MAVLink telemetry from a real drone.
    Generates realistic flight data for DroneSync testing.
    """

    def __init__(self, start_lat: float = 0.0, start_lon: float = 0.0):
        self.lat = start_lat
        self.lon = start_lon
        self.alt = 0.0
        self.speed = 0.0
        self.heading = 0.0
        self.battery = 100.0
        self.t = 0
        self._phase = "takeoff"

    def tick(self) -> dict:
        """Generate one telemetry frame."""
        self.t += 1
        self._update_phase()
        self._update_position()
        self._update_battery()

        return {
            "timestamp": time.time(),
            "lat": round(self.lat, 7),
            "lon": round(self.lon, 7),
            "alt": round(self.alt, 2),
            "speed_ms": round(self.speed, 2),
            "heading": round(self.heading, 1),
            "battery_pct": round(self.battery, 1),
            "phase": self._phase,
            "gps_fix": 3,
            "satellites": random.randint(8, 14),
        }

    def _update_phase(self):
        if self.t < 10:
            self._phase = "takeoff"
        elif self.t < 80:
            self._phase = "cruise"
        elif self.t < 90:
            self._phase = "return"
        else:
            self._phase = "landing"

    def _update_position(self):
        if self._phase == "takeoff":
            self.alt = min(50.0, self.alt + 5.0)
            self.speed = min(5.0, self.speed + 0.5)

        elif self._phase == "cruise":
            self.speed = 12.0 + random.uniform(-1, 1)
            self.heading = (self.heading + random.uniform(-5, 5)) % 360
            rad = math.radians(self.heading)
            self.lat += math.cos(rad) * 0.00005
            self.lon += math.sin(rad) * 0.00005
            self.alt = 50.0 + random.uniform(-2, 2)

        elif self._phase == "return":
            self.speed = 8.0
            self.heading = (self.heading + 180) % 360

        elif self._phase == "landing":
            self.alt = max(0.0, self.alt - 3.0)
            self.speed = max(0.0, self.speed - 1.0)

    def _update_battery(self):
        drain = 0.05 if self._phase == "cruise" else 0.02
        self.battery = max(0.0, self.battery - drain)

    def run_mission(self, duration_ticks: int = 100) -> list:
        """Run full mission and return telemetry frames."""
        frames = []
        for _ in range(duration_ticks):
            frames.append(self.tick())
        return frames


def telemetry_to_score(frames: list) -> dict:
    """Convert telemetry frames to DroneSync mission score."""
    if not frames:
        return {"total_score": 0.0, "grade": "POOR"}

    avg_battery = sum(f["battery_pct"] for f in frames) / len(frames)
    avg_speed = sum(f["speed_ms"] for f in frames) / len(frames)
    min_alt = min(f["alt"] for f in frames)
    gps_ok = all(f["gps_fix"] >= 3 for f in frames)

    battery_score = avg_battery / 100.0
    speed_score = min(1.0, avg_speed / 15.0)
    alt_score = 1.0 if min_alt >= 10.0 else 0.5
    gps_score = 1.0 if gps_ok else 0.3

    total = (battery_score * 0.3 + speed_score * 0.3 +
             alt_score * 0.2 + gps_score * 0.2)

    if total >= 0.85:
        grade = "EXCELLENT"
    elif total >= 0.70:
        grade = "GOOD"
    elif total >= 0.55:
        grade = "AVERAGE"
    else:
        grade = "POOR"

    return {
        "total_score": round(total, 4),
        "grade": grade,
        "battery_avg": round(avg_battery, 1),
        "speed_avg": round(avg_speed, 2),
        "gps_ok": gps_ok,
        "frames": len(frames),
    }
