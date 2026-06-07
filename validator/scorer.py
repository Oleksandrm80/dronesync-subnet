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
            safety = self._score_safety(trajectory.positions, sensor_data if isinstance(sensor_data, list) else [])
            return round(safety * 100)

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
