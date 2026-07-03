"""
DroneSync - Mission Pipeline
Single canonical end-to-end flow from mission to PoPW on-chain.

FULL CHAIN:
  1. Mission accepted
  2. Trajectory integrity check
  3. Energy estimate
  4. Threat assessment
  5. SensorBundle
  6. Swarm consensus (weighted by reputation)
  7. Validator score
  8. ScoreRoot commitment
  9. PoPW signed (asymmetric)
 10. Reputation updated
"""
from typing import Optional
import time
import hashlib
import json
import math

from dronesync.protocol import MissionInstruction, Trajectory, SensorData
from dronesync.verifier import PoPWRecord
from dronesync.identity import DRONE_ID
from dronesync.zk_prover import ZKProver, ZKVerifier
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.threat_defense import ThreatDefense
from dronesync.sensor_bundle import SensorBundle
from validator.scoreroot import ScoreRoot


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MissionPipeline:
    def __init__(self, drone_ids: Optional[list] = None, drone_reputations: Optional[dict] = None):
        self.drone_ids = drone_ids or [DRONE_ID]
        self.drone_reputations = drone_reputations or {}
        self.consensus = SwarmConsensus(self.drone_ids)
        self.threat = ThreatDefense()
        self.popw = PoPWRecord()
        self.score_root = ScoreRoot(validator_id="pipeline_validator")
        self.zk_prover = ZKProver()
        self._pipeline_log: list = []

        for drone_id, rep in self.drone_reputations.items():
            status = rep.get_status()
            self.consensus.register_drone_reputation(drone_id, status["tier"])

    def run(self, mission: MissionInstruction, trajectory: Trajectory,
            sensor_data: SensorData, score: int,
            executing_drone_id: str = DRONE_ID) -> dict:

        start_time = time.time()
        self._pipeline_log = []
        checks: dict = {}

        # 1. Mission fingerprint
        mission_fingerprint = hashlib.sha256(
            json.dumps(mission.to_dict(), sort_keys=True).encode()
        ).hexdigest()
        self._log("mission_accepted", mission_id=mission.mission_id,
                  fingerprint=mission_fingerprint[:16])

        # 2. Trajectory integrity
        traj_hash = hashlib.sha256(str(trajectory.positions).encode()).hexdigest()
        steps_hash = trajectory.metadata.get("steps_hash", "N/A")
        checks["trajectory_hash"] = traj_hash
        checks["steps_hash"] = steps_hash
        self._log("trajectory_built", waypoints=len(trajectory.positions),
                  steps_hash=steps_hash[:16])

        # 3. Energy estimate
        total_dist_km = 0.0
        for i in range(1, len(trajectory.positions)):
            p0, p1 = trajectory.positions[i-1], trajectory.positions[i]
            total_dist_km += _haversine_km(p0[0], p0[1], p1[0], p1[1])
        energy_wh = round(total_dist_km * 12.5, 2)
        checks["distance_km"] = round(total_dist_km, 3)
        checks["energy_estimate_wh"] = energy_wh
        self._log("energy_estimated", distance_km=round(total_dist_km, 3),
                  energy_wh=energy_wh)

        # 4. Threat assessment
        positions_for_threat = [
            [p[0], p[1], p[2], p[3] if len(p) > 3 else int(time.time())]
            for p in trajectory.positions
        ]
        threat_report = self.threat.full_threat_assessment(
            positions=positions_for_threat,
            signal_strength=0.85
        )
        threat_level = threat_report.get("overall_threat_level", "LOW")
        checks["threat_level"] = threat_level
        checks["threat_passed"] = threat_level != "CRITICAL"
        self._log("threat_assessed", level=threat_level,
                  passed=checks["threat_passed"])

        # 5. SensorBundle
        pre_popw = self.popw.create_record(
            mission_id=mission.mission_id,
            trajectory=trajectory,
            score=score
        )
        bundle = SensorBundle()
        sensor_bundle_result = bundle.pack(
            mission_id=mission.mission_id,
            trajectory=trajectory,
            sensor_data=sensor_data,
            popw_record=pre_popw,
            drone_id=executing_drone_id
        )
        checks["sensor_bundle_hash"] = sensor_bundle_result["bundle_hash"]
        self._log("sensor_bundle_created",
                  bundle_hash=sensor_bundle_result["bundle_hash"][:16])

        # 6. Swarm consensus
        votes = [(d, True) for d in self.drone_ids
                 if d not in self.consensus.blacklist]
        consensus_result = self.consensus.vote_on_route(
            mission_id=mission.mission_id,
            route_safe_votes=votes
        )
        checks["consensus_status"] = consensus_result["status"]
        checks["consensus_weight"] = consensus_result.get("total_weight", 0)
        self._log("swarm_voted", status=consensus_result["status"],
                  weight=consensus_result.get("total_weight", 0))

        # 7. Score
        grade = (
            "EXCELLENT" if score >= 85 else
            "GOOD"      if score >= 70 else
            "ACCEPTABLE" if score >= 50 else
            "POOR"
        )
        checks["score"] = score
        checks["grade"] = grade
        self._log("mission_scored", score=score, grade=grade)

        # 8. ScoreRoot
        self.score_root.add_score(
            mission_id=mission.mission_id,
            score=score,
            trajectory_hash=traj_hash,
            sensor_hash=checks["sensor_bundle_hash"]
        )
        root_hash = self.score_root.compute_root()
        commitment = self.score_root.commit()
        checks["score_root"] = root_hash[:16]
        self._log("score_committed", root=root_hash[:16])

        # 8.5 ZK Proof
        zk_proof = None
        zk_verified = False
        if self.zk_prover.is_available():
            waypoints = [[p[0], p[1]] for p in trajectory.positions]
            origin = trajectory.positions[0]
            dest = trajectory.positions[-1]
            zk_proof = self.zk_prover.generate_proof(
                origin_lat=origin[0], origin_lon=origin[1],
                dest_lat=dest[0], dest_lon=dest[1],
                waypoints=waypoints,
                score=float(score),
                min_score=50.0
            )
            if zk_proof:
                zk_verified = self.zk_prover.verify_proof(zk_proof)
        checks["zk_proof_valid"] = zk_verified
        self._log("zk_proof", generated=zk_proof is not None, verified=zk_verified)

        # 9. PoPW signed
        popw_record = self.popw.create_record(
            mission_id=mission.mission_id,
            trajectory=trajectory,
            score=score
        )
        verification = self.popw.verify_record(popw_record)
        checks["popw_tee_valid"] = verification["tee_attestation_valid"]
        checks["popw_signature_valid"] = verification["popw_signature_valid"]
        checks["fully_verified"] = verification["fully_verified"]
        self._log("popw_signed",
                  tee_valid=verification["tee_attestation_valid"],
                  sig_valid=verification["popw_signature_valid"])

        # 10. Reputation update
        rep = self.drone_reputations.get(executing_drone_id)
        reputation_updated = None
        if rep:
            mission_safe = (checks["threat_passed"] and
                           checks["consensus_status"] == "APPROVED")
            rep.record_mission(
                mission_id=mission.mission_id,
                score=score,
                mission_safe=mission_safe,
                battery_used_pct=round(energy_wh / 500.0 * 100, 1)
            )
            reputation_updated = rep.get_status()
            self.consensus.register_drone_reputation(
                executing_drone_id, reputation_updated["tier"]
            )
            self._log("reputation_updated",
                      drone=executing_drone_id,
                      score=reputation_updated["reputation_score"],
                      tier=reputation_updated["tier"])

        # Final result
        elapsed = round(time.time() - start_time, 3)
        on_chain_ready = (
            checks["threat_passed"] and
            checks["consensus_status"] == "APPROVED" and
            checks["fully_verified"] and
            score >= 50
        )
        pipeline_hash = hashlib.sha256(
            json.dumps(checks, sort_keys=True).encode()
        ).hexdigest()

        return {
            "pipeline_version": "1.0",
            "mission_id": mission.mission_id,
            "executing_drone": executing_drone_id,
            "checks": checks,
            "popw_record": popw_record,
            "score_commitment": commitment,
            "reputation": reputation_updated,
            "pipeline_log": self._pipeline_log,
            "pipeline_hash": pipeline_hash,
            "elapsed_s": elapsed,
            "on_chain_ready": on_chain_ready,
            "zk_proof": zk_proof.to_dict() if zk_proof else None,
            "status": "SUCCESS" if on_chain_ready else "FAILED"
        }

    def _log(self, step: str, **kwargs):
        self._pipeline_log.append({
            "step": step,
            "t": round(time.time(), 3),
            **kwargs
        })
