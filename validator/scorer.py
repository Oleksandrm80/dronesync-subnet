"""
DroneSync — Validator Scoring Engine
"""

import math
from dronesync.protocol import MissionInstruction, ValidatorScore


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
                        if 2.0 < p.get("alt", 0) < self.MIN_SAFE_ALT)
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
        dist = self.haversine(final["lat"], final["lon"],
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
            self.haversine(trajectory[i]["lat"], trajectory[i]["lon"],
                          trajectory[i+1]["lat"], trajectory[i+1]["lon"])
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