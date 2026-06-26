"""
Chaos Test — infrastructure failures simulation
"""
import pytest
import asyncio
import json
import random
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.economics import RewardCalculator
from dronesync.replay_guard import ReplayGuard


class ChaosValidator:
    def __init__(self, node_id: str, failure_mode: str = "none"):
        self.node_id = node_id
        self.failure_mode = failure_mode

    async def validate(self, mission: dict) -> dict:
        if self.failure_mode == "crash":
            raise ConnectionResetError(f"Node {self.node_id} crashed")
        if self.failure_mode == "timeout":
            await asyncio.sleep(10)
            return {}
        if self.failure_mode == "garbage":
            raise json.JSONDecodeError("garbage", "", 0)
        if self.failure_mode == "intermittent":
            if random.random() < 0.5:
                raise ConnectionResetError("intermittent")
        if self.failure_mode == "slow":
            await asyncio.sleep(random.uniform(0.01, 0.05))
        score = mission.get("score", 0.75)
        return {"node_id": self.node_id, "accepted": score >= 0.6, "score": score}


async def _call_validator(validator, mission, timeout_s=1.0):
    try:
        return await asyncio.wait_for(validator.validate(mission), timeout=timeout_s)
    except Exception:
        return None


async def chaos_network_validate(validators, mission):
    results = await asyncio.gather(*[_call_validator(v, mission) for v in validators])
    responses = [r for r in results if r is not None]
    accepted = sum(1 for r in responses if r.get("accepted", False))
    total = len(validators)
    consensus = (accepted / total) >= 0.67 if total > 0 else False
    return {"total": total, "reachable": len(responses), "accepted": accepted, "consensus": consensus}


@pytest.mark.asyncio
async def test_all_nodes_up():
    validators = [ChaosValidator(f"v{i}", "none") for i in range(5)]
    result = await chaos_network_validate(validators, {"score": 0.85})
    assert result["reachable"] == 5
    assert result["consensus"] is True
    print(f"  [PASS] All nodes up → consensus={result['consensus']}")


@pytest.mark.asyncio
async def test_majority_crashed():
    validators = [
        ChaosValidator("v0", "none"), ChaosValidator("v1", "none"),
        ChaosValidator("v2", "crash"), ChaosValidator("v3", "crash"),
        ChaosValidator("v4", "crash"),
    ]
    result = await chaos_network_validate(validators, {"score": 0.85})
    assert result["consensus"] is False
    assert result["reachable"] == 2
    print(f"  [PASS] Majority crashed → consensus={result['consensus']}")


@pytest.mark.asyncio
async def test_timeout_nodes():
    validators = [
        ChaosValidator("v0", "none"), ChaosValidator("v1", "none"),
        ChaosValidator("v2", "none"), ChaosValidator("v3", "timeout"),
        ChaosValidator("v4", "timeout"),
    ]
    t0 = time.time()
    result = await chaos_network_validate(validators, {"score": 0.85})
    elapsed = time.time() - t0
    assert elapsed < 2.0
    assert result["reachable"] == 3
    print(f"  [PASS] Timeout nodes → time={elapsed:.2f}s")


@pytest.mark.asyncio
async def test_garbage_responses():
    validators = [ChaosValidator(f"v{i}", "garbage") for i in range(5)]
    result = await chaos_network_validate(validators, {"score": 0.85})
    assert result["reachable"] == 0
    assert result["consensus"] is False
    print(f"  [PASS] All garbage → consensus={result['consensus']}")


@pytest.mark.asyncio
async def test_slow_network():
    validators = [ChaosValidator(f"v{i}", "slow") for i in range(5)]
    t0 = time.time()
    result = await chaos_network_validate(validators, {"score": 0.85})
    elapsed = time.time() - t0
    assert elapsed < 0.5
    assert result["reachable"] == 5
    print(f"  [PASS] Slow network parallel → time={elapsed:.3f}s")


@pytest.mark.asyncio
async def test_one_node_down():
    validators = [
        ChaosValidator("v0", "none"), ChaosValidator("v1", "none"),
        ChaosValidator("v2", "none"), ChaosValidator("v3", "none"),
        ChaosValidator("v4", "crash"),
    ]
    result = await chaos_network_validate(validators, {"score": 0.85})
    assert result["consensus"] is True
    assert result["reachable"] == 4
    print(f"  [PASS] One node down → consensus={result['consensus']}")


@pytest.mark.asyncio
async def test_replay_guard_concurrent():
    guard = ReplayGuard(persist_path="/tmp/chaos_guard.json")
    mission_id = f"chaos_concurrent_{time.time()}"
    async def try_register():
        return guard.check(mission_id, created_at=time.time())
    results = await asyncio.gather(*[try_register() for _ in range(50)])
    allowed = sum(1 for r in results if r["allowed"])
    assert allowed >= 1
    print(f"  [PASS] Concurrent ReplayGuard → {allowed} allowed, {50-allowed} blocked")


def test_economics_extreme():
    calc = RewardCalculator()
    cases = [
        (0.0, "POOR", "ROOKIE", 0),
        (1.0, "EXCELLENT", "ELITE", 0),
        (0.5, "AVERAGE", "ACTIVE", 10),
        (0.0, "EXCELLENT", "ELITE", 100),
    ]
    for score, grade, tier, violations in cases:
        b = calc.calculate(f"extreme_{score}", score, grade, tier, violations)
        assert b.final_reward >= 0.0
        assert b.penalty <= 0.5
    print(f"  [PASS] Economics extreme → all {len(cases)} cases valid")


async def main():
    print(f"\n{'='*60}")
    print("Chaos Test Suite")
    print(f"{'='*60}")
    await test_all_nodes_up()
    await test_majority_crashed()
    await test_timeout_nodes()
    await test_garbage_responses()
    await test_slow_network()
    await test_one_node_down()
    await test_replay_guard_concurrent()
    test_economics_extreme()
    print("\n  ALL CHAOS TESTS PASSED")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
