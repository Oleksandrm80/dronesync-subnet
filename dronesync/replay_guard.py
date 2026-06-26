"""
DroneSync - Replay Attack Protection
Prevents resubmission of already processed missions.
Uses SQLite for thread-safe, crash-resistant storage.
"""
import hashlib
import time
import threading
import sqlite3
import os


class ReplayGuard:
    MAX_AGE_SECONDS = 3600

    def __init__(self, persist_path: str = ".dronesync_data/replay_guard.json"):
        db_path = persist_path if persist_path.endswith(".db") else persist_path.replace(".json", ".db") if persist_path.endswith(".json") else persist_path + ".db"
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS seen_missions (
                mission_id TEXT PRIMARY KEY,
                first_seen_at REAL
            )
        """)
        self._db.commit()

    def check(self, mission_id: str, created_at: float) -> dict:
        now = time.time()

        if created_at > now + 60:
            return {
                "allowed": False,
                "reason": "FUTURE_TIMESTAMP",
                "mission_id": mission_id
            }

        age = now - created_at
        if age > self.MAX_AGE_SECONDS:
            return {
                "allowed": False,
                "reason": "MISSION_EXPIRED",
                "age_seconds": round(age, 1),
                "mission_id": mission_id
            }

        with self._lock:
            row = self._db.execute(
                "SELECT first_seen_at FROM seen_missions WHERE mission_id=?",
                (mission_id,)
            ).fetchone()

            if row:
                return {
                    "allowed": False,
                    "reason": "REPLAY_DETECTED",
                    "first_seen_at": row[0],
                    "mission_id": mission_id
                }

            self._db.execute(
                "INSERT INTO seen_missions VALUES (?, ?)",
                (mission_id, now)
            )
            self._db.commit()

        return {
            "allowed": True,
            "reason": "OK",
            "mission_id": mission_id,
            "registered_at": now
        }

    def register(self, mission_id: str):
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO seen_missions VALUES (?, ?)",
                (mission_id, time.time())
            )
            self._db.commit()

    def is_seen(self, mission_id: str) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM seen_missions WHERE mission_id=?",
                (mission_id,)
            ).fetchone()
            return row is not None

    def get_status(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT mission_id FROM seen_missions").fetchall()
            seen_list = [r[0] for r in rows]
        status_hash = hashlib.sha256(str(seen_list).encode()).hexdigest()
        return {
            "total_seen": len(seen_list),
            "seen_missions": seen_list,
            "status_hash": status_hash,
            "on_chain_ready": True
        }
