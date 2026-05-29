"""
DroneSync - Mission History Module
Tracks and analyzes all completed missions
"""
import json
import time


class MissionHistory:
    def __init__(self):
        self.missions = []

    def add(self, mission_id: str, score: int,
            duration_s: float, battery_used: float,
            weather: str = "CLEAR", security: str = "SECURE"):
        self.missions.append({
            "mission_id": mission_id,
            "score": score,
            "duration_s": duration_s,
            "battery_used_pct": battery_used,
            "weather": weather,
            "security": security,
            "timestamp": int(time.time())
        })

    def stats(self) -> dict:
        if not self.missions:
            return {"total": 0}
        scores = [m["score"] for m in self.missions]
        return {
            "total_missions": len(self.missions),
            "avg_score": round(sum(scores) / len(scores), 1),
            "max_score": max(scores),
            "min_score": min(scores),
            "success_rate_pct": round(
                len([s for s in scores if s >= 70]) / len(scores) * 100, 1
            ),
            "total_flights": len(self.missions)
        }

    def last(self, n: int = 3) -> list:
        return self.missions[-n:]