"""
Endurance Test
Simulates long-running operation — checks no degradation over time.
"""
import sys
import os
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard
from dronesync.wallet import MinerWallet


def test_no_performance_degradation():
    """Speed in last batch must be >= 50% of first batch."""
    calc = RewardCalculator()
    batch_size = 10_000
    batches = 5

    rates = []
    for b in range(batches):
        start = time.time()
        for i in range(batch_size):
            calc.calculate(
                mission_id=f"endurance_{b}_{i}",
                total_score=0.75,
                grade="GOOD",
                reputation_tier="ACTIVE",
                safety_violations=0
            )
        elapsed = time.time() - start
        rates.append(batch_size / elapsed)

    first_rate = rates[0]
    last_rate = rates[-1]
    degradation = (first_rate - last_rate) / first_rate * 100

    assert degradation < 50, f"Performance degraded {degradation:.1f}% over {batches} batches"
    print(f"\n  [PASS] First batch: {first_rate:.0f}/sec, Last: {last_rate:.0f}/sec, Degradation: {degradation:.1f}%")


def test_no_memory_growth():
    """Memory must not grow unboundedly over 50k operations."""
    import tracemalloc
    calc = RewardCalculator()

    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    for i in range(50_000):
        calc.calculate(
            mission_id=f"mem_{i}",
            total_score=0.75,
            grade="GOOD",
            reputation_tier="ACTIVE",
            safety_violations=0
        )

    gc.collect()
    snapshot2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot2.compare_to(snapshot1, "lineno")
    total_growth = sum(s.size_diff for s in stats)

    assert total_growth < 10 * 1024 * 1024, f"Memory grew too much: {total_growth / 1024 / 1024:.1f} MB"
    print(f"\n  [PASS] Memory growth: {total_growth / 1024:.1f} KB over 50k ops")


def test_replay_guard_no_degradation():
    """ReplayGuard speed must stay consistent over 50k unique missions."""
    guard = ReplayGuard(persist_path="/tmp/endurance_guard.json")
    batch_size = 10_000
    batches = 5
    rates = []

    for b in range(batches):
        start = time.time()
        for i in range(batch_size):
            guard.check(f"endurance_{b}_{i}", created_at=time.time())
        elapsed = time.time() - start
        rates.append(batch_size / elapsed)

    first_rate = rates[0]
    last_rate = rates[-1]
    degradation = (first_rate - last_rate) / first_rate * 100

    assert degradation < 80, f"ReplayGuard degraded {degradation:.1f}%"
    print(f"\n  [PASS] ReplayGuard: {first_rate:.0f}/sec → {last_rate:.0f}/sec, Degradation: {degradation:.1f}%")


def test_wallet_no_degradation():
    """Wallet credit speed must stay consistent over 1000 transactions."""
    path = "/tmp/endurance_wallet.json"
    if os.path.exists(path):
        os.remove(path)
    w = MinerWallet(wallet_id="endurance", persist_path=path)

    batch_size = 200
    batches = 5
    rates = []

    for b in range(batches):
        start = time.time()
        for i in range(batch_size):
            w.credit(f"m_{b}_{i}", 1.0)
        elapsed = time.time() - start
        rates.append(batch_size / elapsed)

    first_rate = rates[0]
    last_rate = rates[-1]
    degradation = (first_rate - last_rate) / first_rate * 100

    assert degradation < 80, f"Wallet degraded {degradation:.1f}%"
    print(f"\n  [PASS] Wallet: {first_rate:.0f}/sec → {last_rate:.0f}/sec, Degradation: {degradation:.1f}%")
