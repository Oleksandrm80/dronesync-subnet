"""Tests for energy optimizer and weather modules."""
from miner.energy import BatteryModel, EnergyOptimizer
from miner.weather import WeatherService, WeatherCondition, WeatherImpactAnalyzer


# --- BatteryModel ---

def test_battery_consumption_increases_with_wind():
    battery = BatteryModel()
    low = battery.consumption_per_km(speed_ms=10, wind_ms=0)
    high = battery.consumption_per_km(speed_ms=10, wind_ms=10)
    assert high > low


def test_range_decreases_with_payload():
    light = BatteryModel(payload_kg=0.1)
    heavy = BatteryModel(payload_kg=2.0)
    assert light.estimate_range_km() > heavy.estimate_range_km()


# --- EnergyOptimizer ---

def test_analyze_trajectory_feasible():
    from dronesync.protocol import Trajectory
    import time
    base = int(time.time())
    traj = Trajectory(
        positions=[[47.3769 + i * 0.0001, 8.5417 + i * 0.0001, 50.0, base + i * 5]
                   for i in range(5)],
        velocities=[10.0] * 5,
        timestamps=[base + i * 5 for i in range(5)],
    )
    optimizer = EnergyOptimizer()
    result = optimizer.analyze_trajectory(traj.positions)
    assert result["mission_feasible"]
    assert result["battery_remaining_pct"] > 20
    assert result["total_distance_km"] > 0


def test_optimal_speed_is_reasonable():
    optimizer = EnergyOptimizer()
    speed = optimizer.optimal_speed(wind_ms=0)
    assert 5 <= speed <= 25


# --- WeatherService ---

def test_weather_returns_condition():
    service = WeatherService(lat=47.3769, lon=8.5417)
    cond = service.get_current()
    assert isinstance(cond, WeatherCondition)
    assert cond.wind_speed >= 0
    assert cond.visibility > 0


def test_flyable_on_calm_weather():
    cond = WeatherCondition(
        wind_speed=2.0, wind_dir=90, visibility=10000,
        precipitation="none", temperature=15
    )
    assert cond.is_flyable()
    assert cond.severity() == "CLEAR"


def test_not_flyable_in_storm():
    cond = WeatherCondition(
        wind_speed=20.0, wind_dir=90, visibility=300,
        precipitation="heavy", temperature=5
    )
    assert not cond.is_flyable()
    assert cond.severity() == "SEVERE"


def test_impact_analyzer():
    cond = WeatherCondition(
        wind_speed=4.0, wind_dir=180, visibility=8000,
        precipitation="none", temperature=12
    )
    positions = [[47.37 + i * 0.001, 8.54, 50, 0] for i in range(4)]
    analyzer = WeatherImpactAnalyzer()
    result = analyzer.analyze(cond, positions)
    assert result["flyable"]
    assert result["speed_factor"] <= 1.0
    assert result["energy_factor"] >= 1.0
