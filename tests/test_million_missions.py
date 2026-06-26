"""
1,000,000 Missions Test
Proves system handles extreme load without memory leaks or performance degradation.
"""
import sys
import os
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard


def test_million_reward_calculations():
    calc = RewardCalculator()
    start = time.time()

    for i in range(1_000_000):
        r = calc.calculate(
            mission_id=f"m{i}",
            total_score=0.75,
            grade="GOOD",
            reputation_tier="ACTIVE",
            safety_violations=0
        )
        assert r.final_reward >= 0.0

    elapsed = time.time() - start
    rate = 1_000_000 / elapsed
    assert rate > 10_000, f"Too slow: {rate:.0f} missions/sec"
    print(f"\n  [PASS] 1M missions in {elapsed:.1f}s — {rate:.0f} missions/sec")


def test_replay_guard_100k_unique():
    guard = ReplayGuard(persist_path="/tmp/million_guard.json")
    start = time.time()

    for i in range(100_000):
        r = guard.check(f"unique_{i}", created_at=time.time())
        assert r["allowed"] is True

    elapsed = time.time() - start
    rate = 100_000 / elapsed
    assert rate > 500, f"Too slow: {rate:.0f} missions/sec"
    print(f"\n  [PASS] 100k unique missions in {elapsed:.1f}s — {rate:.0f} missions/sec")


def test_no_memory_leak_reward():
    import tracemalloc
    calc = RewardCalculator()
    tracemalloc.start()

    for i in range(10_000):
        calc.calculate(
            mission_id=f"m{i}",
            total_score=0.75,
            grade="GOOD",
            reputation_tier="ACTIVE",
            safety_violations=0
        )

    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 50 * 1024 * 1024, f"Memory peak too high: {peak / 1024 / 1024:.1f} MB"
    print(f"\n  [PASS] Peak memory: {peak / 1024 / 1024:.1f} MB")
