"""Tests for DroneSync Privacy Module."""

import pytest
from dronesync.privacy import (
    FlightDataEncryptor,
    FlightDataRedactor,
    EncryptedPacket,
    compute_flight_hash,
)

SAMPLE_FLIGHT = {
    "mission_id": "m-001",
    "trajectory": [[50.45, 30.52, 50.0, 1700000000]],
    "pilot_id": "pilot-xyz",
    "sensor_data": {"battery_pct": 85},
}


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        enc = FlightDataEncryptor()
        packet = enc.encrypt(SAMPLE_FLIGHT)
        result = enc.decrypt(packet)
        assert result == SAMPLE_FLIGHT

    def test_ciphertext_differs_from_plaintext(self):
        enc = FlightDataEncryptor()
        packet = enc.encrypt(SAMPLE_FLIGHT)
        import json
        plain_bytes = json.dumps(SAMPLE_FLIGHT, separators=(",", ":")).encode()
        assert packet.ciphertext != plain_bytes

    def test_nonce_is_random_each_call(self):
        enc = FlightDataEncryptor()
        p1 = enc.encrypt(SAMPLE_FLIGHT)
        p2 = enc.encrypt(SAMPLE_FLIGHT)
        assert p1.nonce != p2.nonce

    def test_from_passphrase_deterministic_key(self):
        e1 = FlightDataEncryptor.from_passphrase("secret123")
        e2 = FlightDataEncryptor.from_passphrase("secret123")
        packet = e1.encrypt(SAMPLE_FLIGHT)
        result = e2.decrypt(packet)
        assert result == SAMPLE_FLIGHT

    def test_wrong_key_fails_to_decrypt(self):
        enc = FlightDataEncryptor()
        packet = enc.encrypt(SAMPLE_FLIGHT)
        attacker = FlightDataEncryptor()
        with pytest.raises(Exception):
            attacker.decrypt(packet)

    def test_tampered_ciphertext_raises(self):
        enc = FlightDataEncryptor()
        packet = enc.encrypt(SAMPLE_FLIGHT)
        tampered = EncryptedPacket(
            ciphertext=bytes([b ^ 0xFF for b in packet.ciphertext]),
            nonce=packet.nonce,
            tag=packet.tag,
            key_id=packet.key_id,
        )
        with pytest.raises(Exception):
            enc.decrypt(tampered)

    def test_packet_to_dict_and_back(self):
        enc = FlightDataEncryptor()
        packet = enc.encrypt(SAMPLE_FLIGHT)
        d = packet.to_dict()
        restored = EncryptedPacket.from_dict(d)
        result = enc.decrypt(restored)
        assert result == SAMPLE_FLIGHT

    def test_invalid_key_size_raises(self):
        with pytest.raises(ValueError):
            FlightDataEncryptor(key=b"short")


class TestRedactor:
    def test_removes_pilot_id(self):
        r = FlightDataRedactor()
        result = r.redact(SAMPLE_FLIGHT)
        assert result["pilot_id"] == "[REDACTED]"

    def test_preserves_non_sensitive(self):
        r = FlightDataRedactor()
        result = r.redact(SAMPLE_FLIGHT)
        assert result["mission_id"] == "m-001"

    def test_custom_extra_fields(self):
        r = FlightDataRedactor()
        result = r.redact({"mission_id": "x", "internal_ip": "10.0.0.1"},
                          extra_fields={"internal_ip"})
        assert result["internal_ip"] == "[REDACTED]"

    def test_nested_redaction(self):
        r = FlightDataRedactor()
        data = {"meta": {"pilot_id": "p1", "score": 0.9}}
        result = r.redact(data)
        assert result["meta"]["pilot_id"] == "[REDACTED]"
        assert result["meta"]["score"] == 0.9

    def test_list_items_processed(self):
        r = FlightDataRedactor()
        data = {"logs": [{"pilot_id": "p1"}, {"pilot_id": "p2"}]}
        result = r.redact(data)
        for item in result["logs"]:
            assert item["pilot_id"] == "[REDACTED]"


class TestFlightHash:
    def test_hash_is_64_hex_chars(self):
        h = compute_flight_hash(SAMPLE_FLIGHT)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_deterministic(self):
        h1 = compute_flight_hash(SAMPLE_FLIGHT)
        h2 = compute_flight_hash(SAMPLE_FLIGHT)
        assert h1 == h2

    def test_different_data_different_hash(self):
        h1 = compute_flight_hash({"a": 1})
        h2 = compute_flight_hash({"a": 2})
        assert h1 != h2

    def test_key_order_independent(self):
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert compute_flight_hash(d1) == compute_flight_hash(d2)
