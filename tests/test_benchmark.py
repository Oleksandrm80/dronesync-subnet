"""
DroneSync -- Planner Benchmarks
Compares DronePlanner vs AIPlanner on speed and trajectory quality.
"""

import time
import math
import pytest
from dronesync.protocol import MissionInstruction, Waypoint, MissionType
from miner.planner import DronePlanner, AIPlanner


def make_mission(n_waypoints=3) -> MissionInstruction:
    origin = Waypoint(lat=50.4501, lon=30.5234, alt=50.0, speed=10.0)
    destination = Waypoint(lat=50.4700, lon=30.5500, alt=50.0, speed=10.0)
    step = 1.0 / (n_waypoints + 1)
    waypoints = [
        Waypoint(
            lat=50.4501 + (i + 1) * step * 0.02,
            lon=30.5234 + (i + 1) * step * 0.03,
            alt=50.0 + i * 2,
            speed=10.0
        )
        for i in range(n_waypoints)
    ]
    return MissionInstruction(
        mission_id=f"bench-{n_waypoints}wp",
        mission_type=MissionType.URBAN_DELIVERY,
        origin=origin,
        destination=destination,
        waypoints=waypoints,
    )


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class TestPlannerSpeed:
    def test_drone_planner_speed_small(self):
        planner = DronePlanner()
        mission = make_mission(3)
        t0 = time.time()
        traj = planner.plan_trajectory(mission)
        elapsed = time.time() - t0
        assert elapsed < 0.1, f"DronePlanner too slow: {elapsed:.3f}s"
        assert len(traj.positions) >= 2

    def test_ai_planner_speed_small(self):
        planner = AIPlanner()
        mission = make_mission(3)
        t0 = time.time()
        traj = planner.plan_trajectory(mission)
        elapsed = time.time() - t0
        assert elapsed < 0.1, f"AIPlanner too slow: {elapsed:.3f}s"
        assert len(traj.positions) >= 2

    def test_drone_planner_speed_large(self):
        planner = DronePlanner()
        mission = make_mission(20)
        t0 = time.time()
        _ = planner.plan_trajectory(mission)
        elapsed = time.time() - t0
        assert elapsed < 0.5, f"DronePlanner too slow on 20wp: {elapsed:.3f}s"

    def test_ai_planner_speed_large(self):
        planner = AIPlanner()
        mission = make_mission(20)
        t0 = time.time()
        _ = planner.plan_trajectory(mission)
        elapsed = time.time() - t0
        assert elapsed < 0.5, f"AIPlanner too slow on 20wp: {elapsed:.3f}s"


class TestTrajectoryCoverage:
    def test_all_waypoints_covered(self):
        planner = DronePlanner()
        mission = make_mission(5)
        traj = planner.plan_trajectory(mission)
        assert len(traj.positions) == 7

    def test_ai_all_waypoints_covered(self):
        planner = AIPlanner()
        mission = make_mission(5)
        traj = planner.plan_trajectory(mission)
        assert len(traj.positions) == 7

    def test_starts_at_origin(self):
        planner = DronePlanner()
        mission = make_mission(2)
        traj = planner.plan_trajectory(mission)
        assert traj.positions[0][0] == pytest.approx(mission.origin.lat)
        assert traj.positions[0][1] == pytest.approx(mission.origin.lon)

    def test_ends_near_destination(self):
        planner = DronePlanner()
        mission = make_mission(2)
        traj = planner.plan_trajectory(mission)
        last = traj.positions[-1]
        dist = haversine(last[0], last[1], mission.destination.lat, mission.destination.lon)
        assert dist < 10, f"Final position too far from destination: {dist:.1f}m"

    def test_timestamps_increasing(self):
        planner = DronePlanner()
        mission = make_mission(3)
        traj = planner.plan_trajectory(mission)
        for i in range(len(traj.timestamps) - 1):
            assert traj.timestamps[i] < traj.timestamps[i + 1]


class TestAIPlannerLearning:
    def test_learn_high_score_boosts_efficiency(self):
        planner = AIPlanner()
        eff_before = planner.learned_weights["efficiency"]
        planner.learn_from_score(95)
        assert planner.learned_weights["efficiency"] >= eff_before

    def test_learn_low_score_boosts_safety(self):
        planner = AIPlanner()
        safety_before = planner.learned_weights["safety"]
        planner.learn_from_score(60)
        assert planner.learned_weights["safety"] >= safety_before

    def test_weights_stay_normalized_after_learning(self):
        planner = AIPlanner()
        for score in [95, 60, 95, 60, 95]:
            planner.learn_from_score(score)
        total = sum(planner.learned_weights.values())
        assert total == pytest.approx(1.0, abs=0.05)

    def test_mission_history_grows(self):
        planner = AIPlanner()
        m1 = make_mission(2)
        m2 = make_mission(4)
        planner.plan_trajectory(m1)
        planner.plan_trajectory(m2)
        assert len(planner.mission_history) == 2


class TestComparativeBenchmark:
    def test_ai_safe_altitude(self):
        planner = AIPlanner()
        mission = make_mission(5)
        traj = planner.plan_trajectory(mission)
        for pos in traj.positions[1:]:
            assert pos[2] >= 25.0, f"Unsafe altitude: {pos[2]}m"

    def test_both_produce_metadata(self):
        dp = DronePlanner()
        ap = AIPlanner()
        mission = make_mission(3)
        t1 = dp.plan_trajectory(mission)
        t2 = ap.plan_trajectory(mission)
        assert "planner_version" in t1.metadata
        assert "planner_version" in t2.metadata
        assert t1.metadata["planner_version"] != t2.metadata["planner_version"]

    def test_drone_planner_has_steps_hash(self):
        planner = DronePlanner()
        mission = make_mission(2)
        traj = planner.plan_trajectory(mission)
        assert "steps_hash" in traj.metadata
        assert len(traj.metadata["steps_hash"]) == 64
