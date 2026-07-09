"""
DroneSync - TEE Verifier Module
Trusted Execution Environment simulation for PoPW artifact attestation.
In production: integrates with Intel SGX / ARM TrustZone.

Signing: Ed25519 (asymmetric) — private key signs, public key verifies.
Anyone can verify a PoPW artifact using only the public key.
"""
from typing import Any
import hashlib
import time
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class DroneKeyPair:
    def __init__(self):
        self._private_key = Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    @property
    def public_key_hex(self) -> str:
        return self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def sign(self, data: bytes) -> str:
        import base64
        sig = self._private_key.sign(data)
        return base64.b64encode(sig).decode()

    @staticmethod
    def verify(data: bytes, signature_b64: str, public_key_hex: str) -> bool:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            pub_bytes = bytes.fromhex(public_key_hex)
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            vk = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig = base64.b64decode(signature_b64)
            vk.verify(sig, data)
            return True
        except (InvalidSignature, Exception):
            return False


class TEEAttestation:
    TEE_VERSION = "dronesync-tee-v2"
    HARDWARE_ID = "SGX_SIM_001"

    # Реестр доверенных публичных ключей TEE
    # В production загружается из конфига или смарт-контракта
    _trusted_keys: set = set()

    def __init__(self):
        self.attestation_count = 0
        self._keypair = DroneKeyPair()
        self.public_key = self._keypair.public_key_hex
        # Регистрируем свой ключ как доверенный
        TEEAttestation._trusted_keys.add(self.public_key)

    @classmethod
    def register_trusted_key(cls, public_key_hex: str):
        """Добавить доверенный публичный ключ TEE в реестр."""
        cls._trusted_keys.add(public_key_hex)

    @classmethod
    def is_trusted_key(cls, public_key_hex: str) -> bool:
        return public_key_hex in cls._trusted_keys

    def attest_mission(self, mission_id: str, trajectory_hash: str, score: int) -> dict:
        self.attestation_count += 1
        timestamp = int(time.time())
        payload = {
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "timestamp": timestamp,
            "tee_version": self.TEE_VERSION,
            "hardware_id": self.HARDWARE_ID
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()
        signature = self._keypair.sign(payload_bytes)
        return {
            "attestation_id": "ATT_" + str(self.attestation_count).zfill(6),
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "timestamp": timestamp,
            "tee_version": self.TEE_VERSION,
            "hardware_id": self.HARDWARE_ID,
            "payload_hash": payload_hash,
            "signature": signature,
            "public_key": self.public_key,
            "status": "SIGNED"
        }

    def verify_attestation(self, attestation: dict) -> bool:
        payload = {
            "mission_id": attestation["mission_id"],
            "trajectory_hash": attestation.get("trajectory_hash", ""),
            "score": attestation["score"],
            "timestamp": attestation["timestamp"],
            "tee_version": attestation["tee_version"],
            "hardware_id": attestation["hardware_id"]
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        pub_key = attestation["public_key"]
        if not TEEAttestation.is_trusted_key(pub_key):
            return False
        return DroneKeyPair.verify(payload_bytes, attestation["signature"], pub_key)


class PoPWRecord:
    def __init__(self):
        self.tee = TEEAttestation()
        self._keypair = DroneKeyPair()
        self.public_key = self._keypair.public_key_hex

    def create_record(self, mission_id: str, trajectory: Any, score: int) -> dict:
        traj_data = str(trajectory.positions).encode()
        trajectory_hash = hashlib.sha256(traj_data).hexdigest()
        attestation = self.tee.attest_mission(mission_id=mission_id, trajectory_hash=trajectory_hash, score=score)
        record_payload = json.dumps({
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "attestation_id": attestation["attestation_id"]
        }, sort_keys=True).encode()
        record_signature = self._keypair.sign(record_payload)
        return {
            "popw_version": "2.0",
            "mission_id": mission_id,
            "trajectory_hash": trajectory_hash,
            "score": score,
            "attestation": attestation,
            "popw_signature": record_signature,
            "popw_public_key": self.public_key,
            "on_chain_ready": True
        }

    def verify_record(self, record: dict) -> dict:
        tee_ok = self.tee.verify_attestation(record["attestation"])
        record_payload = json.dumps({
            "mission_id": record["mission_id"],
            "trajectory_hash": record["trajectory_hash"],
            "score": record["score"],
            "attestation_id": record["attestation"]["attestation_id"]
        }, sort_keys=True).encode()
        popw_ok = DroneKeyPair.verify(record_payload, record["popw_signature"], record["popw_public_key"])
        return {
            "mission_id": record["mission_id"],
            "tee_attestation_valid": tee_ok,
            "popw_signature_valid": popw_ok,
            "fully_verified": tee_ok and popw_ok,
            "verified_at": int(time.time())
        }

    def format_for_chain(self, record: dict) -> str:
        import json
        canonical = json.dumps({
            "mission_id": record["mission_id"],
            "trajectory_hash": record["trajectory_hash"],
            "score": record["score"],
            "attestation_id": record["attestation"]["attestation_id"],
            "popw_version": record["popw_version"],
        }, sort_keys=True)
        reproducible_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return (
            "POPW|" +
            record["mission_id"] + "|" +
            record["trajectory_hash"][:16] + "|" +
            str(record["score"]) + "|" +
            reproducible_hash[:16]
        )
