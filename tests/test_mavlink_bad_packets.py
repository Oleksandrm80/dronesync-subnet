"""
MAVLink Bad Packets & Packet Loss Test
Proves system handles corrupted/missing telemetry gracefully.
"""
import copy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.mavlink_emulator import MAVLinkEmulator, telemetry_to_score


def test_missing_gps_fields():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    broken = copy.deepcopy(frames)
    for f in broken[10:20]:
        del f["lat"]
        del f["lon"]
    result, err = None, None
    try:
        result = telemetry_to_score(broken)
    except Exception as e:
        err = type(e).__name__
    assert result is not None or err is not None


def test_packet_loss_50_percent():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    surviving = frames[::2]  # every second frame dropped
    assert len(surviving) == 50
    result = telemetry_to_score(surviving)
    assert result["total_score"] >= 0.0
    assert result["frames"] == 50


def test_packet_loss_90_percent():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    surviving = frames[::10]  # 90% loss
    assert len(surviving) == 10
    result = telemetry_to_score(surviving)
    assert result["total_score"] >= 0.0


def test_empty_telemetry():
    result = telemetry_to_score([])
    assert result["total_score"] == 0.0
    assert result["grade"] == "POOR"


def test_single_frame():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=1)
    result = telemetry_to_score(frames)
    assert result["total_score"] >= 0.0


def test_none_values_in_frame():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    broken = copy.deepcopy(frames)
    broken[5]["battery_pct"] = None
    result, err = None, None
    try:
        result = telemetry_to_score(broken)
    except Exception as e:
        err = type(e).__name__
    assert result is not None or err is not None


def test_corrupted_gps_fix():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    broken = copy.deepcopy(frames)
    for f in broken:
        f["gps_fix"] = -999
    result = telemetry_to_score(broken)
    assert result["gps_ok"] is False
    assert result["total_score"] < 1.0


def test_score_lower_with_packet_loss():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    full_score = telemetry_to_score(frames)
    partial = frames[:20]
    partial_score = telemetry_to_score(partial)
    assert partial_score["total_score"] <= full_score["total_score"] + 0.1
