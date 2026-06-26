"""
TEE (Trusted Execution Environment) Test
Proves PoPW attestation is cryptographically valid.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.verifier import DroneKeyPair, TEEAttestation, PoPWRecord


def test_keypair_generates_unique_keys():
    kp1 = DroneKeyPair()
    kp2 = DroneKeyPair()
    assert kp1.public_key_hex != kp2.public_key_hex


def test_keypair_sign_and_verify():
    kp = DroneKeyPair()
    data = b"test mission data"
    sig = kp.sign(data)
    assert DroneKeyPair.verify(data, sig, kp.public_key_hex)


def test_keypair_wrong_key_rejected():
    kp1 = DroneKeyPair()
    kp2 = DroneKeyPair()
    data = b"test mission data"
    sig = kp1.sign(data)
    assert not DroneKeyPair.verify(data, sig, kp2.public_key_hex)


def test_keypair_tampered_data_rejected():
    kp = DroneKeyPair()
    data = b"test mission data"
    sig = kp.sign(data)
    assert not DroneKeyPair.verify(b"tampered data", sig, kp.public_key_hex)


def test_tee_attestation_creates_record():
    tee = TEEAttestation()
    att = tee.attest_mission("m1", "hash123", 85)
    assert att["status"] == "SIGNED"
    assert att["mission_id"] == "m1"
    assert att["score"] == 85
    assert len(att["signature"]) > 0
    assert len(att["public_key"]) == 64


def test_tee_attestation_verify():
    tee = TEEAttestation()
    att = tee.attest_mission("m1", "hash123", 85)
    assert tee.verify_attestation(att) is True


def test_tee_attestation_tampered_rejected():
    tee = TEEAttestation()
    att = tee.attest_mission("m1", "hash123", 85)
    att["score"] = 100
    assert tee.verify_attestation(att) is False


def test_tee_attestation_ids_unique():
    tee = TEEAttestation()
    ids = [tee.attest_mission(f"m{i}", "hash", 80)["attestation_id"] for i in range(5)]
    assert len(set(ids)) == 5


def test_popw_record_create_and_verify():
    class FakeTraj:
        positions = [(1.0, 2.0), (3.0, 4.0)]

    popw = PoPWRecord()
    record = popw.create_record("m1", FakeTraj(), 90)
    assert record["on_chain_ready"] is True
    assert record["popw_version"] == "2.0"
    result = popw.verify_record(record)
    assert result["fully_verified"] is True
    assert result["tee_attestation_valid"] is True
    assert result["popw_signature_valid"] is True


def test_popw_format_for_chain():
    class FakeTraj:
        positions = [(1.0, 2.0)]

    popw = PoPWRecord()
    record = popw.create_record("m1", FakeTraj(), 85)
    chain_str = popw.format_for_chain(record)
    assert chain_str.startswith("POPW|m1|")
    parts = chain_str.split("|")
    assert len(parts) == 5


def test_tee_hardware_id():
    tee = TEEAttestation()
    att = tee.attest_mission("m1", "hash", 80)
    assert att["hardware_id"] == "SGX_SIM_001"
    assert att["tee_version"] == "dronesync-tee-v2"
