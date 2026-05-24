"""
DroneSync Subnet — Core Protocol Definitions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import hashlib
import json
import time


class MissionType(Enum):
    URBAN_DELIVERY = "urban_delivery"
    SWARM_SURVEY = "swarm_survey"
    OBSTACLE_RACE = "obstacle_race"
    FORMATION_FLY = "formation_fly"
    EMERGENCY_ROUTE = "emergency_route"


class MissionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SCORED = "scored"


@dataclass
class Waypoint:
    lat: float
    lon: float
    alt: float
    speed: float = 5.0
    hover_time: float = 0.0


@dataclass
class MissionInstruction:
    mission_id: str
    mission_type: MissionType
    origin: Waypoint
    destination: Waypoint
    waypoints: List[Waypoint] = field(default_factory=list)
    drone_count: int = 1
    payload_kg: float = 0.5
    priority: int = 1
    deadline_unix: Optional[float] = None
    reward_knx: float = 1.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "mission_type": self.mission_type.value,
            "origin": vars(self.origin),
            "destination": vars(self.destination),
            "drone_count": self.drone_count,
            "payload_kg": self.payload_kg,
            "priority": self.priority,
            "reward_knx": self.reward_knx,
        }

    def instruction_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()