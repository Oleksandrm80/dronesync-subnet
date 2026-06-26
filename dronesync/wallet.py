"""
DroneSync - Wallet & Key Management
"""
import hashlib
import json
import os
import base64
import uuid
import time
import threading
import sqlite3


def _derive_key(password: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"dronesync_salt_v1", 100_000)


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    key_cycle = (key * (len(data) // len(key) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, key_cycle))


class Wallet:
    DEFAULT_PATH = ".dronesync_data/wallet.enc"

    def __init__(self, path: str = DEFAULT_PATH):
        self._path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def save(self, secret_key: str, password: str):
        key = _derive_key(password)
        encrypted = _xor_encrypt(secret_key.encode(), key)
        payload = {
            "data": base64.b64encode(encrypted).decode(),
            "checksum": hashlib.sha256(secret_key.encode()).hexdigest()[:16],
        }
        with open(self._path, "w") as f:
            json.dump(payload, f)

    def load(self, password: str) -> str:
        if not os.path.exists(self._path):
            raise FileNotFoundError(f"Wallet not found: {self._path}")
        with open(self._path) as f:
            payload = json.load(f)
        key = _derive_key(password)
        encrypted = base64.b64decode(payload["data"])
        secret_key = _xor_encrypt(encrypted, key).decode()
        checksum = hashlib.sha256(secret_key.encode()).hexdigest()[:16]
        if checksum != payload["checksum"]:
            raise ValueError("Wrong password or corrupted wallet")
        return secret_key

    def exists(self) -> bool:
        return os.path.exists(self._path)


class Transaction:
    def __init__(self, sender: str, receiver: str, amount_knx: float, mission_id: str = "", reason: str = "", balance_after: float = 0.0):
        self.tx_id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.amount_knx = amount_knx
        self.amount = abs(amount_knx)
        self.mission_id = mission_id
        self.reason = reason
        self.balance_after = balance_after
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "amount_knx": self.amount_knx,
            "mission_id": self.mission_id,
            "reason": self.reason,
            "balance_after": self.balance_after,
            "timestamp": self.timestamp,
        }


class MinerWallet:
    def __init__(self, wallet_id: str, persist_path: str = ".dronesync_data/miner_wallet.json"):
        self.wallet_id = wallet_id
        self._path = persist_path.replace(".json", ".db")
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._db = sqlite3.connect(self._path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                sender TEXT,
                receiver TEXT,
                amount_knx REAL,
                mission_id TEXT,
                reason TEXT,
                balance_after REAL,
                timestamp REAL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS wallet (
                wallet_id TEXT PRIMARY KEY,
                balance REAL
            )
        """)
        self._db.execute(
            "INSERT OR IGNORE INTO wallet VALUES (?, ?)", (wallet_id, 0.0)
        )
        self._db.commit()

    def _get_balance(self) -> float:
        row = self._db.execute(
            "SELECT balance FROM wallet WHERE wallet_id=?", (self.wallet_id,)
        ).fetchone()
        return row[0] if row else 0.0

    def credit(self, mission_id: str, amount: float, reason: str = "") -> Transaction:
        if amount < 0:
            raise ValueError(f"Amount must be non-negative: {amount}")
        with self._lock:
            balance = self._get_balance() + amount
            tx = Transaction("network", self.wallet_id, amount, mission_id, reason, balance)
            self._db.execute(
                "UPDATE wallet SET balance=? WHERE wallet_id=?", (balance, self.wallet_id)
            )
            self._db.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                (tx.tx_id, tx.sender, tx.receiver, tx.amount_knx,
                 tx.mission_id, tx.reason, tx.balance_after, tx.timestamp)
            )
            self._db.commit()
        return tx

    def debit(self, mission_id: str, amount: float, reason: str = "") -> Transaction:
        with self._lock:
            current = self._get_balance()
            actual = min(amount, current)
            balance = current - actual
            tx = Transaction(self.wallet_id, "network", -actual, mission_id, reason, balance)
            self._db.execute(
                "UPDATE wallet SET balance=? WHERE wallet_id=?", (balance, self.wallet_id)
            )
            self._db.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                (tx.tx_id, tx.sender, tx.receiver, tx.amount_knx,
                 tx.mission_id, tx.reason, tx.balance_after, tx.timestamp)
            )
            self._db.commit()
        return tx

    def deposit(self, amount: float, mission_id: str = "") -> Transaction:
        return self.credit(mission_id, amount)

    def withdraw(self, amount: float) -> Transaction:
        return self.debit("", amount)

    @property
    def balance(self) -> float:
        with self._lock:
            return round(self._get_balance(), 4)

    @property
    def transaction_count(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) FROM transactions").fetchone()
            return row[0] if row else 0

    def history(self, limit: int = 50) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT tx_id, sender, receiver, amount_knx, mission_id, reason, balance_after, timestamp FROM transactions ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            result = []
            for r in reversed(rows):
                result.append({
                    "tx_id": r[0], "sender": r[1], "receiver": r[2],
                    "amount_knx": r[3], "mission_id": r[4], "reason": r[5],
                    "balance_after": r[6], "timestamp": r[7]
                })
            return result

    def get_history(self) -> list:
        return self.history(limit=100000)

    def summary(self) -> dict:
        with self._lock:
            balance = self._get_balance()
            earned = self._db.execute(
                "SELECT COALESCE(SUM(amount_knx),0) FROM transactions WHERE amount_knx > 0"
            ).fetchone()[0]
            penalties = self._db.execute(
                "SELECT COALESCE(SUM(amount_knx),0) FROM transactions WHERE amount_knx < 0"
            ).fetchone()[0]
            count = self._db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            return {
                "balance_knx": round(balance, 4),
                "total_earned_knx": round(earned, 4),
                "total_penalties_knx": round(-penalties, 4),
                "transaction_count": count,
            }

    def _save(self):
        pass
