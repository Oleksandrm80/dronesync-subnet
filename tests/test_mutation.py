"""
Real Flight Mutation Test
Proves that mutating GPS/timestamp/battery invalidates PoPW proof.
"""
import copy
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.mavlink_emulator import MAVLinkEmulator, telemetry_to_score


def make_proof(frames: list) -> str:
    """SHA256 hash of telemetry — PoPW fingerprint."""
    data = json.dumps(frames, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def verify(frames: list, original_proof: str) -> bool:
    return make_proof(frames) == original_proof


def test_valid_flight_passes():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)
    assert verify(frames, proof), "Original flight must pass verification"


def test_mutate_gps_invalidates_proof():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)

    mutated = copy.deepcopy(frames)
    mutated[10]["lat"] += 1.0  # teleport drone

    assert not verify(mutated, proof), "Mutated GPS must invalidate proof"


def test_mutate_timestamp_invalidates_proof():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)

    mutated = copy.deepcopy(frames)
    mutated[5]["timestamp"] += 9999.0  # shift time forward

    assert not verify(mutated, proof), "Mutated timestamp must invalidate proof"


def test_mutate_battery_invalidates_proof():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)

    mutated = copy.deepcopy(frames)
    mutated[50]["battery_pct"] = 100.0  # fake full battery throughout

    assert not verify(mutated, proof), "Mutated battery must invalidate proof"


def test_mutate_altitude_invalidates_proof():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)

    mutated = copy.deepcopy(frames)
    for f in mutated:
        f["alt"] = 1000.0  # fake altitude

    assert not verify(mutated, proof), "Mutated altitude must invalidate proof"


def test_score_drops_after_gps_mutation():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    original_score = telemetry_to_score(frames)

    mutated = copy.deepcopy(frames)
    for f in mutated:
        f["gps_fix"] = 0  # no GPS fix
        f["satellites"] = 0

    mutated_score = telemetry_to_score(mutated)
    assert mutated_score["total_score"] < original_score["total_score"], \
        "GPS loss must reduce score"


def test_full_mutation_suite():
    emulator = MAVLinkEmulator()
    frames = emulator.run_mission(duration_ticks=100)
    proof = make_proof(frames)

    mutations = [
        ("lat+1.0",       lambda f: f.__setitem__("lat", f["lat"] + 1.0)),
        ("lon+1.0",       lambda f: f.__setitem__("lon", f["lon"] + 1.0)),
        ("battery=100",   lambda f: f.__setitem__("battery_pct", 100.0)),
        ("timestamp+999", lambda f: f.__setitem__("timestamp", f["timestamp"] + 999)),
        ("alt=0",         lambda f: f.__setitem__("alt", 0.0)),
        ("speed=0",       lambda f: f.__setitem__("speed_ms", 0.0)),
    ]

    for name, mutate_fn in mutations:
        mutated = copy.deepcopy(frames)
        mutate_fn(mutated[10])
        assert not verify(mutated, proof), f"Mutation '{name}' must invalidate proof"
