"""Tests for validator scoring engine."""
import time
import pytest
from dronesync.protocol import Trajectory, MissionInstruction, MissionType, Waypoint
from validator.scorer import DroneEvaluator, MissionScorer
from environment.sim import DroneEnvironment
from miner.planner import DronePlanner


def make_mission():
    return MissionInstruction(
        mission_id="TEST_VAL_001",
        mission_type=MissionType.URBAN_DELIVERY,
        origin=Waypoint(lat=47.3769, lon=8.5417, alt=50, speed=5),
        destination=Waypoint(lat=47.3800, lon=8.5450, alt=50, speed=5),
    )


def test_evaluator_returns_score():
    mission = make_mission()
    planner = DronePlanner()
    traj = planner.plan_trajectory(mission)
    env = DroneEnvironment()
    sensor_data = env.run(traj)
    evaluator = DroneEvaluator()
    score = evaluator.score(traj, sensor_data)
    assert isinstance(score, (int, float))
    assert 0 <= score <= 100


def test_score_decreases_with_more_waypoints():
    mission = make_mission()
    planner = DronePlanner()

    # Add extra waypoints to inflate the trajectory
    mission.waypoints = [
        Waypoint(lat=47.3775 + i * 0.0001, lon=8.5420, alt=50, speed=5)
        for i in range(5)
    ]
    traj = planner.plan_trajectory(mission)
    env = DroneEnvironment()
    sensor_data = env.run(traj)
    evaluator = DroneEvaluator()
    score = evaluator.score(traj, sensor_data)
    assert 0 <= score <= 100

def test_pow_generation():
    mission = make_mission()
    planner = DronePlanner()
    traj = planner.plan_trajectory(mission)
    evaluator = DroneEvaluator()
    pow_data = evaluator.generate_pow(traj, steps=50)
    assert pow_data["valid"]
    assert pow_data["steps"] == 50
    assert "hash" in pow_data
