"""Tests for TEE attestation and PoPW records."""
import pytest
from dronesync.verifier import TEEAttestation, PoPWRecord
from dronesync.protocol import Trajectory
import time


def make_trajectory():
    base = int(time.time())
    return Trajectory(
        positions=[[47.3769 + i * 0.0001, 8.5417, 50.0, base + i * 5]
                   for i in range(3)],
        velocities=[5.0] * 3,
        timestamps=[base + i * 5 for i in range(3)],
    )


def test_attestation_created():
    tee = TEEAttestation()
    result = tee.attest_mission("MISSION_001", "abc123", 95)
    assert result["status"] in ("VERIFIED", "SIGNED")
    assert result["mission_id"] == "MISSION_001"
    assert result["score"] == 95
    assert result["attestation_id"].startswith("ATT_")


def test_attestation_verified():
    tee = TEEAttestation()
    att = tee.attest_mission("MISSION_001", "abc123", 95)
    assert tee.verify_attestation(att)


def test_popw_record_created():
    popw = PoPWRecord()
    traj = make_trajectory()
    record = popw.create_record("MISSION_001", traj, 95)
    assert record["on_chain_ready"]
    assert record["score"] == 95
    assert len(record["trajectory_hash"]) == 64


def test_popw_chain_format():
    popw = PoPWRecord()
    traj = make_trajectory()
    record = popw.create_record("MISSION_001", traj, 95)
    chain_str = popw.format_for_chain(record)
    parts = chain_str.split("|")
    assert parts[0] == "POPW"
    assert parts[1] == "MISSION_001"
    assert parts[3] == "95"
