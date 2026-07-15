"""Tests for MissionPipeline -- the canonical mission-to-PoPW flow.

No test previously covered this module at all, which is how a KeyError
(pipeline.py referencing "reputation_score" while DroneReputation.get_status()
returns "score") went unnoticed: it broke every real run through
DroneNavSynapseHandler (used by the dashboard and any real miner flow),
since MissionPipeline is always constructed there with a populated
drone_reputations dict.
"""
import time
from dronesync.pipeline import MissionPipeline
from dronesync.protocol import MissionInstruction, MissionType, Waypoint, Trajectory, SensorData
from dronesync.reputation import DroneReputation


def make_mission():
    return MissionInstruction(
        mission_id="TEST_MISSION_001",
        mission_type=MissionType.URBAN_DELIVERY,
        origin=Waypoint(lat=47.3769, lon=8.5417, alt=50),
        destination=Waypoint(lat=47.3820, lon=8.5460, alt=50),
    )


def make_trajectory():
    base = int(time.time())
    return Trajectory(
        positions=[[47.3769 + i * 0.001, 8.5417 + i * 0.001, 50.0, base + i * 5] for i in range(5)],
        velocities=[5.0] * 5,
        timestamps=[base + i * 5 for i in range(5)],
        metadata={"planner_steps": [], "steps_hash": "abc123"},
    )


def make_sensor_data():
    return SensorData(
        lidar_points=[[1.0, 2.0, 3.0]],
        camera_detections=[{"object": "tree", "confidence": 0.9}],
        imu_data={"pitch": 0.0, "roll": 0.0, "yaw": 0.0},
        timestamp=int(time.time()),
    )


def test_pipeline_run_with_reputation_completes_successfully():
    """Regression test: passing a real DroneReputation must not crash the
    pipeline with a KeyError on the reputation status dict."""
    drone_id = "DRONE_PIPELINE_TEST"
    reputation = DroneReputation(drone_id=drone_id)
    pipeline = MissionPipeline(drone_ids=[drone_id], drone_reputations={drone_id: reputation})

    result = pipeline.run(
        make_mission(), make_trajectory(), make_sensor_data(), score=90,
        executing_drone_id=drone_id,
    )

    assert result["status"] in ("SUCCESS", "FAILED")
    assert "checks" in result
    assert result["reputation"] is not None
    assert result["reputation"]["score"] >= 0


def test_pipeline_updates_reputation_score_after_run():
    drone_id = "DRONE_PIPELINE_TEST_2"
    reputation = DroneReputation(drone_id=drone_id)
    before = reputation.get_status()["missions_count"]
    pipeline = MissionPipeline(drone_ids=[drone_id], drone_reputations={drone_id: reputation})

    pipeline.run(make_mission(), make_trajectory(), make_sensor_data(), score=90,
                  executing_drone_id=drone_id)

    after = reputation.get_status()["missions_count"]
    assert after == before + 1


def test_pipeline_without_reputation_still_works():
    pipeline = MissionPipeline(drone_ids=["DRONE_NOREP"])
    result = pipeline.run(make_mission(), make_trajectory(), make_sensor_data(), score=90)
    assert result["reputation"] is None
    assert "pipeline_hash" in result
