"""
tests/fuzz_mission.py

Fuzz testing for DroneSync core components.
Generates thousands of random inputs and checks for crashes.

Run:
    python3 tests/fuzz_mission.py
    python3 tests/fuzz_mission.py -runs=10000
"""

import sys
import os
import json
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import atheris

with atheris.instrument_imports():
    from dronesync.synapse import DroneNavSynapseHandler
    from dronesync.replay_guard import ReplayGuard
    from dronesync.validator_node import ValidatorNode


handler = DroneNavSynapseHandler()
replay = ReplayGuard(persist_path="/tmp/fuzz_replay")
validator = ValidatorNode("fuzz-validator", port=9999)


def fuzz_synapse(data: bytes):
    """Fuzz the synapse handler with random mission data."""
    fdp = atheris.FuzzedDataProvider(data)
    try:
        task = {
            "mission_id": fdp.ConsumeString(64),
            "waypoints": [
                [fdp.ConsumeFloat(), fdp.ConsumeFloat(), fdp.ConsumeFloat()]
                for _ in range(fdp.ConsumeIntInRange(0, 10))
            ],
            "battery": fdp.ConsumeFloat(),
            "created_at": fdp.ConsumeFloat(),
            "mission_type": fdp.ConsumeString(32),
        }
        result = handler.handle(task)
        # Must always return a dict
        assert isinstance(result, dict)
        # Must always have status
        assert "status" in result
        # Score must be in valid range if present
        if "score" in result and result["score"] is not None:
            assert 0 <= result["score"] <= 100 or result["score"] == 0
    except (ValueError, TypeError, KeyError):
        pass  # Expected for malformed input


def fuzz_replay_guard(data: bytes):
    """Fuzz ReplayGuard with random mission IDs."""
    fdp = atheris.FuzzedDataProvider(data)
    try:
        mission_id = fdp.ConsumeString(256)
        created_at = fdp.ConsumeFloat()

        result = replay.check(mission_id, created_at)
        assert isinstance(result, dict)
        assert "allowed" in result

        if result["allowed"]:
            replay.register(mission_id)
            # Second check must be rejected
            result2 = replay.check(mission_id, created_at)
            assert result2["allowed"] is False
    except (ValueError, TypeError, OverflowError):
        pass


def fuzz_validator(data: bytes):
    """Fuzz validator with random PoPW data."""
    fdp = atheris.FuzzedDataProvider(data)
    try:
        popw = {
            "mission_id": fdp.ConsumeString(64),
            "score": fdp.ConsumeFloat(),
            "computation_hash": fdp.ConsumeString(64),
            "constraints_satisfied": fdp.ConsumeBool(),
            "trajectory_positions": [
                [fdp.ConsumeFloat(), fdp.ConsumeFloat(),
                 fdp.ConsumeFloat(), fdp.ConsumeFloat()]
                for _ in range(fdp.ConsumeIntInRange(0, 20))
            ],
        }
        vote = validator._validate_popw(popw)
        assert isinstance(vote.accepted, bool)
        assert isinstance(vote.score, float)
        assert len(vote.signature) == 16
    except (ValueError, TypeError, OverflowError):
        pass


def fuzz_json_input(data: bytes):
    """Fuzz with raw JSON bytes — test JSON parsing robustness."""
    try:
        text = data.decode("utf-8", errors="replace")
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            handler.handle(parsed)
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        pass


def run_all_fuzzers(n_runs: int = 1000):
    """Run all fuzzers without atheris instrumentation (simple mode)."""
    import random
    import struct

    print(f"\n{'='*60}")
    print("DroneSync — Fuzz Testing")
    print(f"{'='*60}")

    fuzzers = [
        ("Synapse Handler", fuzz_synapse),
        ("ReplayGuard", fuzz_replay_guard),
        ("Validator", fuzz_validator),
        ("JSON Input", fuzz_json_input),
    ]

    for name, fuzzer in fuzzers:
        crashes = 0
        errors = 0
        print(f"\n[*] Fuzzing {name} ({n_runs} runs)...")
        for i in range(n_runs):
            # Generate random bytes
            size = random.randint(0, 256)
            data = bytes([random.randint(0, 255) for _ in range(size)])
            try:
                fuzzer(data)
            except SystemExit:
                pass
            except Exception as e:
                crashes += 1
                if crashes <= 3:
                    print(f"    ❌ CRASH: {type(e).__name__}: {e}")

        if crashes == 0:
            print(f"    ✅ No crashes in {n_runs} runs")
        else:
            print(f"    ⚠️  {crashes} crashes found")

    print(f"\n{'='*60}")
    print("✅ Fuzz testing complete")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    n_runs = 1000
    for arg in sys.argv[1:]:
        if arg.startswith("-runs="):
            n_runs = int(arg.split("=")[1])
    run_all_fuzzers(n_runs)
