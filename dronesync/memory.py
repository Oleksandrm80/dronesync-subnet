"""
DroneSync - Drone Memory
Each drone accumulates flight experience stored on-chain.
Experience is an asset — a drone with 1000 hours is worth more than a new one.
"""
import hashlib
import time


class DroneMemory:
    """
    Persistent flight experience for a drone.
    Stores dangerous zones, wind patterns, obstacle history.
    Memory hash goes on-chain — tamper-evident experience record.
    """

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.dangerous_zones = []
        self.wind_patterns = []
        self.obstacle_encounters = []
        self.total_flight_hours = 0.0
        self.missions_completed = 0

    def record_flight(self, positions: list, duration_s: float,
                      obstacles: list = None, wind_ms: float = 0.0):
        """Record flight experience after each mission."""
        self.total_flight_hours += duration_s / 3600
        self.missions_completed += 1

        if wind_ms > 8.0:
            self.wind_patterns.append({
                "lat": positions[0][0],
                "lon": positions[0][1],
                "wind_ms": wind_ms,
                "timestamp": int(time.time())
            })

        if obstacles:
            for obs in obstacles:
                self.obstacle_encounters.append({
                    "obstacle_id": obs.get("obstacle_id", "unknown"),
                    "type": obs.get("type", "unknown"),
                    "timestamp": int(time.time())
                })

    def is_zone_dangerous(self, lat: float, lon: float,
                          radius_m: float = 100) -> bool:
        """Check if a position is near a known dangerous zone."""
        import math
        for zone in self.dangerous_zones:
            dlat = math.radians(lat - zone["lat"])
            dlon = math.radians(lon - zone["lon"])
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(zone["lat"])) * math.sin(dlon/2)**2
            dist = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            if dist < radius_m:
                return True
        return False

    def get_memory_record(self) -> dict:
        """Return on-chain memory record."""
        memory_data = {
            "drone_id": self.drone_id,
            "missions_completed": self.missions_completed,
            "total_flight_hours": round(self.total_flight_hours, 2),
            "dangerous_zones": len(self.dangerous_zones),
            "wind_patterns": len(self.wind_patterns),
            "obstacle_encounters": len(self.obstacle_encounters)
        }
        memory_hash = hashlib.sha256(str(memory_data).encode()).hexdigest()
        memory_data["memory_hash"] = memory_hash
        memory_data["on_chain_ready"] = True
        memory_data["asset_value"] = self._compute_asset_value()
        return memory_data

    def _compute_asset_value(self) -> str:
        """More experience = higher asset value."""
        if self.missions_completed >= 100:
            return "HIGH"
        elif self.missions_completed >= 20:
            return "MEDIUM"
        else:
            return "LOW"
