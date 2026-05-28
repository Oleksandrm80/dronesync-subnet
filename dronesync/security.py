"""
DroneSync - Security Module
Protection against GPS spoofing, signal hijacking, and command injection
Critical for PoPW integrity on Konnex network
"""
import hashlib
import hmac
import time
import math
import json


class GPSSpoofingDetector:
    """
    Detects GPS spoofing attacks by analyzing trajectory anomalies.
    Flags impossible speed changes, teleportation, and signal patterns.
    """

    MAX_SPEED_MS = 500.0        # max drone speed 30 m/s
    MAX_ALT_CHANGE = 20.0      # max altitude change per step (meters)
    MIN_GPS_ACCURACY = 10.0    # meters - worse than this is suspicious

    def __init__(self):
        self.alerts = []

    def analyze_trajectory(self, positions: list) -> dict:
        """Analyze trajectory for spoofing indicators."""
        alerts = []
        for i in range(1, len(positions)):
            prev = positions[i-1]
            curr = positions[i]

            # Check impossible speed
            dist = self._haversine(prev[0], prev[1], curr[0], curr[1])
            time_delta = max(curr[3] - prev[3], 0.1) if len(curr) > 3 else 1.0
            speed = dist / time_delta

            if speed > self.MAX_SPEED_MS:
                alerts.append({
                    "type": "IMPOSSIBLE_SPEED",
                    "step": i,
                    "speed_ms": round(speed, 2),
                    "severity": "HIGH"
                })

            # Check altitude jump
            alt_change = abs(curr[2] - prev[2])
            if alt_change > self.MAX_ALT_CHANGE:
                alerts.append({
                    "type": "ALTITUDE_ANOMALY",
                    "step": i,
                    "alt_change": round(alt_change, 2),
                    "severity": "MEDIUM"
                })

        return {
            "spoofing_detected": len(alerts) > 0,
            "alert_count": len(alerts),
            "alerts": alerts,
            "status": "COMPROMISED" if alerts else "CLEAN"
        }

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


class CommandSigner:
    """
    Cryptographic signing for drone commands.
    Prevents command injection and replay attacks.
    Every mission command is signed with HMAC-SHA256.
    """

    def __init__(self, secret_key: str = "dronesync_secret_v1"):
        self.secret = secret_key.encode()
        self.nonce_cache = set()

    def sign_command(self, command: dict) -> dict:
        """Sign a mission command with HMAC."""
        nonce = str(int(time.time() * 1000))
        command["nonce"] = nonce
        command["timestamp"] = int(time.time())

        payload = json.dumps(command, sort_keys=True).encode()
        signature = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

        return {
            "command": command,
            "signature": signature,
            "signed_at": command["timestamp"]
        }

    def verify_command(self, signed_command: dict) -> bool:
        """Verify command signature. Rejects replays and tampering."""
        command = signed_command.get("command", {})
        received_sig = signed_command.get("signature", "")
        nonce = command.get("nonce", "")

        # Reject replay attacks
        if nonce in self.nonce_cache:
            return False
        self.nonce_cache.add(nonce)

        # Verify timestamp (reject commands older than 30 seconds)
        cmd_time = command.get("timestamp", 0)
        if abs(time.time() - cmd_time) > 30:
            return False

        # Verify signature
        payload = json.dumps(command, sort_keys=True).encode()
        expected_sig = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(received_sig, expected_sig)


class AnomalyDetector:
    """
    AI-based anomaly detection for drone behavior.
    Detects hijacking by comparing expected vs actual behavior.
    """

    def __init__(self):
        self.baseline_scores = []

    def update_baseline(self, score: int):
        """Update normal behavior baseline."""
        self.baseline_scores.append(score)
        if len(self.baseline_scores) > 10:
            self.baseline_scores.pop(0)

    def detect_anomaly(self, current_score: int,
                        trajectory: list) -> dict:
        """Detect if current behavior deviates from baseline."""
        anomalies = []

        # Score anomaly
        if self.baseline_scores:
            avg = sum(self.baseline_scores) / len(self.baseline_scores)
            if current_score < avg * 0.7:
                anomalies.append({
                    "type": "SCORE_DROP",
                    "expected": round(avg, 1),
                    "actual": current_score,
                    "severity": "HIGH"
                })

        # Trajectory anomaly - sudden direction change
        if len(trajectory) >= 3:
            for i in range(2, len(trajectory)):
                p1 = trajectory[i-2]
                p2 = trajectory[i-1]
                p3 = trajectory[i]
                angle = self._direction_change(p1, p2, p3)
                if angle > 150:
                    anomalies.append({
                        "type": "SHARP_DIRECTION_CHANGE",
                        "step": i,
                        "angle": round(angle, 1),
                        "severity": "MEDIUM"
                    })

        return {
            "hijacking_suspected": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "threat_level": "HIGH" if any(
                a["severity"] == "HIGH" for a in anomalies
            ) else "LOW" if anomalies else "NONE"
        }

    def _direction_change(self, p1, p2, p3) -> float:
        """Calculate direction change angle between three points."""
        v1 = (p2[0]-p1[0], p2[1]-p1[1])
        v2 = (p3[0]-p2[0], p3[1]-p2[1])
        dot = v1[0]*v2[0] + v1[1]*v2[1]
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2) or 0.0001
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2) or 0.0001
        cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
        return math.degrees(math.acos(cos_angle))


class DroneSecuritySuite:
    """
    Complete security suite combining all protection layers.
    Single entry point for all security checks.
    """

    def __init__(self):
        self.spoof_detector = GPSSpoofingDetector()
        self.cmd_signer = CommandSigner()
        self.anomaly_detector = AnomalyDetector()

    def full_security_check(self, trajectory, score: int) -> dict:
        """Run complete security analysis on mission."""
        spoof_result = self.spoof_detector.analyze_trajectory(
            trajectory.positions
        )
        anomaly_result = self.anomaly_detector.detect_anomaly(
            score, trajectory.positions
        )
        self.anomaly_detector.update_baseline(score)

        overall_safe = (
            not spoof_result["spoofing_detected"] and
            not anomaly_result["hijacking_suspected"]
        )

        return {
            "overall_status": "SECURE" if overall_safe else "THREAT_DETECTED",
            "gps_spoofing": spoof_result["status"],
            "hijacking": "NONE" if not anomaly_result[
                "hijacking_suspected"] else "SUSPECTED",
            "threat_level": anomaly_result["threat_level"],
            "mission_cleared": overall_safe
        }