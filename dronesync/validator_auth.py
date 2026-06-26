"""
DroneSync - Validator TLS Authentication
Secures validator-to-validator communication.
"""
import hashlib
import hmac
import time
import os
import json


class ValidatorAuth:
    """
    HMAC-based authentication for validator nodes.
    Each message is signed with a shared secret.
    Prevents unauthorized nodes from joining the network.
    """

    TOKEN_TTL = 30  # seconds

    def __init__(self, secret: str = None):
        self._secret = (secret or os.urandom(32).hex()).encode()

    def sign_message(self, payload: dict) -> dict:
        """Add timestamp and HMAC signature to message."""
        payload = dict(payload)
        payload["_ts"] = time.time()
        payload["_nonce"] = os.urandom(8).hex()
        body = json.dumps(payload, sort_keys=True).encode()
        sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        payload["_sig"] = sig
        return payload

    def verify_message(self, payload: dict) -> bool:
        """Verify HMAC signature and timestamp freshness."""
        payload = dict(payload)
        sig = payload.pop("_sig", None)
        if not sig:
            return False

        ts = payload.get("_ts", 0)
        if abs(time.time() - ts) > self.TOKEN_TTL:
            return False

        body = json.dumps(payload, sort_keys=True).encode()
        expected = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def generate_token(self, validator_id: str) -> dict:
        """Generate auth token for validator handshake."""
        return self.sign_message({
            "type": "auth",
            "validator_id": validator_id,
        })

    def verify_token(self, token: dict) -> bool:
        """Verify auth token from another validator."""
        if token.get("type") != "auth":
            return False
        return self.verify_message(token)

    def get_wss_uri(self, host: str, port: int) -> str:
        """Return secure WebSocket URI."""
        return f"wss://{host}:{port}"

    def get_ws_uri(self, host: str, port: int) -> str:
        """Return plain WebSocket URI for local dev."""
        return f"ws://{host}:{port}"
