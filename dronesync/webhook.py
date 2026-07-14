"""
DroneSync Webhook — уведомления клиентов о завершении миссий.
"""
import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".dronesync" / "webhooks.db"


class WebhookDB:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(DB_PATH))
            self._local.conn.execute("""
                CREATE TABLE IF NOT EXISTS webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    secret TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at REAL
                )
            """)
            self._local.conn.commit()
        return self._local.conn

    def register(self, client_id: str, url: str, secret: str) -> dict:
        conn = self._conn()
        conn.execute(
            "INSERT INTO webhooks (client_id, url, secret, active, created_at) VALUES (?,?,?,1,?)",
            (client_id, url, secret, time.time())
        )
        conn.commit()
        return {"status": "registered", "client_id": client_id, "url": url}

    def get_webhooks(self, client_id: str) -> list:
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, url, secret FROM webhooks WHERE client_id=? AND active=1",
            (client_id,)
        ).fetchall()
        return [{"id": r[0], "url": r[1], "secret": r[2]} for r in rows]

    def deactivate(self, webhook_id: int):
        conn = self._conn()
        conn.execute("UPDATE webhooks SET active=0 WHERE id=?", (webhook_id,))
        conn.commit()


_db: Optional[WebhookDB] = None


def get_webhook_db() -> WebhookDB:
    global _db
    if _db is None:
        _db = WebhookDB()
    return _db


def _sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def send_webhook(client_id: str, event: str, data: dict):
    """Отправляет webhook уведомление всем зарегистрированным URL клиента."""
    hooks = get_webhook_db().get_webhooks(client_id)
    if not hooks:
        return
    payload = json.dumps({"event": event, "data": data, "timestamp": time.time()}).encode()
    for hook in hooks:
        def _send(url=hook["url"], secret=hook["secret"]):
            try:
                sig = _sign_payload(secret, payload)
                with httpx.Client(timeout=10) as client:
                    client.post(url, content=payload, headers={
                        "Content-Type": "application/json",
                        "X-DroneSync-Signature": sig,
                    })
                logger.info("[Webhook] Sent %s to %s", event, url)
            except Exception as e:
                logger.warning("[Webhook] Failed %s: %s", url, e)
        threading.Thread(target=_send, daemon=True).start()
