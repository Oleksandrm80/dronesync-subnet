"""
DroneSync - Persistent Storage
Saves drone state between runs — reputation, memory, mission history.
Without this, a 24/7 node loses all data on restart.
"""
import hashlib
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
        payload = json.dumps(data, sort_keys=True, indent=2)
        data["_integrity"] = hashlib.sha256(payload.encode()).hexdigest()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    def load(self) -> dict:
        """Load drone state from disk. Returns empty dict if no data yet."""
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            import logging
            logging.getLogger(__name__).warning("Storage corrupted: %s — resetting", self.path)
            os.rename(self.path, self.path + ".corrupted")
            return {}
        stored_hash = data.pop("_integrity", None)
        if stored_hash:
            check = json.dumps(data, sort_keys=True, indent=2)
            if hashlib.sha256(check.encode()).hexdigest() != stored_hash:
                return {"_tampered": True}
        return data
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


class SecureStorage:
    """
    Encrypted storage for sensitive mission data.
    Uses Fernet symmetric encryption (AES-128-CBC + HMAC).
    Key derived from drone_id — in production use hardware key.
    """

    def __init__(self, drone_id: str):
        import os
        import base64
        from cryptography.fernet import Fernet
        _key_path = os.path.join(STORAGE_DIR, drone_id + "_fernet.key")
        os.makedirs(STORAGE_DIR, exist_ok=True)
        if os.path.exists(_key_path):
            with open(_key_path, "rb") as _kf:
                key = _kf.read()
        else:
            key = base64.urlsafe_b64encode(os.urandom(32))
            with open(_key_path, "wb") as _kf:
                _kf.write(key)
        self._fernet = Fernet(key)
        self.drone_id = drone_id
        self._store = {}
        self._persist_path = os.path.join(STORAGE_DIR, drone_id + "_secure.bin")
        os.makedirs(STORAGE_DIR, exist_ok=True)
        if os.path.exists(self._persist_path):
            import json as _json
            with open(self._persist_path, "r") as f:
                self._store = _json.load(f)
    def save(self, key: str, data: dict) -> str:
        """Encrypt and store data. Returns storage hash."""
        payload = json.dumps(data, sort_keys=True).encode()
        encrypted = self._fernet.encrypt(payload)
        # JSON can't hold raw bytes -- persist ciphertext as hex.
        self._store[key] = encrypted.hex()
        with open(self._persist_path, "w") as f:
            json.dump(self._store, f)
        return hashlib.sha256(payload).hexdigest()

    def load(self, key: str) -> dict:
        """Decrypt and return data."""
        if key not in self._store:
            return {}
        decrypted = self._fernet.decrypt(bytes.fromhex(self._store[key]))
        return json.loads(decrypted)

    def verify(self, key: str, expected_hash: str) -> bool:
        """Verify data has not been tampered with."""
        if key not in self._store:
            return False
        decrypted = self._fernet.decrypt(bytes.fromhex(self._store[key]))
        actual_hash = hashlib.sha256(decrypted).hexdigest()
        return actual_hash == expected_hash

    def get_status(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "stored_keys": list(self._store.keys()),
            "total_records": len(self._store),
            "encrypted": True
        }
