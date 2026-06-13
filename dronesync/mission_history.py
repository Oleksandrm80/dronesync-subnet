"""
DroneSync - Mission History Module
Tracks and analyzes all completed missions
"""
import hashlib
import json
import time
from typing import Any


class MissionHistory:
    def __init__(self) -> None:
        self.missions: list[dict[str, Any]] = []
        self._chain_hash: str = "0" * 64

    def add(
        self,
        mission_id: str,
        score: int,
        duration_s: float,
        battery_used: float,
        weather: str = "CLEAR",
        security: str = "SECURE",
    ) -> None:
        entry: dict[str, Any] = {
            "mission_id": mission_id,
            "score": score,
            "duration_s": duration_s,
            "battery_used_pct": battery_used,
            "weather": weather,
            "security": security,
            "timestamp": int(time.time()),
            "prev_hash": self._chain_hash,
        }
        entry_str = json.dumps({k: v for k, v in entry.items()}, sort_keys=True)
        entry["entry_hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
        self._chain_hash = entry["entry_hash"]
        self.missions.append(entry)

    def verify_chain(self) -> bool:
        prev: str = "0" * 64
        for entry in self.missions:
            check = {k: v for k, v in entry.items() if k != "entry_hash"}
            check["prev_hash"] = prev
            expected = hashlib.sha256(
                json.dumps(check, sort_keys=True).encode()
            ).hexdigest()
            if entry["entry_hash"] != expected:
                return False
            prev = entry["entry_hash"]
        return True

    def stats(self) -> dict[str, Any]:
        if not self.missions:
            return {"total_missions": 0, "chain_valid": True}
        scores = [m["score"] for m in self.missions]
        return {
            "total_missions": len(self.missions),
            "avg_score": round(sum(scores) / len(scores), 1),
            "max_score": max(scores),
            "min_score": min(scores),
            "success_rate_pct": round(
                len([s for s in scores if s >= 70]) / len(scores) * 100, 1
            ),
            "total_flights": len(self.missions),
            "chain_valid": self.verify_chain(),
            "chain_root": self.missions[0]["entry_hash"] if self.missions else None,
        }

    def last(self, n: int = 3) -> list[dict[str, Any]]:
        return self.missions[-n:]
