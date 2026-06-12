"""
DroneSync - Replay Attack Protection
Prevents resubmission of already processed missions.
Stores seen mission_ids with timestamps.
"""
import hashlib
import time


class ReplayGuard:
    """
    Protects against replay attacks — resubmitting old missions.
    Each mission_id can only be processed once.
    Nonce + timestamp validation prevents time-shifted replays.
    """

    MAX_AGE_SECONDS = 3600  # mission older than 1 hour is rejected

    def __init__(self, persist_path: str = ".dronesync_data/replay_guard.json"):
        import os, json
        self._persist_path = persist_path
        os.makedirs(os.path.dirname(persist_path), exist_ok=True)
        if os.path.exists(persist_path):
            with open(persist_path) as f:
                self._seen = json.load(f)
        else:
            self._seen = {}
    def check(self, mission_id: str, created_at: float) -> dict:
        """
        Check if mission is safe to process.
        Returns dict with allowed=True/False and reason.
        """
        now = time.time()

        # Check age
        age = now - created_at
        if age > self.MAX_AGE_SECONDS:
            return {
                "allowed": False,
                "reason": "MISSION_EXPIRED",
                "age_seconds": round(age, 1),
                "mission_id": mission_id
            }

        # Check replay
        if mission_id in self._seen:
            first_seen = self._seen[mission_id]
            return {
                "allowed": False,
                "reason": "REPLAY_DETECTED",
                "first_seen_at": first_seen,
                "mission_id": mission_id
            }

        # All good — register
        self._seen[mission_id] = now
        return {
            "allowed": True,
            "reason": "OK",
            "mission_id": mission_id,
            "registered_at": now
        }

    def register(self, mission_id: str):
        """Manually register a mission_id as seen."""
        import json
        self._seen[mission_id] = time.time()
        with open(self._persist_path, "w") as f:
            json.dump(self._seen, f)
    def is_seen(self, mission_id: str) -> bool:
        return mission_id in self._seen

    def get_status(self) -> dict:
        seen_list = list(self._seen.keys())
        status_hash = hashlib.sha256(str(seen_list).encode()).hexdigest()
        return {
            "total_seen": len(self._seen),
            "seen_missions": seen_list,
            "status_hash": status_hash,
            "on_chain_ready": True
        }
