"""Tests for MAVLink adapter — no real drone required."""

import time
import pytest
from dronesync.mavlink_adapter import MAVLinkAdapter, TelemetryFrame


def _make_adapter_with_frames(n: int = 10) -> MAVLinkAdapter:
    adapter = MAVLinkAdapter.__new__(MAVLinkAdapter)
    adapter.connection_string = "test"
    adapter._connected = False
    adapter._mav = None

    frames = []
    base_ts = time.time()
    for i in range(n):
        f = TelemetryFrame()
        f.timestamp = base_ts + i * 0.2
        f.lat = 50.4501 + i * 0.0001
        f.lon = 30.5234 + i * 0.0001
        f.alt = 50.0 + i * 0.5
        f.vx = 2.0
        f.vy = 1.0
        f.vz = 0.1
        f.roll = 0.01
        f.pitch = 0.02
        f.yaw = 1.57
        f.battery_voltage = 11.8 - i * 0.01
        f.battery_remaining = 90 - i
        f.armed = True
        frames.append(f)

    adapter._frames = frames
    return adapter


def test_trajectory_shape():
    adapter = _make_adapter_with_frames(10)
    traj = adapter._to_trajectory()
    assert len(traj.positions) == 10
    assert len(traj.velocities) == 10
    assert len(traj.timestamps) == 10


def test_trajectory_positions_valid():
    adapter = _make_adapter_with_frames(5)
    traj = adapter._to_trajectory()
    for pos in traj.positions:
        lat, lon, alt, ts = pos
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        assert 0 <= alt <= 500


def test_trajectory_metadata():
    adapter = _make_adapter_with_frames(10)
    traj = adapter._to_trajectory()
    assert traj.metadata["source"] == "mavlink"
    assert traj.metadata["frame_count"] == 10
    assert traj.metadata["max_altitude"] > 0
    assert traj.metadata["avg_battery"] > 0


def test_sensor_data_imu():
    adapter = _make_adapter_with_frames(5)
    sensor = adapter._to_sensor_data()
    assert sensor.imu_data["source"] == "mavlink_real"
    assert len(sensor.imu_data["samples"]) == 5
    assert sensor.imu_data["armed_frames"] == 5
    assert sensor.imu_data["total_frames"] == 5


def test_sensor_data_battery():
    adapter = _make_adapter_with_frames(5)
    sensor = adapter._to_sensor_data()
    battery = sensor.imu_data["battery"]
    assert len(battery) == 5
    for b in battery:
        assert 0 <= b["remaining_pct"] <= 100


def test_empty_frames():
    adapter = MAVLinkAdapter.__new__(MAVLinkAdapter)
    adapter._frames = []
    adapter.connection_string = "test"
    traj = adapter._to_trajectory()
    sensor = adapter._to_sensor_data()
    assert traj.positions == []
    assert sensor.imu_data == {}


def test_velocity_calculated():
    adapter = _make_adapter_with_frames(3)
    traj = adapter._to_trajectory()
    for v in traj.velocities:
        assert v >= 0


def test_frame_count_property():
    adapter = _make_adapter_with_frames(7)
    assert adapter.frame_count == 7


def test_is_connected_false():
    adapter = MAVLinkAdapter("udp:127.0.0.1:14550")
    assert adapter.is_connected is False
