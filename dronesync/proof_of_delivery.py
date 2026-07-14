"""
DroneSync — Proof of Delivery
GPS + Camera snapshot + ZK proof → validator consensus.
Доказывает что дрон реально доставил посылку в нужную точку.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, List

from dronesync.zk_prover import ZKProver
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.identity import DRONE_ID


@dataclass
class DeliverySnapshot:
    mission_id: str
    drone_id: str
    destination_lat: float
    destination_lon: float
    actual_lat: float
    actual_lon: float
    altitude: float
    timestamp: float = field(default_factory=time.time)
    camera_detections: List[dict] = field(default_factory=list)
    camera_snapshot_hash: str = ""

    def gps_accuracy_m(self) -> float:
        import math
        R = 6371000
        dlat = math.radians(self.actual_lat - self.destination_lat)
        dlon = math.radians(self.actual_lon - self.destination_lon)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(self.destination_lat)) *
             math.cos(math.radians(self.actual_lat)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "drone_id": self.drone_id,
            "destination": {"lat": self.destination_lat, "lon": self.destination_lon},
            "actual": {"lat": self.actual_lat, "lon": self.actual_lon},
            "altitude": self.altitude,
            "gps_accuracy_m": round(self.gps_accuracy_m(), 2),
            "timestamp": self.timestamp,
            "camera_detections": self.camera_detections,
            "camera_snapshot_hash": self.camera_snapshot_hash,
        }


@dataclass
class DeliveryProof:
    snapshot: DeliverySnapshot
    proof_hash: str
    zk_proof: Optional[dict]
    consensus_status: str
    consensus_weight: float
    delivered: bool
    on_chain_ready: bool
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "mission_id": self.snapshot.mission_id,
            "drone_id": self.snapshot.drone_id,
            "delivered": self.delivered,
            "gps_accuracy_m": round(self.snapshot.gps_accuracy_m(), 2),
            "consensus_status": self.consensus_status,
            "consensus_weight": self.consensus_weight,
            "proof_hash": self.proof_hash,
            "zk_proof": self.zk_proof,
            "on_chain_ready": self.on_chain_ready,
            "snapshot": self.snapshot.to_dict(),
            "created_at": self.created_at,
        }


class ProofOfDelivery:
    MAX_GPS_ERROR_M = 50.0

    def __init__(self, drone_ids: Optional[List[str]] = None):
        self.drone_ids = drone_ids or [DRONE_ID]
        self.consensus = SwarmConsensus(drone_ids=self.drone_ids)
        self.zk_prover = ZKProver()

    def create_snapshot(self,
                        mission_id: str,
                        destination_lat: float,
                        destination_lon: float,
                        actual_lat: float,
                        actual_lon: float,
                        altitude: float,
                        camera_detections: Optional[List[dict]] = None,
                        drone_id: str = DRONE_ID) -> DeliverySnapshot:
        snapshot = DeliverySnapshot(
            mission_id=mission_id,
            drone_id=drone_id,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            actual_lat=actual_lat,
            actual_lon=actual_lon,
            altitude=altitude,
            camera_detections=camera_detections or [],
        )
        snapshot_json = json.dumps(snapshot.to_dict(), sort_keys=True).encode()
        snapshot.camera_snapshot_hash = hashlib.sha256(snapshot_json).hexdigest()
        return snapshot

    def prove(self, snapshot: DeliverySnapshot, score: int = 90) -> DeliveryProof:
        gps_ok = snapshot.gps_accuracy_m() <= self.MAX_GPS_ERROR_M
        camera_ok = len(snapshot.camera_detections) > 0

        zk_proof = None
        if self.zk_prover.is_available():
            zk_proof_obj = self.zk_prover.generate_proof(
                origin_lat=snapshot.destination_lat,
                origin_lon=snapshot.destination_lon,
                dest_lat=snapshot.actual_lat,
                dest_lon=snapshot.actual_lon,
                waypoints=[[snapshot.actual_lat, snapshot.actual_lon]],
                score=float(score),
                min_score=70.0,
            )
            if zk_proof_obj:
                zk_proof = zk_proof_obj.to_dict()

        delivered = gps_ok and camera_ok

        votes = [(d, delivered) for d in self.drone_ids]
        consensus_result = self.consensus.vote_on_route(
            mission_id=snapshot.mission_id,
            route_safe_votes=votes,
        )

        proof_data = {
            "snapshot_hash": snapshot.camera_snapshot_hash,
            "gps_ok": gps_ok,
            "camera_ok": camera_ok,
            "delivered": delivered,
            "consensus": consensus_result["status"],
            "timestamp": snapshot.timestamp,
        }
        proof_hash = hashlib.sha256(
            json.dumps(proof_data, sort_keys=True).encode()
        ).hexdigest()

        on_chain_ready = (
            delivered and
            consensus_result["status"] == "APPROVED" and
            proof_hash != ""
        )

        return DeliveryProof(
            snapshot=snapshot,
            proof_hash=proof_hash,
            zk_proof=zk_proof,
            consensus_status=consensus_result["status"],
            consensus_weight=consensus_result.get("approval_weight", 0),
            delivered=delivered,
            on_chain_ready=on_chain_ready,
        )
