"""Tests for SwarmEnvironment.run_swarm()"""
from environment.sim import SwarmEnvironment


def _make_trajectory(origin, destination):
    mission = type("M", (), {
        "mission_id": "TEST_01",
        "origin": type("W", (), {"lat": origin[0], "lon": origin[1], "alt": 50, "speed": 5}),
        "destination": type("W", (), {"lat": destination[0], "lon": destination[1], "alt": 50, "speed": 5}),
        "waypoints": [],
        "mission_type": type("MT", (), {"value": "urban_delivery"}),
        "drone_count": 1,
        "payload_kg": 0.5,
    })
    from miner.planner import DronePlanner
    return DronePlanner().plan_trajectory(mission)


def test_run_swarm_returns_drone_keys():
    swarm = SwarmEnvironment(n_drones=2)
    t1 = _make_trajectory((0.0, 0.0), (0.01, 0.01))
    t2 = _make_trajectory((1.0, 1.0), (1.01, 1.01))
    result = swarm.run_swarm([t1, t2])
    assert "drone_0" in result
    assert "drone_1" in result


def test_run_swarm_no_conflict():
    swarm = SwarmEnvironment(n_drones=2)
    t1 = _make_trajectory((0.0, 0.0), (0.01, 0.01))
    t2 = _make_trajectory((1.0, 1.0), (1.01, 1.01))
    result = swarm.run_swarm([t1, t2])
    assert result["drone_0"]["conflicts_predicted"] == 0
    assert result["drone_1"]["conflicts_predicted"] == 0


def test_run_swarm_detects_conflict():
    swarm = SwarmEnvironment(n_drones=2)
    t1 = _make_trajectory((0.0, 0.0), (0.001, 0.001))
    t2 = _make_trajectory((0.0, 0.0), (0.001, 0.001))
    result = swarm.run_swarm([t1, t2])
    total = result["drone_0"]["conflicts_predicted"] + result["drone_1"]["conflicts_predicted"]
    assert total > 0


def test_run_swarm_three_drones():
    swarm = SwarmEnvironment(n_drones=3)
    t1 = _make_trajectory((0.0, 0.0), (0.01, 0.01))
    t2 = _make_trajectory((0.5, 0.5), (0.51, 0.51))
    t3 = _make_trajectory((1.0, 1.0), (1.01, 1.01))
    result = swarm.run_swarm([t1, t2, t3])
    assert len(result) == 3
