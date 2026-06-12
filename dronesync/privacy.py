"""
DroneSync -- Privacy Module
Encrypts flight data before on-chain submission.
Provides HMAC integrity verification and selective field redaction.
"""

import hashlib
import hmac
import json
import os
import struct
from dataclasses import dataclass


@dataclass
class EncryptedPacket:
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    key_id: str
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "key_id": self.key_id,
            "nonce": self.nonce.hex(),
            "tag": self.tag.hex(),
            "ciphertext": self.ciphertext.hex(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EncryptedPacket":
        return cls(
            ciphertext=bytes.fromhex(d["ciphertext"]),
            nonce=bytes.fromhex(d["nonce"]),
            tag=bytes.fromhex(d["tag"]),
            key_id=d["key_id"],
            version=d.get("version", 1),
        )


class FlightDataEncryptor:
    """
    AES-256-GCM encryption for flight data.
    Falls back to SHA-256 XOR stream cipher if cryptography lib is unavailable.
    """

    KEY_SIZE = 32
    NONCE_SIZE = 12

    def __init__(self, key: bytes = None, key_id: str = "default"):
        if key is not None and len(key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")
        self._key = key or os.urandom(self.KEY_SIZE)
        self._key_id = key_id

    @classmethod
    def from_passphrase(cls, passphrase: str, key_id: str = "default") -> "FlightDataEncryptor":
        key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), b"dronesync-salt", 100_000)
        return cls(key=key, key_id=key_id)

    def encrypt(self, data: dict) -> EncryptedPacket:
        plaintext = json.dumps(data, separators=(",", ":")).encode()
        nonce = os.urandom(self.NONCE_SIZE)
        ciphertext, tag = self._encrypt_gcm(plaintext, nonce)
        return EncryptedPacket(ciphertext=ciphertext, nonce=nonce, tag=tag, key_id=self._key_id)

    def decrypt(self, packet: EncryptedPacket) -> dict:
        plaintext = self._decrypt_gcm(packet.ciphertext, packet.nonce, packet.tag)
        return json.loads(plaintext.decode())

    @staticmethod
    def _aesgcm_available() -> bool:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa
            return True
        except BaseException:
            return False

    def _encrypt_gcm(self, plaintext: bytes, nonce: bytes):
        if self._aesgcm_available():
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(self._key)
                combined = aesgcm.encrypt(nonce, plaintext, None)
                return combined[:-16], combined[-16:]
            except BaseException:
                pass
        return self._xor_stream_encrypt(plaintext, nonce)

    def _decrypt_gcm(self, ciphertext: bytes, nonce: bytes, tag: bytes) -> bytes:
        if self._aesgcm_available():
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(self._key)
                return aesgcm.decrypt(nonce, ciphertext + tag, None)
            except BaseException:
                pass
        plaintext, _ = self._xor_stream_encrypt(ciphertext, nonce)
        computed_tag = self._compute_tag(ciphertext, nonce)
        if not hmac.compare_digest(tag, computed_tag):
            raise ValueError("Authentication tag mismatch -- data tampered")
        return plaintext

    def _xor_stream_encrypt(self, data: bytes, nonce: bytes):
        keystream = b""
        counter = 0
        while len(keystream) < len(data):
            block_key = hashlib.sha256(self._key + nonce + struct.pack(">I", counter)).digest()
            keystream += block_key
            counter += 1
        ciphertext = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))
        tag = self._compute_tag(ciphertext, nonce)
        return ciphertext, tag

    def _compute_tag(self, ciphertext: bytes, nonce: bytes) -> bytes:
        return hmac.new(self._key, nonce + ciphertext, hashlib.sha256).digest()[:16]


class FlightDataRedactor:
    """Removes or masks sensitive fields before logging or sharing."""

    SENSITIVE_FIELDS = {"pilot_id", "operator_key", "wallet", "private_key"}

    def redact(self, data: dict, extra_fields: set = None) -> dict:
        fields = self.SENSITIVE_FIELDS | (extra_fields or set())
        return self._redact_recursive(data, fields)

    def _redact_recursive(self, obj, fields: set):
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if k in fields else self._redact_recursive(v, fields)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._redact_recursive(item, fields) for item in obj]
        return obj


def compute_flight_hash(data: dict) -> str:
    """Canonical SHA-256 hash of flight data for on-chain commitment."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()
