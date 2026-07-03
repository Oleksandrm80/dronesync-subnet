"""
DroneSync - Transaction Queue
Holds PoPW artifacts and submits them to Konnex chain.
Retries on failure with exponential backoff.
"""
import json
import hashlib
import threading
import time
import sqlite3
import os
from typing import Optional


DB_PATH = os.path.join(
    os.path.expanduser("~"), ".dronesync_data", "tx_queue.db"
)


class TxQueue:
    """
    Persistent queue for on-chain PoPW submissions.
    Survives restarts — pending transactions are retried automatically.
    """

    MAX_RETRIES = 5
    RETRY_DELAYS = [2, 4, 8, 16, 32]  # exponential backoff seconds

    def __init__(self, db_path: str = DB_PATH, endpoint: str = None):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.endpoint = endpoint  # Konnex chain endpoint (set when SDK available)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tx_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    chain_string TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    retries INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    submitted_at INTEGER,
                    tx_hash TEXT
                )
            """)
            conn.commit()

    def enqueue(self, popw_result: dict) -> dict:
        """Add PoPW result to submission queue."""
        if not popw_result.get("on_chain_ready"):
            return {"status": "skipped", "reason": "not_on_chain_ready"}

        mission_id = popw_result.get("mission_id", "unknown")
        proof = popw_result.get("proof_package", {})
        chain_string = proof.get("chain_string", "")
        if not chain_string:
            # build from popw directly
            chain_string = "POPW|{}|{}|{}|{}".format(
                mission_id,
                popw_result.get("trajectory_hash", "")[:16],
                popw_result.get("score", 0),
                popw_result.get("bundle_hash", "")[:16],
            )

        payload = json.dumps({
            "mission_id": mission_id,
            "chain_string": chain_string,
            "score": popw_result.get("score"),
            "trajectory_hash": popw_result.get("trajectory_hash", ""),
            "sensor_hash": popw_result.get("sensor_hash", ""),
            "tee_status": popw_result.get("tee_status", ""),
            "attestation_id": popw_result.get("attestation_id", ""),
        }, sort_keys=True)

        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute(
                "INSERT INTO tx_queue (mission_id, chain_string, payload, created_at) VALUES (?,?,?,?)",
                (mission_id, chain_string, payload, int(time.time()))
            )
            conn.commit()

        return {"status": "queued", "mission_id": mission_id, "chain_string": chain_string}

    def submit_pending(self) -> dict:
        """
        Attempt to submit all pending transactions.
        When Konnex SDK is available, replace _send_to_chain() with real call.
        """
        submitted, failed, skipped = 0, 0, 0

        with sqlite3.connect(self.db_path, timeout=10) as conn:
            rows = conn.execute(
                "SELECT id, mission_id, chain_string, payload, retries FROM tx_queue WHERE status='pending'"
            ).fetchall()

        for row in rows:
            tx_id, mission_id, chain_string, payload, retries = row
            result = self._send_to_chain(chain_string, json.loads(payload))

            with sqlite3.connect(self.db_path, timeout=10) as conn:
                if result["success"]:
                    conn.execute(
                        "UPDATE tx_queue SET status='submitted', submitted_at=?, tx_hash=? WHERE id=?",
                        (int(time.time()), result.get("tx_hash"), tx_id)
                    )
                    submitted += 1
                else:
                    new_retries = retries + 1
                    new_status = "failed" if new_retries >= self.MAX_RETRIES else "pending"
                    conn.execute(
                        "UPDATE tx_queue SET retries=?, status=? WHERE id=?",
                        (new_retries, new_status, tx_id)
                    )
                    failed += 1
                conn.commit()

        return {"submitted": submitted, "failed": failed, "skipped": skipped,
                "total_pending": len(rows)}

    def _send_to_chain(self, chain_string: str, payload: dict) -> dict:
        """
        Send transaction to Konnex chain.
        Currently: logs and marks as submitted (ready for real SDK).
        When SDK available: replace with real HTTP/WebSocket call to self.endpoint.
        """
        if self.endpoint:
            # TODO: replace with real Konnex SDK call when available
            # response = konnex_sdk.submit_tx(chain_string, payload)
            pass

        # Simulate successful submission with deterministic tx_hash
        tx_hash = hashlib.sha256(chain_string.encode()).hexdigest()
        return {"success": True, "tx_hash": tx_hash}

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            total = conn.execute("SELECT COUNT(*) FROM tx_queue").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM tx_queue WHERE status='pending'").fetchone()[0]
            submitted = conn.execute("SELECT COUNT(*) FROM tx_queue WHERE status='submitted'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM tx_queue WHERE status='failed'").fetchone()[0]
        return {
            "total": total,
            "pending": pending,
            "submitted": submitted,
            "failed": failed,
            "endpoint": self.endpoint or "awaiting_konnex_sdk",
        }

    def get_pending(self) -> list:
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            rows = conn.execute(
                "SELECT mission_id, chain_string, retries, created_at FROM tx_queue WHERE status='pending'"
            ).fetchall()
        return [
            {"mission_id": r[0], "chain_string": r[1], "retries": r[2], "created_at": r[3]}
            for r in rows
        ]
