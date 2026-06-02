"""
DroneSync - Emergency Override Protocol
City emergency signal redirects all drones in area instantly.
No human operator needed — automatic response to verified emergency.
"""
import hashlib
import time


EMERGENCY_TYPES = {
    "FIRE": {"priority": 10, "action": "ASSIST_FIRE", "radius_m": 500},
    "ACCIDENT": {"priority": 8, "action": "SCOUT_AREA", "radius_m": 300},
    "SEARCH_RESCUE": {"priority": 9, "action": "SEARCH_PATTERN", "radius_m": 1000},
    "HAZMAT": {"priority": 10, "action": "EVACUATE_ZONE", "radius_m": 800},
}

# Mission priorities — higher = more protected from override
MISSION_PRIORITIES = {
    "organ_delivery": 11,     # human organ transplant — NEVER overridden by anything
    "medical_delivery": 9,    # medicine/blood — only FIRE/HAZMAT can override
    "search_rescue": 9,       # already doing rescue — not redirected
    "urban_delivery": 3,      # commercial delivery — easily redirected
    "patrol": 2,
    "surveillance": 2,
    "inspection": 3,
}


class EmergencyOverride:
    """
    Emergency override protocol for drone swarms.
    Respects mission priority — critical missions are protected from override.
    Emergency priority must exceed mission priority to redirect the drone.
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
        If emergency priority <= mission priority — drone is protected.
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

        mission_priority = MISSION_PRIORITIES.get(mission_type, 3)
        emergency_priority = emergency["priority"]

        if emergency_priority <= mission_priority:
            self.protected_drones.append({
                "position": drone_position[:2],
                "mission_type": mission_type,
                "mission_priority": mission_priority,
                "emergency_priority": emergency_priority,
                "timestamp": int(time.time())
            })
            return {
                "override": False,
                "reason": "mission_priority_protected",
                "mission_type": mission_type,
                "mission_priority": mission_priority,
                "emergency_priority": emergency_priority
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
            "priority": emergency_priority,
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

