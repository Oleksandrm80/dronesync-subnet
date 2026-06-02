# dronesync/protocol.py
"""
DroneSync Subnet — Core Protocol Definitions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
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
            "waypoints": [vars(wp) for wp in self.waypoints],
            "drone_count": self.drone_count,
            "payload_kg": self.payload_kg,
            "priority": self.priority,
            "deadline_unix": self.deadline_unix,
            "reward_knx": self.reward_knx,
            "created_at": self.created_at,
        }


@dataclass
class Trajectory:
    positions: List[List[float]]  # [lat, lon, alt, timestamp]
    velocities: List[float]
    timestamps: List[int]
    metadata: Dict = field(default_factory=dict)


@dataclass
class SensorData:
    lidar_points: List[List[float]]
    camera_detections: List[Dict]
    imu_data: Dict
    timestamp: int


@dataclass
class PoPWArtifact:
    computation_hash: str
    simulation_steps: int
    energy_estimate: float
    constraints_satisfied: bool


class DroneSyncSynapse:
    """
    Synapse for miner-validator communication.
    In production: inherits from bittensor.Synapse.
    """

    def __init__(self, mission: "MissionInstruction" = None):
        self.mission = mission
        self.trajectory: Optional[Trajectory] = None
        self.sensor_data: Optional[SensorData] = None
        self.pow_artifact: Optional[PoPWArtifact] = None
        self.score: Optional[float] = None
        self.metadata: Dict = {}

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission.mission_id if self.mission else None,
            "score": self.score,
            "metadata": self.metadata,
        }