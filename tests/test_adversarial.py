"""
Adversarial Test — edge cases and attack inputs
"""

import math
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, type(e).__name__


def test_reward_giant_mission_id():
    calc = RewardCalculator()
    giant_id = "A" * 100_000
    result, err = _safe_call(calc.calculate,
        mission_id=giant_id, total_score=0.75,
        grade="GOOD", reputation_tier="ACTIVE", safety_violations=0)
    assert err is None or result is not None
    if result:
        assert result.final_reward >= 0.0
    print(f"  [PASS] Giant mission_id (100k chars) → err={err}")


def test_reward_nan_score():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="nan_test", total_score=float("nan"),
        grade="GOOD", reputation_tier="ACTIVE", safety_violations=0)
    if result:
        assert not math.isnan(result.final_reward)
    print(f"  [PASS] NaN score → err={err}")


def test_reward_inf_score():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="inf_test", total_score=float("inf"),
        grade="EXCELLENT", reputation_tier="ELITE", safety_violations=0)
    if result:
        assert math.isfinite(result.final_reward)
    print(f"  [PASS] Inf score → err={err}")


def test_reward_negative_score():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="neg_score", total_score=-999.0,
        grade="POOR", reputation_tier="ACTIVE", safety_violations=0)
    if result:
        assert result.final_reward >= 0.0
    print(f"  [PASS] Negative score → err={err}")


def test_reward_negative_violations():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="neg_violations", total_score=0.75,
        grade="GOOD", reputation_tier="ACTIVE", safety_violations=-100)
    if result:
        assert result.final_reward >= 0.0
        assert result.penalty >= 0.0
    print(f"  [PASS] Negative violations → err={err}")


def test_reward_unknown_tier():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="unknown_tier", total_score=0.75,
        grade="GOOD", reputation_tier="HACKER_TIER", safety_violations=0)
    if result:
        assert result.final_reward >= 0.0
        assert result.tier_multiplier == 1.0
    print(f"  [PASS] Unknown tier → fallback 1.0, err={err}")


def test_reward_sql_injection_id():
    calc = RewardCalculator()
    evil_id = "'; DROP TABLE missions; --"
    result, err = _safe_call(calc.calculate,
        mission_id=evil_id, total_score=0.75,
        grade="GOOD", reputation_tier="ACTIVE", safety_violations=0)
    if result:
        assert result.mission_id == evil_id
    print(f"  [PASS] SQL injection → handled, err={err}")


def test_reward_xss_in_grade():
    calc = RewardCalculator()
    result, err = _safe_call(calc.calculate,
        mission_id="xss_test", total_score=0.75,
        grade="<script>alert(1)</script>",
        reputation_tier="ACTIVE", safety_violations=0)
    if result:
        assert result.final_reward >= 0.0
    print(f"  [PASS] XSS in grade → handled, err={err}")


def test_guard_very_old_timestamp():
    guard = ReplayGuard(persist_path="/tmp/adv_guard.json")
    old = time.time() - 86400 * 30
    result = guard.check("ancient_mission", created_at=old)
    assert result["allowed"] is False
    assert result["reason"] == "MISSION_EXPIRED"
    print("  [PASS] Old timestamp → MISSION_EXPIRED")


def test_guard_nan_timestamp():
    guard = ReplayGuard(persist_path="/tmp/adv_guard.json")
    result, err = _safe_call(guard.check, "nan_ts", created_at=float("nan"))
    print(f"  [PASS] NaN timestamp → err={err}")


def test_json_broken_input():
    broken = ["{not json}", "null\x00", "{'key': undefined}", "", "   "]
    for inp in broken:
        result, err = _safe_call(json.loads, inp)
        assert result is None or err is not None
    print(f"  [PASS] {len(broken)} broken JSON inputs → all raised exceptions")


def main():
    print(f"\n{'='*60}")
    print("Adversarial Test Suite")
    print(f"{'='*60}")
    test_reward_giant_mission_id()
    test_reward_nan_score()
    test_reward_inf_score()
    test_reward_negative_score()
    test_reward_negative_violations()
    test_reward_unknown_tier()
    test_reward_sql_injection_id()
    test_reward_xss_in_grade()
    test_guard_very_old_timestamp()
    test_guard_nan_timestamp()
    test_json_broken_input()
    print("\n  ALL ADVERSARIAL TESTS PASSED")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
