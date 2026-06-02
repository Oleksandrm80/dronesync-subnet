"""
DroneSync - Emergency Override Protocol
City emergency signal redirects compatible drones in area.
Each emergency type requests specific drone types — wrong type = not redirected.
"""
import hashlib
import time


# Each emergency needs specific drone capabilities
EMERGENCY_TYPES = {
    "FIRE":          {"priority": 10, "action": "ASSIST_FIRE",    "radius_m": 500,  "needs": ["fire", "cargo", "patrol"]},
    "ACCIDENT":      {"priority": 8,  "action": "SCOUT_AREA",     "radius_m": 300,  "needs": ["patrol", "surveillance", "cargo"]},
    "SEARCH_RESCUE": {"priority": 9,  "action": "SEARCH_PATTERN", "radius_m": 1000, "needs": ["patrol", "surveillance", "cargo", "medical"]},
    "HAZMAT":        {"priority": 10, "action": "EVACUATE_ZONE",  "radius_m": 800,  "needs": ["hazmat", "patrol", "cargo"]},
    "MEDICAL_EMERGENCY": {"priority": 9, "action": "DELIVER_SUPPLIES", "radius_m": 400, "needs": ["medical", "cargo"]},
}

# Each mission type maps to a drone capability
MISSION_DRONE_TYPE = {
    "organ_delivery":    "medical",
    "medical_delivery":  "medical",
    "urban_delivery":    "cargo",
    "patrol":            "patrol",
    "surveillance":      "surveillance",
    "inspection":        "patrol",
    "fire_support":      "fire",
    "hazmat_support":    "hazmat",
}


class EmergencyOverride:
    """
    Emergency override respects both priority and drone type compatibility.
    A fire emergency won't redirect a medical drone — wrong tool for the job.
    A medical emergency won't redirect a surveillance drone.
    """

    def __init__(self):
        self.active_emergencies = []
        self.redirected_drones = []
        self.protected_drones = []

    def broadcast_emergency(self, emergency_type: str, location: dict,
                             authority_id: str) -> dict:
        if emergency_type not in EMERGENCY_TYPES:
            return {"status": "REJECTED", "reason": "unknown_emergency_type"}

        config = EMERGENCY_TYPES[emergency_type]
        timestamp = int(time.time())
        emergency = {
            "emergency_id": "EMG_" + str(timestamp),
            "type": emergency_type,
            "location": location,
            "authority_id": authority_id,
            "action": config["action"],
            "priority": config["priority"],
            "radius_m": config["radius_m"],
            "needs": config["needs"],
            "timestamp": timestamp,
            "status": "ACTIVE"
        }
        self.active_emergencies.append(emergency)
        return emergency

    def check_drone_override(self, drone_position: list,
                              emergency: dict,
                              mission_type: str = "urban_delivery") -> dict:
        """
        Check if drone should be redirected.
        Two conditions must both be true:
        1. Drone is within emergency radius
        2. Drone type is compatible with what emergency needs
        """
        import math
        elat = emergency["location"]["lat"]
        elon = emergency["location"]["lon"]
        dlat = math.radians(drone_position[0] - elat)
        dlon = math.radians(drone_position[1] - elon)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(drone_position[0])) *
             math.cos(math.radians(elat)) *
             math.sin(dlon/2)**2)
        dist = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        if dist > emergency["radius_m"]:
            return {"override": False, "reason": "outside_radius"}

        drone_type = MISSION_DRONE_TYPE.get(mission_type, "cargo")
        needed_types = emergency.get("needs", [])

        if drone_type not in needed_types:
            self.protected_drones.append({
                "position": drone_position[:2],
                "mission_type": mission_type,
                "drone_type": drone_type,
                "emergency_type": emergency["type"],
                "reason": "incompatible_type",
                "timestamp": int(time.time())
            })
            return {
                "override": False,
                "reason": "incompatible_drone_type",
                "drone_type": drone_type,
                "emergency_needs": needed_types,
                "note": "wrong drone type — emergency has dedicated resources"
            }

        self.redirected_drones.append({
            "position": drone_position[:2],
            "emergency_id": emergency["emergency_id"],
            "distance_m": round(dist, 1),
            "timestamp": int(time.time())
        })
        return {
            "override": True,
            "action": emergency["action"],
            "emergency_id": emergency["emergency_id"],
            "distance_to_emergency_m": round(dist, 1),
            "drone_type": drone_type,
            "mission_type": mission_type
        }

    def get_status(self) -> dict:
        status_hash = hashlib.sha256(
            str(self.active_emergencies).encode()
        ).hexdigest()
        return {
            "active_emergencies": len(self.active_emergencies),
            "redirected_drones": len(self.redirected_drones),
            "protected_drones": len(self.protected_drones),
            "status_hash": status_hash,
            "on_chain_ready": True
        }
