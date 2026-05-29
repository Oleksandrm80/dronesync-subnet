"""
DroneSync - Node Connection Module
Handles Konnex network connection with auto-reconnect
"""
import time
import hashlib
import json


class KonnexNode:
    """
    Manages connection to Konnex network.
    Handles reconnection, authentication, mission polling.
    In production: uses official Konnex SDK.
    """

    MAX_RETRIES = 5
    RETRY_DELAY = 3.0
    TIMEOUT = 30.0

    def __init__(self, wallet_address: str,
                 network: str = "testnet"):
        self.wallet = wallet_address
        self.network = network
        self.connected = False
        self.retry_count = 0
        self.session_id = None

    def connect(self) -> bool:
        """Connect to Konnex node with auto-retry."""
        for attempt in range(self.MAX_RETRIES):
            try:
                self.session_id = hashlib.sha256(
                    f"{self.wallet}{time.time()}".encode()
                ).hexdigest()[:16]
                self.connected = True
                self.retry_count = 0
                return True
            except Exception as e:
                self.retry_count += 1
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        return False

    def disconnect(self):
        self.connected = False
        self.session_id = None

    def is_healthy(self) -> bool:
        return self.connected and self.session_id is not None

    def reconnect_if_needed(self) -> bool:
        if not self.is_healthy():
            return self.connect()
        return True

    def get_status(self) -> dict:
        return {
            "connected": self.connected,
            "network": self.network,
            "wallet": self.wallet[:8] + "...",
            "session_id": self.session_id,
            "retry_count": self.retry_count
        }