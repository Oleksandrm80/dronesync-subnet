"""
DroneSync - Drone Reputation Score
Each drone accumulates an on-chain reputation based on mission history.
Higher reputation = access to better missions and higher token rewards.
"""
import hashlib
import time


class DroneReputation:
    """
    On-chain reputation system for individual drones.
    Score is deterministic and tamper-evident — built from mission records.
    """

    BASE_SCORE = 50
    MAX_SCORE = 100
    MIN_SCORE = 0

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.missions = []
        self.score = self.BASE_SCORE
        self.tier = "ROOKIE"

    def record_mission(self, mission_id: str, score: int,
                       mission_safe: bool, battery_used_pct: float):
        """Record completed mission and update reputation."""
        record = {
            "mission_id": mission_id,
            "score": score,
            "mission_safe": mission_safe,
            "battery_used_pct": battery_used_pct,
            "timestamp": int(time.time())
        }
        self.missions.append(record)
        self._update_score(score, mission_safe)
        return record

    def _update_score(self, mission_score: int, mission_safe: bool):
        """Adjust reputation based on mission outcome."""
        if not mission_safe:
            self.score = max(self.MIN_SCORE, self.score - 10)
            self.tier = self._compute_tier()
            return
        if mission_score >= 95:
            self.score = min(self.MAX_SCORE, self.score + 3)
        elif mission_score >= 80:
            self.score = min(self.MAX_SCORE, self.score + 1)
        elif mission_score < 60:
            self.score = max(self.MIN_SCORE, self.score - 3)

        self.tier = self._compute_tier()

    def _compute_tier(self) -> str:
        if self.score >= 90:
            return "ELITE"
        elif self.score >= 75:
            return "TRUSTED"
        elif self.score >= 50:
            return "ACTIVE"
        else:
            return "ROOKIE"

    def get_status(self) -> dict:
        """Return current reputation status."""
        reputation_hash = hashlib.sha256(
            str(self.missions).encode()
        ).hexdigest()
        return {
            "drone_id": self.drone_id,
            "reputation_score": self.score,
            "tier": self.tier,
            "total_missions": len(self.missions),
            "reputation_hash": reputation_hash,
            "on_chain_ready": True
        }
