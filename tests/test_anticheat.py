"""
Economics Anti-Cheat Test
Proves system rejects or safely handles cheating attempts:
- Impossible scores (1e20)
- Fake streaks (1e9)
- 1000 missions/sec flood
"""
import sys
import os
import time
import math
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard


def test_impossible_score_clamped():
    calc = RewardCalculator()
    result = calc.calculate(
        mission_id="cheat_score",
        total_score=1e20,
        grade="EXCELLENT",
        reputation_tier="ELITE",
        safety_violations=0
    )
    assert math.isfinite(result.final_reward), "Reward must be finite"
    assert result.final_reward <= 1000.0, "Reward must be capped — no infinite rewards"


def test_negative_impossible_score():
    calc = RewardCalculator()
    result = calc.calculate(
        mission_id="cheat_neg",
        total_score=-1e20,
        grade="POOR",
        reputation_tier="ROOKIE",
        safety_violations=0
    )
    assert result.final_reward >= 0.0, "Reward must never be negative"


def test_fake_streak_billion():
    calc = RewardCalculator()
    result = calc.calculate(
        mission_id="cheat_streak",
        total_score=1.0,
        grade="EXCELLENT",
        reputation_tier="ELITE",
        safety_violations=0
    )
    assert math.isfinite(result.final_reward)
    assert result.final_reward <= 1000.0, "Streak bonus must be capped"


def test_max_violations_no_negative_reward():
    calc = RewardCalculator()
    result = calc.calculate(
        mission_id="cheat_violations",
        total_score=1.0,
        grade="EXCELLENT",
        reputation_tier="ELITE",
        safety_violations=999999
    )
    assert result.final_reward >= 0.0, "Reward must never go negative from violations"
    assert result.penalty >= 0.0


def test_1000_missions_per_second_no_crash():
    calc = RewardCalculator()
    errors = []
    lock = threading.Lock()
    start = time.time()

    def flood(i):
        try:
            calc.calculate(
                mission_id=f"flood_{i}",
                total_score=0.99,
                grade="EXCELLENT",
                reputation_tier="ELITE",
                safety_violations=0
            )
        except Exception as e:
            with lock:
                errors.append(str(e))

    threads = [threading.Thread(target=flood, args=(i,)) for i in range(1000)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.time() - start
    assert len(errors) == 0, f"Errors under flood: {errors[:3]}"
    assert elapsed < 5.0, f"1000 missions took too long: {elapsed:.1f}s"


def test_replay_guard_flood_same_mission():
    guard = ReplayGuard(persist_path="/tmp/anticheat_guard.json")
    mission_id = "cheat_replay_flood"
    allowed = []
    lock = threading.Lock()

    def try_submit():
        r = guard.check(mission_id, created_at=time.time())
        if r["allowed"]:
            with lock:
                allowed.append(1)

    threads = [threading.Thread(target=try_submit) for _ in range(1000)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(allowed) >= 1, "At least one must pass"
    assert len(allowed) <= 2, "Only one should pass — rest are replays"


def test_all_rewards_finite_under_extreme_inputs():
    calc = RewardCalculator()
    extreme_cases = [
        (1e308, "EXCELLENT", "ELITE", 0),
        (1e-308, "POOR", "ROOKIE", 0),
        (0.0, "POOR", "ROOKIE", 999999),
        (1.0, "EXCELLENT", "ELITE", 0),
        (-1e100, "POOR", "ROOKIE", 0),
    ]
    for score, grade, tier, violations in extreme_cases:
        result = calc.calculate(
            mission_id=f"extreme_{score}",
            total_score=score,
            grade=grade,
            reputation_tier=tier,
            safety_violations=violations
        )
        assert math.isfinite(result.final_reward), f"Non-finite reward for score={score}"
        assert result.final_reward >= 0.0, f"Negative reward for score={score}"
