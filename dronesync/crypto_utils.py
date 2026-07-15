"""
DroneSync - Shared HMAC-SHA256 signing primitives.
Used by CommandSigner, DroneFirewall, ValidatorAuth, webhook signing,
and swarm peer verification so signature/verify logic lives in one place.
"""
import hashlib
import hmac


def hmac_sign(secret: bytes, payload: bytes) -> str:
    """Return hex-encoded HMAC-SHA256 signature."""
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def hmac_verify(secret: bytes, payload: bytes, signature: str) -> bool:
    """Constant-time comparison against a hex-encoded HMAC-SHA256 signature."""
    return hmac.compare_digest(hmac_sign(secret, payload), signature)
