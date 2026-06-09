"""
DroneSync - Drone Firewall
Filters all incoming commands. Blocks anomalies and logs attempts in PoPW.
"""
import time
import hashlib


class DroneFirewall:
    """
    Command firewall for drone nodes.
    Every incoming command is validated before execution.
    Blocked attempts are logged and included in PoPW record.
    """

    MAX_COMMANDS_PER_MINUTE = 20
    ALLOWED_ACTIONS = {"fly", "hover", "land", "return_home", "scan", "deliver", "execute_task"}

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.blocked_log = []
        self.allowed_log = []
        self._command_times = []
        self.trusted_sources = set()

    def add_trusted_source(self, source_id: str) -> dict:
        """Add a trusted source that bypasses rate limiting and signature checks."""
        self.trusted_sources.add(source_id)
        return {"status": "ADDED", "source_id": source_id}

    def filter(self, command: dict) -> dict:
        """
        Filter incoming command.
        Returns result with status ALLOWED or BLOCKED + reason.
        """
        action = command.get("action", "")
        source = command.get("source", "unknown")
        timestamp = command.get("timestamp", 0)

        # Trusted sources bypass all checks
        if source in self.trusted_sources:
            entry = {"action": action, "source": source, "timestamp": int(time.time()), "status": "ALLOWED"}
            self.allowed_log.append(entry)
            return {"status": "ALLOWED", "action": action}

        # Check 1: unknown action
        if action not in self.ALLOWED_ACTIONS:
            return self._block(command, "unknown_action")

        # Check 2: missing signature
        if "signature" not in command:
            return self._block(command, "missing_signature")

        # Check 3: stale command (older than 30 seconds)
        now = int(time.time())
        if timestamp and (now - timestamp) > 30:
            return self._block(command, "stale_command")

        # Check 4: rate limit
        self._command_times = [t for t in self._command_times if now - t < 60]
        if len(self._command_times) >= self.MAX_COMMANDS_PER_MINUTE:
            return self._block(command, "rate_limit_exceeded")

        self._command_times.append(now)
        entry = {"action": action, "source": source, "timestamp": now, "status": "ALLOWED"}
        self.allowed_log.append(entry)
        return {"status": "ALLOWED", "action": action}

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
        """Return firewall report for PoPW inclusion."""
        log_hash = hashlib.sha256(str(self.blocked_log).encode()).hexdigest()
        return {
            "drone_id": self.drone_id,
            "total_allowed": len(self.allowed_log),
            "total_blocked": len(self.blocked_log),
            "blocked_log": self.blocked_log,
            "log_hash": log_hash,
            "on_chain_ready": True
        }
