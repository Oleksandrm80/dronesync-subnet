"""
Tests for POST /mission/run-live -- runs a mission from a real connected
drone (MAVLink/DJI/ROS2) instead of the simulator. DroneConnector is faked
since no real SITL/hardware is available in CI.
"""
import time
import pytest
from fastapi import HTTPException

import api
from dronesync.protocol import Trajectory, SensorData
from dronesync.auth import Client, ROLE_PERMISSIONS


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """slowapi's @limiter.limit requires a real starlette Request when
    enabled; calling the endpoint function directly (no HTTP round-trip)
    doesn't have one, so disable rate limiting for these unit tests."""
    api.limiter.enabled = False
    yield
    api.limiter.enabled = True


def make_client(role: str = "operator") -> Client:
    return Client(
        client_id="test_client_001",
        name="Test Client",
        role=role,
        api_key_hash="unused",
        active=True,
        created_at=time.time(),
        last_seen=time.time(),
        request_count=0,
        permissions=ROLE_PERMISSIONS[role],
    )


class FakeConnectorBase:
    def __init__(self, manufacturer="mavlink", connection="udp:127.0.0.1:14550"):
        self.manufacturer = manufacturer
        self.connection = connection
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True


def _trajectory_with_frames(n=5):
    base = time.time()
    positions = [[47.3769 + i * 0.0001, 8.5417 + i * 0.0001, 50.0, base + i] for i in range(n)]
    return Trajectory(
        positions=positions,
        velocities=[5.0] * n,
        timestamps=[int((base + i) * 1000) for i in range(n)],
        metadata={"source": "mavlink", "frame_count": n, "duration_s": n,
                  "avg_battery": 90, "max_altitude": 50.0, "max_speed": 5.0},
    )


def _empty_sensor_data():
    return SensorData(lidar_points=[], camera_detections=[], imu_data={"source": "mavlink_real"},
                       timestamp=int(time.time() * 1000))


class TestMissionRunLive:
    def test_success_returns_popw_from_real_telemetry(self, monkeypatch):
        class FakeConnector(FakeConnectorBase):
            def connect(self):
                return True

            def record_mission(self, duration_seconds, poll_hz):
                return _trajectory_with_frames(), _empty_sensor_data()

        monkeypatch.setattr("dronesync.drone_connector.DroneConnector", FakeConnector)

        req = api.LiveMissionRequest()
        result = api.run_mission_live(None, req, client=make_client())

        assert result["source"] == "mavlink"
        assert result["telemetry"]["frame_count"] == 5
        assert 0 <= result["score"] <= 100
        assert result["on_chain_ready"] is True
        assert "mission_id" in result

    def test_connection_failure_raises_502(self, monkeypatch):
        class FakeConnector(FakeConnectorBase):
            def connect(self):
                return False

            def record_mission(self, duration_seconds, poll_hz):
                raise AssertionError("should not be called when connect() fails")

        monkeypatch.setattr("dronesync.drone_connector.DroneConnector", FakeConnector)

        req = api.LiveMissionRequest()
        with pytest.raises(HTTPException) as exc_info:
            api.run_mission_live(None, req, client=make_client())
        assert exc_info.value.status_code == 502

    def test_no_telemetry_captured_raises_422(self, monkeypatch):
        class FakeConnector(FakeConnectorBase):
            def connect(self):
                return True

            def record_mission(self, duration_seconds, poll_hz):
                empty = Trajectory(positions=[], velocities=[], timestamps=[], metadata={})
                return empty, _empty_sensor_data()

        monkeypatch.setattr("dronesync.drone_connector.DroneConnector", FakeConnector)

        req = api.LiveMissionRequest()
        with pytest.raises(HTTPException) as exc_info:
            api.run_mission_live(None, req, client=make_client())
        assert exc_info.value.status_code == 422

    def test_disconnect_called_even_on_recording_failure(self, monkeypatch):
        connectors = []

        class FakeConnector(FakeConnectorBase):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                connectors.append(self)

            def connect(self):
                return True

            def record_mission(self, duration_seconds, poll_hz):
                raise RuntimeError("telemetry link dropped")

        monkeypatch.setattr("dronesync.drone_connector.DroneConnector", FakeConnector)

        req = api.LiveMissionRequest()
        with pytest.raises(HTTPException) as exc_info:
            api.run_mission_live(None, req, client=make_client())
        assert exc_info.value.status_code == 502
        assert connectors[0].disconnected is True

    def test_invalid_manufacturer_rejected_by_validation(self):
        with pytest.raises(ValueError):
            api.LiveMissionRequest(manufacturer="parrot_ar_drone")

    def test_duration_capped_at_60_seconds(self):
        with pytest.raises(ValueError):
            api.LiveMissionRequest(duration_seconds=120)
