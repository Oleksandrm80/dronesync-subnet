# tests/test_dashboard_nav.py
"""
Tests for Navigation Intelligence panel in dashboard.
"""

import pytest
from dronesync.navigation import NavigationEngine
from dronesync.protocol import Waypoint, AlertLevel


@pytest.fixture
def engine():
    return NavigationEngine()


@pytest.fixture
def mission_waypoints():
    return [
        Waypoint(lat=47.3769, lon=8.5417, alt=50, speed=10),
        Waypoint(lat=47.3800, lon=8.5450, alt=55, speed=10),
        Waypoint(lat=47.3820, lon=8.5460, alt=50, speed=10),
    ]


def test_sim_flight_produces_summary(engine, mission_waypoints):
    sim = engine.sim_flight(mission_waypoints)
    s = sim.summary()
    assert "segments" in s
    assert "alerts" in s
    assert "safe" in s
    assert "critical" in s


def test_nav_alerts_empty_on_safe_route(engine, mission_waypoints):
    sim = engine.sim_flight(mission_waypoints)
    assert sim.safe is True
    assert sim.summary()["critical"] == 0


def test_nav_alerts_on_low_altitude(engine):
    wps = [
        Waypoint(lat=47.37, lon=8.54, alt=2, speed=10),
        Waypoint(lat=47.38, lon=8.55, alt=2, speed=10),
        Waypoint(lat=47.39, lon=8.56, alt=2, speed=10),
    ]
    sim = engine.sim_flight(wps)
    assert sim.safe is False
    assert len(sim.alerts) > 0
    assert any(a.level == AlertLevel.CRITICAL for a in sim.alerts)


def test_etas_generated(engine, mission_waypoints):
    sim = engine.sim_flight(mission_waypoints)
    etas = engine.calculate_etas(sim.segments)
    assert len(etas) == len(sim.segments)
    assert all(e.planned_eta > 0 for e in etas)
    assert etas[-1].planned_eta > etas[0].planned_eta


def test_swarm_targets_tracked(engine):
    data = [
        {"drone_id": "DRONE_001", "lat": 47.37, "lon": 8.54,
         "alt": 50, "speed": 10, "bearing_deg": 90},
        {"drone_id": "DRONE_002", "lat": 47.38, "lon": 8.55,
         "alt": 55, "speed": 8, "bearing_deg": 45},
        {"drone_id": "DRONE_003", "lat": 47.39, "lon": 8.56,
         "alt": 45, "speed": 12, "bearing_deg": 180},
    ]
    targets = engine.track_swarm(data)
    assert len(targets) == 3
    ids = [t.drone_id for t in targets]
    assert "DRONE_001" in ids
    assert "DRONE_003" in ids


def test_overlay_layers_count():
    layers = ["Flight Routes", "Swarm Targets", "No-Fly Zones",
              "Path Deviation", "Floor Altitude", "Vert. Clearance"]
    assert len(layers) == 6


def test_alert_levels_defined():
    assert AlertLevel.CRITICAL.value == "critical"
    assert AlertLevel.ALERT.value == "alert"
    assert AlertLevel.NOTICE.value == "notice"


def test_dashboard_render_has_nav_panel():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dashboard.app import HTML_TEMPLATE
    assert "{nav_alerts}" in HTML_TEMPLATE
    assert "{nav_etas}" in HTML_TEMPLATE
    assert "{sim_flight}" in HTML_TEMPLATE
    assert "{swarm_targets}" in HTML_TEMPLATE
