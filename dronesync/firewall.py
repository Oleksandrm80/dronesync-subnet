"""
DroneSync - Drone Firewall
"""
import time
import hashlib
import hmac
import json
import os


class DroneFirewall:
    MAX_COMMANDS_PER_MINUTE = 20
    ALLOWED_ACTIONS = {"fly", "hover", "land", "return_home", "scan", "deliver", "execute_task"}

    def __init__(self, drone_id: str, secret_key: str = None):
        self.drone_id = drone_id
        self.blocked_log = []
        self.allowed_log = []
        self._command_times = []
        self.trusted_sources = set()
        self._secret = (secret_key or os.urandom(32).hex()).encode()
        self._admin_token = os.urandom(16).hex()

    def add_trusted_source(self, source_id: str, admin_token: str = None) -> dict:
        if not admin_token or admin_token != self._admin_token:
            return {"status": "DENIED", "reason": "invalid_admin_token"}
        self.trusted_sources.add(source_id)
        return {"status": "ADDED", "source_id": source_id}

    def filter(self, command: dict) -> dict:
        action = command.get("action", "")
        source = command.get("source", "unknown")
        timestamp = command.get("timestamp", 0)

        if source in self.trusted_sources:
            entry = {"action": action, "source": source, "timestamp": int(time.time()), "status": "ALLOWED"}
            self.allowed_log.append(entry)
            return {"status": "ALLOWED", "action": action}

        if action not in self.ALLOWED_ACTIONS:
            return self._block(command, "unknown_action")

        if not command.get("signature"):
            return self._block(command, "missing_signature")

        cmd_copy = {k: v for k, v in command.items() if k != "signature"}
        expected_sig = hmac.new(
            self._secret,
            json.dumps(cmd_copy, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(command["signature"], expected_sig):
            return self._block(command, "invalid_signature")

        now = int(time.time())
        if timestamp and (now - timestamp) > 30:
            return self._block(command, "stale_command")

        self._command_times = [t for t in self._command_times if now - t < 60]
        if len(self._command_times) >= self.MAX_COMMANDS_PER_MINUTE:
            return self._block(command, "rate_limit_exceeded")

        self._command_times.append(now)
        entry = {"action": action, "source": source, "timestamp": now, "status": "ALLOWED"}
        self.allowed_log.append(entry)
        return {"status": "ALLOWED", "action": action}

    def filter_command(self, command: dict) -> dict:
        return self.filter(command)

    def _block(self, command: dict, reason: str) -> dict:
        entry = {
            "action": command.get("action", "unknown"),
            "source": command.get("source", "unknown"),
            "reason": reason,
            "timestamp": int(time.time())
        }
        self.blocked_log.append(entry)
        return {"status": "BLOCKED", "reason": reason}

    def get_report(self) -> dict:
        log_hash = hashlib.sha256(str(self.blocked_log).encode()).hexdigest()
        return {
            "drone_id": self.drone_id,
            "total_allowed": len(self.allowed_log),
            "total_blocked": len(self.blocked_log),
            "blocked_log": self.blocked_log,
            "log_hash": log_hash,
            "on_chain_ready": True
        }
