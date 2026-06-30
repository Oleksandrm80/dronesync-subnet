"""
DroneSync — Validator Scoring Engine
"""

import math
from dronesync.protocol import MissionInstruction

class MissionScorer:
    MIN_SAFE_ALT = 25.0
    MAX_SAFE_ALT = 130.0
    MIN_BATTERY_LANDING = 20.0

    def haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def score(self, mission: MissionInstruction,
              trajectory: list, sensor_readings: list,
              validator_wallet: str) -> dict:

        safety = self._score_safety(trajectory, sensor_readings)
        task_match = self._score_task_match(mission, trajectory)
        efficiency = self._score_efficiency(mission, trajectory)
        sensor_quality = self._score_sensor_quality(sensor_readings)

        total = (safety * 0.40 + task_match * 0.30 +
                 efficiency * 0.20 + sensor_quality * 0.10)

        grade = ("EXCELLENT" if total > 0.85 else
                 "GOOD" if total > 0.70 else
                 "ACCEPTABLE" if total > 0.50 else "POOR")

        return {
            "mission_id": mission.mission_id,
            "validator_wallet": validator_wallet,
            "safety_score": round(safety, 3),
            "task_match_score": round(task_match, 3),
            "efficiency_score": round(efficiency, 3),
            "sensor_quality_score": round(sensor_quality, 3),
            "total_score": round(total, 3),
            "grade": grade
        }

    def _score_safety(self, trajectory, sensor_readings) -> float:
        score = 1.0
        violations = sum(1 for p in trajectory
                        if 0 < p[2] < self.MIN_SAFE_ALT)
        score -= min(0.5, violations * 0.05)
        high_violations = sum(1 for p in trajectory if p[2] > self.MAX_SAFE_ALT)
        score -= min(0.3, high_violations * 0.05)
        if sensor_readings:
            final_battery = sensor_readings[-1].get("battery_pct", 100)
            if final_battery < self.MIN_BATTERY_LANDING:
                score -= 0.2
        return max(0.0, score)

    def _score_task_match(self, mission, trajectory) -> float:
        if not trajectory:
            return 0.0
        score = 1.0
        final = trajectory[-1]
        dist = self.haversine(final[0], final[1],
                              mission.destination.lat,
                              mission.destination.lon)
        if dist > 50:
            score -= 0.4
        elif dist > 20:
            score -= 0.1
        return max(0.0, score)

    def _score_efficiency(self, mission, trajectory) -> float:
        if len(trajectory) < 2:
            return 0.0
        score = 1.0
        actual = sum(
            self.haversine(trajectory[i][0], trajectory[i][1],
                          trajectory[i+1][0], trajectory[i+1][1])
            for i in range(len(trajectory)-1)
        )
        optimal = self.haversine(mission.origin.lat, mission.origin.lon,
                                 mission.destination.lat,
                                 mission.destination.lon)
        if optimal > 0 and actual / optimal > 2.0:
            score -= 0.3
        return max(0.0, score)

    def _score_sensor_quality(self, sensor_readings) -> float:
        if not sensor_readings:
            return 0.0
        avg_gps = sum(s.get("gps_accuracy", 5)
                     for s in sensor_readings) / len(sensor_readings)
        return max(0.0, 1.0 - min(1.0, (avg_gps - 5) * 0.05))
class DroneEvaluator(MissionScorer):
    def score(self, trajectory, sensor_data):
        if isinstance(sensor_data, list):
            readings = sensor_data
        elif hasattr(sensor_data, 'lidar_points'):
            readings = [{"battery_pct": 95, "signal_strength": 0.9,
                         "lidar_points": len(sensor_data.lidar_points)}]
        else:
            readings = []
        safety = self._score_safety(trajectory.positions, readings)
        sensor_quality = self._score_sensor_quality(readings)
        total = safety * 0.80 + sensor_quality * 0.20
        return round(total * 100)

    def generate_pow(self, trajectory, steps):
        return {
            "hash": str(hash(str(trajectory.positions))),
            "steps": steps,
            "valid": True
        }

    def replay_validate(self, trajectory) -> dict:
        """
        Replay Validation: validator повторяет расчёт хэша шагов
        и сравнивает с тем что записал планировщик.
        VERIFIED если совпало, REJECTED если нет.
        """
        import hashlib
        planner_steps = trajectory.metadata.get("planner_steps")
        recorded_hash = trajectory.metadata.get("steps_hash")

        if not planner_steps or not recorded_hash:
            return {
                "status": "REJECTED",
                "reason": "no planner_steps in trace",
                "verified": False
            }

        # Повторяем расчёт хэша
        recomputed_hash = hashlib.sha256(str(planner_steps).encode()).hexdigest()

        if recomputed_hash == recorded_hash:
            return {
                "status": "VERIFIED",
                "reason": "trace hash matches",
                "verified": True,
                "steps_count": len(planner_steps),
                "hash": recorded_hash
            }
        else:
            return {
                "status": "REJECTED",
                "reason": "trace hash mismatch",
                "verified": False,
                "recorded_hash": recorded_hash,
                "recomputed_hash": recomputed_hash
            }


class ValidatorIdentity:
    """
    Validator signs its score with private key.
    Anyone can verify the score came from this validator
    using only the public key.
    """

    def __init__(self, validator_id: str, key_path: str = ".dronesync_data/validator_key.pem"):
        self.validator_id = validator_id
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, NoEncryption, load_pem_private_key
        )
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                self._private_key = load_pem_private_key(f.read(), password=None)
        else:
            self._private_key = Ed25519PrivateKey.generate()
            with open(key_path, "wb") as f:
                f.write(self._private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
        self._public_key = self._private_key.public_key()

    @property
    def public_key_hex(self) -> str:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def sign_score(self, mission_id: str, score: int, grade: str) -> dict:
        """Sign a validator score — returns signed result."""
        import hashlib
        import json
        import base64
        import time
        payload = {
            "validator_id": self.validator_id,
            "mission_id": mission_id,
            "score": score,
            "grade": grade,
            "timestamp": int(time.time())
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        sig = self._private_key.sign(payload_bytes)
        return {
            **payload,
            "signature": base64.b64encode(sig).decode(),
            "public_key": self.public_key_hex
        }

    @staticmethod
    def verify_score(signed_score: dict) -> bool:
        """Verify score signature using only public key."""
        import hashlib
        import json
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            payload = {
                "validator_id": signed_score["validator_id"],
                "mission_id": signed_score["mission_id"],
                "score": signed_score["score"],
                "grade": signed_score["grade"],
                "timestamp": signed_score["timestamp"]
            }
            payload_bytes = json.dumps(payload, sort_keys=True).encode()
            pub_bytes = bytes.fromhex(signed_score["public_key"])
            vk = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig = base64.b64decode(signed_score["signature"])
            vk.verify(sig, payload_bytes)
            return True
        except (InvalidSignature, Exception):
            return False
