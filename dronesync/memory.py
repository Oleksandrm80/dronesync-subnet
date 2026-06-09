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
    def learn_from_failure(self, mission_id: str, reason: str, 
                           lat: float, lon: float):
        """Record mission failure to avoid repeating mistakes."""
        self.dangerous_zones.append({
            "lat": lat,
            "lon": lon,
            "reason": reason,
            "mission_id": mission_id,
            "timestamp": int(time.time())
        })

    def recommend_action(self, lat: float, lon: float, 
                         wind_ms: float = 0.0) -> str:
        """Recommend action based on accumulated experience."""
        if self.is_zone_dangerous(lat, lon):
            return "HOVER"
        if wind_ms > 10.0:
            return "LAND"
        if self.missions_completed > 50:
            return "PROCEED"
        return "PROCEED_WITH_CAUTION"

    def get_experience_level(self) -> str:
        """Return drone experience tier."""
        if self.missions_completed >= 100:
            return "VETERAN"
        elif self.missions_completed >= 50:
            return "EXPERT"
        elif self.missions_completed >= 20:
            return "EXPERIENCED"
        else:
            return "ROOKIE"

    def save_to_file(self, path: str):
        """Persist memory to disk."""
        import json
        import os
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)       
        with open(path, "w") as f:
            json.dump({
                "drone_id": self.drone_id,
                "dangerous_zones": self.dangerous_zones,
                "wind_patterns": self.wind_patterns,
                "obstacle_encounters": self.obstacle_encounters,
                "total_flight_hours": self.total_flight_hours,
                "missions_completed": self.missions_completed
            }, f, indent=2)

    def load_from_file(self, path: str):
        """Load memory from disk."""
        import json
        import os
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        self.dangerous_zones = data.get("dangerous_zones", [])
        self.wind_patterns = data.get("wind_patterns", [])
        self.obstacle_encounters = data.get("obstacle_encounters", [])
        self.total_flight_hours = data.get("total_flight_hours", 0.0)
        self.missions_completed = data.get("missions_completed", 0)
