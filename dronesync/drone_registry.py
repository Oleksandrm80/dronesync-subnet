"""
DroneSync - Dynamic Drone Registry
Drones register themselves and appear on dashboard automatically.
"""
import time
import threading
import hashlib


class DroneRegistry:
    """
    Dynamic registry — drones register/unregister automatically.
    Supports MAVLink, HTTP API, WebSocket, MQTT sources.
    """

    HEARTBEAT_TIMEOUT = 30  # seconds before drone marked offline

    def __init__(self):
        self._drones = {}
        self._lock = threading.Lock()

    def register(self, drone_id: str, source: str = "unknown", metadata: dict = None) -> dict:
        """Register a new drone or update existing."""
        with self._lock:
            self._drones[drone_id] = {
                "drone_id":   drone_id,
                "source":     source,
                "connected":  True,
                "registered_at": int(time.time()),
                "last_seen":  int(time.time()),
                "telemetry":  {},
                "metadata":   metadata or {},
                "token": hashlib.sha256(f"{drone_id}{time.time()}".encode()).hexdigest()[:16]
            }
        return {"status": "registered", "drone_id": drone_id}

    def unregister(self, drone_id: str) -> dict:
        with self._lock:
            if drone_id in self._drones:
                del self._drones[drone_id]
                return {"status": "unregistered", "drone_id": drone_id}
        return {"status": "not_found", "drone_id": drone_id}

    def update_telemetry(self, drone_id: str, telemetry: dict) -> bool:
        with self._lock:
            if drone_id not in self._drones:
                self.register(drone_id, source=telemetry.get("source", "api"))
            self._drones[drone_id]["telemetry"]  = telemetry
            self._drones[drone_id]["last_seen"]   = int(time.time())
            self._drones[drone_id]["connected"]   = True
        return True

    def heartbeat(self, drone_id: str) -> bool:
        with self._lock:
            if drone_id in self._drones:
                self._drones[drone_id]["last_seen"] = int(time.time())
                return True
        return False

    def get_active_drones(self) -> dict:
        now = int(time.time())
        with self._lock:
            active = {}
            for did, d in self._drones.items():
                age = now - d["last_seen"]
                d["connected"] = age < self.HEARTBEAT_TIMEOUT
                d["age_s"] = age
                active[did] = dict(d)
        return active

    def get_drone(self, drone_id: str) -> dict:
        with self._lock:
            return dict(self._drones.get(drone_id, {}))

    def count(self) -> int:
        with self._lock:
            return len(self._drones)


# Global registry instance
registry = DroneRegistry()
