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
import os


class Ed25519Signer:
    """
    Ed25519 digital signatures for PoPW records.
    Each drone generates a keypair on init.
    Validator verifies signature before accepting PoPW.
    Ed25519 chosen over RSA: faster, smaller keys, safe by default.
    """

    def __init__(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import (
                Encoding, PublicFormat, PrivateFormat, NoEncryption
            )
            self._private_key = Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            pub_bytes = self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            self.public_key_hex = pub_bytes.hex()
            self._backend = "cryptography"
        except ImportError:
            # Fallback: HMAC-SHA256 симуляция если cryptography не установлен
            self._secret = os.urandom(32)
            self.public_key_hex = self._secret.hex()
            self._backend = "hmac_fallback"

    def sign(self, data: bytes) -> str:
        """Sign bytes, return hex signature."""
        if self._backend == "cryptography":
            sig = self._private_key.sign(data)
            return sig.hex()
        else:
            return hmac.new(self._secret, data, hashlib.sha256).hexdigest()

    def verify(self, data: bytes, signature_hex: str,
               public_key_hex: str = None) -> bool:
        """Verify signature. Uses own public key if none provided."""
        if self._backend == "cryptography":
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
                from cryptography.exceptions import InvalidSignature
                if public_key_hex is None:
                    pub_key = self._public_key
                else:
                    pub_bytes = bytes.fromhex(public_key_hex)
                    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
                pub_key.verify(bytes.fromhex(signature_hex), data)
                return True
            except Exception:
                return False
        else:
            expected = hmac.new(self._secret, data, hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature_hex, expected)

    def sign_popw(self, popw_hash: str, mission_id: str) -> dict:
        """Sign a PoPW record hash. Returns signature bundle."""
        payload = f"{mission_id}:{popw_hash}".encode()
        signature = self.sign(payload)
        return {
            "mission_id": mission_id,
            "popw_hash": popw_hash,
            "signature": signature,
            "public_key": self.public_key_hex,
            "backend": self._backend,
            "signed_at": int(time.time())
        }

    def verify_popw(self, sig_bundle: dict) -> bool:
        """Verify a PoPW signature bundle."""
        payload = f"{sig_bundle['mission_id']}:{sig_bundle['popw_hash']}".encode()
        return self.verify(
            data=payload,
            signature_hex=sig_bundle["signature"],
            public_key_hex=sig_bundle.get("public_key")
        )


class GPSSpoofingDetector:
    """
    Detects GPS spoofing attacks by analyzing trajectory anomalies.
    Flags impossible speed changes, teleportation, and signal patterns.
    """

    MAX_SPEED_MS = 200.0       # max drone speed — above this is teleportation
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

        if nonce in self.nonce_cache:
            return False
        self.nonce_cache.add(nonce)

        cmd_time = command.get("timestamp", 0)
        if abs(time.time() - cmd_time) > 30:
            return False

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

        if self.baseline_scores:
            avg = sum(self.baseline_scores) / len(self.baseline_scores)
            if current_score < avg * 0.7:
                anomalies.append({
                    "type": "SCORE_DROP",
                    "expected": round(avg, 1),
                    "actual": current_score,
                    "severity": "HIGH"
                })

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
        self.ed25519 = Ed25519Signer()

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

    def sign_and_verify_popw(self, popw_hash: str, mission_id: str) -> dict:
        """Sign PoPW hash and immediately verify — confirms key pair works."""
        sig_bundle = self.ed25519.sign_popw(popw_hash, mission_id)
        verified = self.ed25519.verify_popw(sig_bundle)
        return {
            "signed": True,
            "verified": verified,
            "public_key": sig_bundle["public_key"][:16] + "...",
            "backend": sig_bundle["backend"],
            "status": "OK" if verified else "SIGNATURE_FAILED"
        }
