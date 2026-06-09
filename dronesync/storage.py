"""
DroneSync - Persistent Storage
Saves drone state between runs — reputation, memory, mission history.
Without this, a 24/7 node loses all data on restart.
"""
import json
import os
import time


STORAGE_DIR = ".dronesync_data"


class DroneStorage:
    """
    File-based persistent storage for drone state.
    Each drone has its own JSON file — simple, portable, auditable.
    """

    def __init__(self, drone_id: str, storage_dir: str = STORAGE_DIR):
        self.drone_id = drone_id
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.path = os.path.join(storage_dir, drone_id + ".json")

    def save(self, data: dict):
        """Save drone state to disk."""
        data = {**data, "drone_id": self.drone_id, "last_saved": int(time.time())}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> dict:
        """Load drone state from disk. Returns empty dict if no data yet."""
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def append_mission(self, mission_record: dict):
        """Append a mission to drone's history without overwriting other data."""
        state = self.load()
        if "missions" not in state:
            state["missions"] = []
        state["missions"].append(mission_record)
        # keep last 1000 missions
        state["missions"] = state["missions"][-1000:]
        self.save(state)

    def get_missions(self) -> list:
        return self.load().get("missions", [])

    def update_reputation(self, score: int, tier: str):
        state = self.load()
        state["reputation_score"] = score
        state["reputation_tier"] = tier
        self.save(state)

    def get_reputation(self) -> dict:
        state = self.load()
        return {
            "score": state.get("reputation_score", 50),
            "tier": state.get("reputation_tier", "ROOKIE")
        }

    def clear(self):
        """Reset drone state — for testing."""
        if os.path.exists(self.path):
            os.remove(self.path)
