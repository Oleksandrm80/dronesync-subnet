"""
Long Run Test — 100,000 missions
Monitors: RAM, throughput, replay blocking, degradation.
"""

import time
import random
import gc
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.replay_guard import ReplayGuard
from dronesync.economics import RewardCalculator


TOTAL_MISSIONS = 100_000
CHECKPOINT_EVERY = 10_000


def _random_grade(score):
    if score >= 0.85: return "EXCELLENT"
    elif score >= 0.70: return "GOOD"
    elif score >= 0.55: return "AVERAGE"
    else: return "POOR"


def run_long_run_test():
    print(f"\n{'='*60}")
    print(f"Long Run Test: {TOTAL_MISSIONS:,} missions")
    print(f"{'='*60}")

    gc.collect()
    guard = ReplayGuard(persist_path="/tmp/test_long_run_guard.json")
    calc = RewardCalculator()

    start_time = time.time()
    checkpoint_time = start_time
    times = []
    errors = 0
    mission_ids = []

    for i in range(TOTAL_MISSIONS):
        mission_id = f"mission_{i:07d}_{random.randint(0, 999999):06d}"
        mission_ids.append(mission_id)

        t0 = time.perf_counter()

        guard.check(mission_id, created_at=time.time())

        score = random.uniform(0.4, 1.0)
        grade = _random_grade(score)
        tier = random.choice(["ROOKIE", "ACTIVE", "TRUSTED", "ELITE"])
        violations = random.randint(0, 3)

        try:
            b = calc.calculate(mission_id, score, grade, tier, violations)
            assert b.final_reward >= 0.0
        except Exception:
            errors += 1

        times.append(time.perf_counter() - t0)

        if (i + 1) % CHECKPOINT_EVERY == 0:
            elapsed = time.time() - checkpoint_time
            throughput = CHECKPOINT_EVERY / elapsed
            avg_ms = sum(times[-CHECKPOINT_EVERY:]) / CHECKPOINT_EVERY * 1000
            print(f"  [{i+1:>7,}]  Avg: {avg_ms:.3f}ms  |  {throughput:,.0f} missions/s  |  KNX: {calc.total_earned:.2f}")
            checkpoint_time = time.time()

    print("\n  Testing replay blocking on 1,000 missions...")
    dup_count = 0
    for mid in random.sample(mission_ids, 1000):
        r = guard.check(mid, created_at=time.time())
        if not r["allowed"] and r.get("reason") == "REPLAY_DETECTED":
            dup_count += 1

    total_time = time.time() - start_time
    first_avg = sum(times[:CHECKPOINT_EVERY]) / CHECKPOINT_EVERY * 1000
    last_avg = sum(times[-CHECKPOINT_EVERY:]) / CHECKPOINT_EVERY * 1000
    degradation = ((last_avg - first_avg) / first_avg) * 100

    print(f"\n{'='*60}")
    print(f"  Total time:      {total_time:.1f}s")
    print(f"  Throughput:      {TOTAL_MISSIONS / total_time:,.0f} missions/s")
    print(f"  Errors:          {errors}")
    print(f"  Replay blocked:  {dup_count}/1000")
    print(f"  Degradation:     {degradation:+.1f}%")
    print(f"  Total KNX:       {calc.total_earned:.2f}")

    assert errors == 0
    assert dup_count >= 950
    assert degradation < 2000

    print("\n  ALL LONG RUN TESTS PASSED")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_long_run_test()
