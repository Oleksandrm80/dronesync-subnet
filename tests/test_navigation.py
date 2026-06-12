# tests/test_navigation.py
"""
Tests for dronesync.navigation module.
"""

import pytest
from dronesync.protocol import Waypoint, AlertLevel
from dronesync.navigation import (
    NavigationEngine,
    PathDeviation,
    NavETA,
    SwarmTarget,
    haversine_distance,
    bearing,
)


@pytest.fixture
def engine():
    return NavigationEngine()


@pytest.fixture
def simple_waypoints():
    return [
        Waypoint(lat=47.3769, lon=8.5417, alt=50, speed=10),
        Waypoint(lat=47.3800, lon=8.5450, alt=55, speed=10),
        Waypoint(lat=47.3830, lon=8.5480, alt=50, speed=10),
    ]


def test_haversine_distance():
    d = haversine_distance(47.3769, 8.5417, 47.3820, 8.5460)
    assert 500 < d < 700


def test_haversine_same_point():
    assert haversine_distance(47.0, 8.0, 47.0, 8.0) == 0.0


def test_bearing_north():
    b = bearing(47.0, 8.0, 48.0, 8.0)
    assert abs(b) < 1.0


def test_build_segments(engine, simple_waypoints):
    segs = engine.build_segments(simple_waypoints)
    assert len(segs) == 2
    assert segs[0].segment_index == 0
    assert segs[1].segment_index == 1
    assert segs[0].planned_duration_s > 0


def test_floor_altitude_ok(engine, simple_waypoints):
    segs = engine.build_segments(simple_waypoints)
    alerts = engine.check_floor_altitude(segs)
    assert len(alerts) == 0


def test_floor_altitude_violation(engine):
    wps = [
        Waypoint(lat=47.37, lon=8.54, alt=5, speed=10),
        Waypoint(lat=47.38, lon=8.55, alt=5, speed=10),
    ]
    segs = engine.build_segments(wps)
    alerts = engine.check_floor_altitude(segs)
    assert len(alerts) == 1
    assert alerts[0].code == "FLOOR_ALT_VIOLATION"


def test_floor_altitude_critical(engine):
    wps = [
        Waypoint(lat=47.37, lon=8.54, alt=2, speed=10),
        Waypoint(lat=47.38, lon=8.55, alt=2, speed=10),
    ]
    segs = engine.build_segments(wps)
    alerts = engine.check_floor_altitude(segs)
    assert alerts[0].level == AlertLevel.CRITICAL


def test_path_deviation_within_limit(engine, simple_waypoints):
    devs = engine.calculate_path_deviation(simple_waypoints, simple_waypoints)
    assert all(not d.exceeded for d in devs)


def test_path_deviation_exceeded(engine):
    planned = [Waypoint(lat=47.37, lon=8.54, alt=50, speed=10)]
    actual = [Waypoint(lat=47.39, lon=8.56, alt=50, speed=10)]
    devs = engine.calculate_path_deviation(planned, actual)
    assert devs[0].exceeded


def test_calculate_etas(engine, simple_waypoints):
    segs = engine.build_segments(simple_waypoints)
    etas = engine.calculate_etas(segs)
    assert len(etas) == 2
    assert etas[1].planned_eta > etas[0].planned_eta


def test_sim_flight_safe(engine, simple_waypoints):
    sim = engine.sim_flight(simple_waypoints)
    assert sim.safe is True
    assert sim.summary()["segments"] == 2


def test_sim_flight_unsafe(engine):
    wps = [
        Waypoint(lat=47.37, lon=8.54, alt=2, speed=10),
        Waypoint(lat=47.38, lon=8.55, alt=2, speed=10),
    ]
    sim = engine.sim_flight(wps)
    assert sim.safe is False
    assert sim.summary()["critical"] >= 1


def test_track_swarm(engine):
    data = [
        {"drone_id": "D1", "lat": 47.37, "lon": 8.54, "alt": 50, "speed": 10, "bearing_deg": 90},
        {"drone_id": "D2", "lat": 47.38, "lon": 8.55, "alt": 55, "speed": 8, "bearing_deg": 45},
    ]
    targets = engine.track_swarm(data)
    assert len(targets) == 2
    assert targets[0].drone_id == "D1"


def test_swarm_target_distance():
    t = SwarmTarget(drone_id="D1", lat=47.37, lon=8.54, alt=50, speed=10, bearing_deg=0)
    d = t.distance_to(47.38, 8.55)
    assert d > 0


def test_nav_eta_delay():
    eta = NavETA(waypoint_index=1, planned_eta=1000.0, actual_eta=1050.0)
    assert eta.delay_s == 50.0


def test_path_deviation_severity():
    dev = PathDeviation(segment_index=0, deviation_m=120.0, max_allowed_m=50.0)
    assert dev.severity == AlertLevel.CRITICAL
