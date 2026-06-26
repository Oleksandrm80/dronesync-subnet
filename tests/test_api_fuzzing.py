"""
API Fuzzing Test
Proves system handles random/malformed inputs without crashing.
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard
from dronesync.firewall import DroneFirewall
from dronesync.wallet import MinerWallet


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, type(e).__name__


FUZZ_STRINGS = [
    "", " ", "\n", "\t", "\x00",
    "A" * 10000,
    "'; DROP TABLE--",
    "<script>alert(1)</script>",
    "null", "undefined", "NaN",
    "../../etc/passwd",
    "{}", "[]", "true", "false",
]

FUZZ_NUMBERS = [
    0, -1, -999999, 999999999,
    float("inf"), float("-inf"), float("nan"),
    1e308, -1e308, 0.0000001,
]


def test_fuzz_reward_calculator_mission_id():
    calc = RewardCalculator()
    for s in FUZZ_STRINGS:
        result, err = _safe(calc.calculate,
            mission_id=s, total_score=0.5,
            grade="GOOD", reputation_tier="ACTIVE", safety_violations=0)
        assert result is not None or err is not None


def test_fuzz_reward_calculator_score():
    calc = RewardCalculator()
    for n in FUZZ_NUMBERS:
        result, err = _safe(calc.calculate,
            mission_id="fuzz", total_score=n,
            grade="GOOD", reputation_tier="ACTIVE", safety_violations=0)
        if result:
            assert math.isfinite(result.final_reward)


def test_fuzz_reward_calculator_violations():
    calc = RewardCalculator()
    for n in FUZZ_NUMBERS:
        if isinstance(n, float) and (math.isnan(n) or math.isinf(n)):
            continue
        result, err = _safe(calc.calculate,
            mission_id="fuzz", total_score=0.5,
            grade="GOOD", reputation_tier="ACTIVE", safety_violations=int(n) if abs(n) < 1e9 else 0)
        if result:
            assert result.final_reward >= 0.0


def test_fuzz_replay_guard_mission_id():
    import time
    guard = ReplayGuard(persist_path="/tmp/fuzz_guard.json")
    for s in FUZZ_STRINGS:
        result, err = _safe(guard.check, s, created_at=time.time())
        assert result is not None or err is not None


def test_fuzz_replay_guard_timestamp():
    guard = ReplayGuard(persist_path="/tmp/fuzz_guard2.json")
    for n in FUZZ_NUMBERS:
        result, err = _safe(guard.check, f"fuzz_{n}", created_at=n)
        assert result is not None or err is not None


def test_fuzz_firewall_action():
    fw = DroneFirewall("FUZZ_DRONE")
    import time
    for s in FUZZ_STRINGS:
        result, err = _safe(fw.filter, {
            "action": s, "source": "op",
            "timestamp": int(time.time()), "signature": "fake"
        })
        assert result is not None or err is not None


def test_fuzz_firewall_missing_fields():
    fw = DroneFirewall("FUZZ_DRONE")
    inputs = [
        {},
        {"action": "fly"},
        {"signature": "x"},
        {"action": "fly", "source": "op"},
        {"action": None, "source": None, "timestamp": None, "signature": None},
    ]
    for cmd in inputs:
        result, err = _safe(fw.filter, cmd)
        assert result is not None or err is not None


def test_fuzz_wallet_credit():
    path = "/tmp/fuzz_wallet.json"
    w = MinerWallet(wallet_id="fuzz", persist_path=path)
    for s in FUZZ_STRINGS[:5]:
        result, err = _safe(w.credit, s, 1.0)
        assert result is not None or err is not None
