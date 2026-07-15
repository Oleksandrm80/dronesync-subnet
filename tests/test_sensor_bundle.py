"""Tests for SensorBundle — evidence packaging and tamper detection."""
from dronesync.protocol import Trajectory, SensorData
from dronesync.sensor_bundle import SensorBundle


def make_trajectory():
    return Trajectory(
        positions=[[47.3769, 8.5417, 50.0, 0], [47.3770, 8.5418, 50.0, 5]],
        velocities=[5.0, 5.0],
        timestamps=[0, 5],
        metadata={"planner_steps": ["plan", "execute"], "steps_hash": "abc"},
    )


def make_sensor_data():
    return SensorData(
        lidar_points=[[1.0, 2.0, 3.0]],
        camera_detections=[{"object": "tree", "confidence": 0.9}],
        imu_data={"pitch": 0.1, "roll": 0.0, "yaw": 1.2},
        timestamp=5,
    )


def make_popw_record():
    return {
        "mission_id": "M1",
        "trajectory_hash": "a" * 64,
        "score": 90,
        "attestation": {"attestation_id": "att1", "status": "VERIFIED", "signature": "sig123"},
    }


def test_pack_produces_valid_bundle():
    bundle = SensorBundle().pack("M1", make_trajectory(), make_sensor_data(), make_popw_record())
    assert bundle["mission_id"] == "M1"
    assert bundle["on_chain_ready"] is True
    assert "bundle_hash" in bundle


def test_verify_accepts_untampered_bundle():
    bundle = SensorBundle().pack("M1", make_trajectory(), make_sensor_data(), make_popw_record())
    result = SensorBundle().verify(bundle)
    assert result["valid"] is True
    assert result["mission_id"] == "M1"


def test_verify_rejects_tampered_bundle():
    bundle = SensorBundle().pack("M1", make_trajectory(), make_sensor_data(), make_popw_record())
    bundle["popw"]["score"] = 999
    result = SensorBundle().verify(bundle)
    assert result["valid"] is False
    assert result["reason"] == "bundle_hash_mismatch"


def test_pack_batch_summarizes_bundles():
    bundle1 = SensorBundle().pack("M1", make_trajectory(), make_sensor_data(), make_popw_record())
    bundle2 = SensorBundle().pack("M2", make_trajectory(), make_sensor_data(), make_popw_record())
    batch = SensorBundle().pack_batch([bundle1, bundle2])
    assert batch["batch_size"] == 2
    assert set(batch["mission_ids"]) == {"M1", "M2"}
    assert batch["on_chain_ready"] is True
