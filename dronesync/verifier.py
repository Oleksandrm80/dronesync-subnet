"""
DroneSync - TEE Verifier Module
Trusted Execution Environment simulation for PoPW artifact attestation
In production: integrates with Intel SGX / ARM TrustZone
"""
import hashlib
import time
import json


class TEEAttestation:
    TEE_VERSION = "dronesync-tee-v1"
    HARDWARE_ID = "SGX_SIM_001"
    _global_count = 0

    def __init__(self):
        self.attestation_count = 0

    def attest_mission(self, mission_id: str, trajectory_hash: str,
                        score: int) -> dict:
        TEEAttestation._global_count += 1
        self.attestation_count += 1
        timestamp = int(time.time())
        payload = {
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "timestamp": timestamp,
            "tee_version": self.TEE_VERSION,
            "hardware_id": self.HARDWARE_ID
        }
        attestation_hash = self._sign_payload(payload)
        return {
            "attestation_id": "ATT_" + str(TEEAttestation._global_count).zfill(6),
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "timestamp": timestamp,
            "tee_version": self.TEE_VERSION,
            "hardware_id": self.HARDWARE_ID,
            "attestation_hash": attestation_hash,
            "status": "VERIFIED"
        }

    def verify_attestation(self, attestation: dict) -> bool:
        payload = {
            "mission_id": attestation["mission_id"],
            "trajectory_hash": attestation.get("trajectory_hash", ""),
            "score": attestation["score"],
            "timestamp": attestation["timestamp"],
            "tee_version": attestation["tee_version"],
            "hardware_id": attestation["hardware_id"]
        }
        expected_hash = self._sign_payload(payload)
        return attestation["attestation_hash"] == expected_hash

    def _sign_payload(self, payload: dict) -> str:
        data = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()


class ProofChain:
    """
    Непрерывная цепочка доказательств PoPW.
    trajectory_hash  = SHA256(positions)
    sensor_hash      = SHA256(sensor_data + trajectory_hash)
    score_root       = SHA256(score + sensor_hash + trajectory_hash + mission_id)
    popw_hash        = SHA256(score_root + validator_wallet + timestamp)
    """

    @staticmethod
    def build(mission_id: str, positions: list, sensor_data: dict,
              score: int, validator_wallet: str) -> dict:
        timestamp = int(time.time())
        trajectory_hash = hashlib.sha256(
            json.dumps(positions, sort_keys=True).encode()
        ).hexdigest()
        sensor_hash = hashlib.sha256(
            json.dumps({"data": sensor_data,
                        "trajectory_hash": trajectory_hash},
                       sort_keys=True).encode()
        ).hexdigest()
        score_root = hashlib.sha256(
            json.dumps({"mission_id": mission_id,
                        "score": score,
                        "sensor_hash": sensor_hash,
                        "trajectory_hash": trajectory_hash},
                       sort_keys=True).encode()
        ).hexdigest()
        popw_hash = hashlib.sha256(
            json.dumps({"score_root": score_root,
                        "validator_wallet": validator_wallet,
                        "timestamp": timestamp},
                       sort_keys=True).encode()
        ).hexdigest()
        return {
            "mission_id": mission_id,
            "timestamp": timestamp,
            "trajectory_hash": trajectory_hash,
            "sensor_hash": sensor_hash,
            "score_root": score_root,
            "popw_hash": popw_hash,
            "validator_wallet": validator_wallet,
            "chain_valid": True
        }

    @staticmethod
    def verify(chain: dict, positions: list, sensor_data: dict,
               score: int) -> dict:
        recomputed_traj = hashlib.sha256(
            json.dumps(positions, sort_keys=True).encode()
        ).hexdigest()
        recomputed_sensor = hashlib.sha256(
            json.dumps({"data": sensor_data,
                        "trajectory_hash": recomputed_traj},
                       sort_keys=True).encode()
        ).hexdigest()
        recomputed_root = hashlib.sha256(
            json.dumps({"mission_id": chain["mission_id"],
                        "score": score,
                        "sensor_hash": recomputed_sensor,
                        "trajectory_hash": recomputed_traj},
                       sort_keys=True).encode()
        ).hexdigest()
        traj_ok = recomputed_traj == chain["trajectory_hash"]
        sensor_ok = recomputed_sensor == chain["sensor_hash"]
        root_ok = recomputed_root == chain["score_root"]
        return {
            "trajectory_ok": traj_ok,
            "sensor_ok": sensor_ok,
            "score_root_ok": root_ok,
            "chain_intact": traj_ok and sensor_ok and root_ok,
            "status": "VERIFIED" if (traj_ok and sensor_ok and root_ok) else "TAMPERED"
        }


class PoPWRecord:
    def __init__(self):
        self.tee = TEEAttestation()

    def create_record(self, mission_id: str, trajectory: object,
                       sensor_data_or_score=None, score: int = 0,
                       validator_wallet: str = "unknown") -> dict:
        if isinstance(sensor_data_or_score, int):
            score = sensor_data_or_score
            sensor_data = {}
        else:
            sensor_data = sensor_data_or_score or {}
        chain = ProofChain.build(
            mission_id=mission_id,
            positions=trajectory.positions,
            sensor_data=sensor_data,
            score=score,
            validator_wallet=validator_wallet
        )
        attestation = self.tee.attest_mission(
            mission_id=mission_id,
            trajectory_hash=chain["trajectory_hash"],
            score=score
        )
        return {
            "popw_version": "2.0",
            "mission_id": mission_id,
            "trajectory_hash": chain["trajectory_hash"],
            "sensor_hash": chain["sensor_hash"],
            "score_root": chain["score_root"],
            "popw_hash": chain["popw_hash"],
            "score": score,
            "attestation": attestation,
            "chain": chain,
            "on_chain_ready": True
        }

    def verify_record(self, record: dict, trajectory: object,
                       sensor_data: dict, score: int) -> dict:
        tee_ok = self.tee.verify_attestation(record["attestation"])
        chain_result = ProofChain.verify(
            chain=record["chain"],
            positions=trajectory.positions,
            sensor_data=sensor_data,
            score=score
        )
        overall = tee_ok and chain_result["chain_intact"]
        return {
            "tee_valid": tee_ok,
            "chain_valid": chain_result["chain_intact"],
            "trajectory_ok": chain_result["trajectory_ok"],
            "sensor_ok": chain_result["sensor_ok"],
            "score_root_ok": chain_result["score_root_ok"],
            "overall_valid": overall,
            "status": "VERIFIED" if overall else "REJECTED"
        }

    def format_for_chain(self, record: dict) -> str:
        return (
            "POPW|" +
            record["mission_id"] + "|" +
            record["trajectory_hash"][:16] + "|" +
            str(record["score"]) + "|" +
            record["attestation"]["attestation_hash"][:16]
        )
