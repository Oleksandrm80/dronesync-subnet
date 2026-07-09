"""
dronesync/auth.py
Multi-client authentication and authorization for DroneSync API.

Client types:
  - admin        : full access
  - fleet_manager: manage drones, run missions, view stats
  - operator     : run missions, view own data
  - validator    : verify PoPW, vote in consensus
  - customer     : track delivery status only
"""

import sqlite3
import secrets
import hashlib
import time
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DRONESYNC_AUTH_DB", os.path.expanduser("~/.dronesync/auth.db"))

# Права доступа по типу клиента
ROLE_PERMISSIONS = {
    "admin":         {"mission:run", "mission:read", "fleet:manage", "validator:vote", "admin:all"},
    "fleet_manager": {"mission:run", "mission:read", "fleet:manage"},
    "operator":      {"mission:run", "mission:read"},
    "validator":     {"mission:read", "validator:vote"},
    "customer":      {"delivery:track"},
}


@dataclass
class Client:
    client_id: str
    name: str
    role: str
    api_key_hash: str
    active: bool
    created_at: float
    last_seen: float
    request_count: int
    permissions: set


class AuthDB:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                client_id     TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                role          TEXT NOT NULL,
                api_key_hash  TEXT UNIQUE NOT NULL,
                active        INTEGER DEFAULT 1,
                created_at    REAL NOT NULL,
                last_seen     REAL DEFAULT 0,
                request_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS request_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   TEXT NOT NULL,
                endpoint    TEXT NOT NULL,
                method      TEXT NOT NULL,
                status_code INTEGER,
                timestamp   REAL NOT NULL
            );
        """)
        self._db.commit()

    def create_client(self, name: str, role: str) -> dict:
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Unknown role: {role}. Choose from: {list(ROLE_PERMISSIONS.keys())}")

        api_key = "ds_" + secrets.token_hex(24)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        client_id = "client_" + secrets.token_hex(8)
        now = time.time()

        self._db.execute(
            "INSERT INTO clients VALUES (?, ?, ?, ?, 1, ?, 0, 0)",
            (client_id, name, role, api_key_hash, now)
        )
        self._db.commit()

        logger.info("[Auth] Created client: %s (%s) role=%s", name, client_id, role)
        return {
            "client_id": client_id,
            "name": name,
            "role": role,
            "api_key": api_key,  # показывается только один раз при создании
            "permissions": list(ROLE_PERMISSIONS[role]),
            "created_at": now,
        }

    def verify_key(self, api_key: str) -> Optional[Client]:
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        row = self._db.execute(
            "SELECT client_id, name, role, api_key_hash, active, created_at, last_seen, request_count FROM clients WHERE api_key_hash=?",
            (api_key_hash,)
        ).fetchone()

        if not row:
            return None

        client_id, name, role, stored_hash, active, created_at, last_seen, request_count = row

        if not active:
            logger.warning("[Auth] Inactive client tried to authenticate: %s", client_id)
            return None

        # Обновляем last_seen и счётчик запросов
        self._db.execute(
            "UPDATE clients SET last_seen=?, request_count=request_count+1 WHERE client_id=?",
            (time.time(), client_id)
        )
        self._db.commit()

        return Client(
            client_id=client_id,
            name=name,
            role=role,
            api_key_hash=stored_hash,
            active=bool(active),
            created_at=created_at,
            last_seen=last_seen,
            request_count=request_count,
            permissions=ROLE_PERMISSIONS.get(role, set()),
        )

    def revoke_client(self, client_id: str) -> bool:
        self._db.execute(
            "UPDATE clients SET active=0 WHERE client_id=?",
            (client_id,)
        )
        self._db.commit()
        logger.info("[Auth] Revoked client: %s", client_id)
        return True

    def log_request(self, client_id: str, endpoint: str, method: str, status_code: int):
        self._db.execute(
            "INSERT INTO request_log (client_id, endpoint, method, status_code, timestamp) VALUES (?, ?, ?, ?, ?)",
            (client_id, endpoint, method, status_code, time.time())
        )
        self._db.commit()

    def list_clients(self) -> list:
        rows = self._db.execute(
            "SELECT client_id, name, role, active, created_at, last_seen, request_count FROM clients ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "client_id": r[0],
                "name": r[1],
                "role": r[2],
                "active": bool(r[3]),
                "created_at": r[4],
                "last_seen": r[5],
                "request_count": r[6],
                "permissions": list(ROLE_PERMISSIONS.get(r[2], set())),
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        total = self._db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        active = self._db.execute("SELECT COUNT(*) FROM clients WHERE active=1").fetchone()[0]
        requests = self._db.execute("SELECT COUNT(*) FROM request_log").fetchone()[0]
        return {"total_clients": total, "active_clients": active, "total_requests": requests}


# Глобальный экземпляр
_auth_db: Optional[AuthDB] = None

def get_auth_db() -> AuthDB:
    global _auth_db
    if _auth_db is None:
        _auth_db = AuthDB()
    return _auth_db
