"""Tests for DronePlanner and AIPlanner."""
import pytest
from dronesync.protocol import MissionInstruction, MissionType, Waypoint, Trajectory
from miner.planner import DronePlanner, AIPlanner


def make_mission(origin=(47.3769, 8.5417), destination=(47.3800, 8.5450)):
    return MissionInstruction(
        mission_id="TEST_001",
        mission_type=MissionType.URBAN_DELIVERY,
        origin=Waypoint(lat=origin[0], lon=origin[1], alt=50, speed=5),
        destination=Waypoint(lat=destination[0], lon=destination[1], alt=50, speed=5),
        waypoints=[Waypoint(lat=47.3780, lon=8.5430, alt=50, speed=5)],
    )


def test_planner_returns_trajectory():
    planner = DronePlanner()
    mission = make_mission()
    traj = planner.plan_trajectory(mission)
    assert isinstance(traj, Trajectory)
    assert len(traj.positions) >= 2
    assert len(traj.velocities) == len(traj.positions)
    assert len(traj.timestamps) == len(traj.positions)


def test_trajectory_starts_at_origin():
    planner = DronePlanner()
    mission = make_mission(origin=(47.3769, 8.5417))
    traj = planner.plan_trajectory(mission)
    assert traj.positions[0][0] == pytest.approx(47.3769)
    assert traj.positions[0][1] == pytest.approx(8.5417)


def test_trajectory_ends_at_destination():
    planner = DronePlanner()
    mission = make_mission(destination=(47.3800, 8.5450))
    traj = planner.plan_trajectory(mission)
    assert traj.positions[-1][0] == pytest.approx(47.3800)
    assert traj.positions[-1][1] == pytest.approx(8.5450)


def test_timestamps_monotonically_increasing():
    planner = DronePlanner()
    traj = planner.plan_trajectory(make_mission())
    for i in range(1, len(traj.timestamps)):
        assert traj.timestamps[i] > traj.timestamps[i - 1]


def test_ai_planner_learns_from_score():
    planner = AIPlanner()
    mission = make_mission()
    initial_efficiency = planner.learned_weights["efficiency"]
    planner.plan_trajectory(mission)
    planner.learn_from_score(95)
    assert planner.learned_weights["efficiency"] > initial_efficiency


def test_ai_planner_increases_safety_on_low_score():
    planner = AIPlanner()
    mission = make_mission()
    planner.plan_trajectory(mission)
    initial_safety = planner.learned_weights["safety"]
    planner.learn_from_score(50)
    assert planner.learned_weights["safety"] > initial_safety


def test_sensor_data_generated():
    planner = DronePlanner()
    mission = make_mission()
    traj = planner.plan_trajectory(mission)
    sensor = planner.generate_sensor_data(traj)
    assert len(sensor.lidar_points) == 50
    assert sensor.imu_data is not None
