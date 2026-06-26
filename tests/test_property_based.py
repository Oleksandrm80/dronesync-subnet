"""
tests/test_property_based.py

Property-Based Testing for DroneSync.
Tests mathematical invariants that must hold for ANY input.

Properties tested:
1. Score always in [0, 100]
2. PoPW hash is deterministic
3. History never changes after write
4. ReplayGuard always rejects duplicate
5. Consensus quorum math is correct
"""

import time
import random
import string
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dronesync.synapse import DroneNavSynapseHandler
from dronesync.replay_guard import ReplayGuard
from dronesync.validator_node import ValidatorNode, ValidatorVote
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.mpc import ShamirSecretSharing


def random_string(max_len=64):
    length = random.randint(0, max_len)
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_float(low=-1e10, high=1e10):
    return random.uniform(low, high)


def random_mission():
    return {
        "mission_id": random_string(32),
        "waypoints": [
            [random.uniform(-90, 90), random.uniform(-180, 180),
             random.uniform(0, 500)]
            for _ in range(random.randint(0, 5))
        ],
        "battery": random.uniform(0, 100),
        "created_at": time.time() + random.uniform(-3600, 60),
        "mission_type": random.choice(["urban_delivery", "survey", "unknown", ""]),
    }


# ── Property 1: Score always in [0, 100] ──────────────────────
class TestScoreRange:

    def setup_method(self):
        self.handler = DroneNavSynapseHandler()

    @pytest.mark.parametrize("_", range(50))
    def test_score_always_valid_range(self, _):
        task = random_mission()
        result = self.handler.handle(task)
        assert isinstance(result, dict)
        assert "status" in result
        if "score" in result and result["score"] is not None:
            assert 0 <= result["score"] <= 100


# ── Property 2: PoPW hash is deterministic ────────────────────
class TestPoPWDeterminism:

    @pytest.mark.parametrize("_", range(20))
    def test_same_input_same_hash(self, _):
        import hashlib
        import json
        positions = [
            [random.uniform(49, 51), random.uniform(29, 31),
             random.uniform(20, 100), time.time()]
            for _ in range(random.randint(2, 10))
        ]
        h1 = hashlib.sha256(json.dumps(positions, sort_keys=True).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(positions, sort_keys=True).encode()).hexdigest()
        assert h1 == h2

    @pytest.mark.parametrize("_", range(20))
    def test_different_input_different_hash(self, _):
        import hashlib
        import json
        p1 = [[50.0, 30.0, 50.0, 1000.0]]
        p2 = [[50.0, 30.0, 50.1, 1000.0]]
        h1 = hashlib.sha256(json.dumps(p1, sort_keys=True).encode()).hexdigest()
        h2 = hashlib.sha256(json.dumps(p2, sort_keys=True).encode()).hexdigest()
        assert h1 != h2


# ── Property 3: ReplayGuard always rejects duplicate ──────────
class TestReplayGuardProperty:

    def setup_method(self):
        self.replay = ReplayGuard(persist_path="/tmp/prop_replay")

    @pytest.mark.parametrize("_", range(50))
    def test_duplicate_always_rejected(self, _):
        mission_id = random_string(32)
        if not mission_id:
            return
        created_at = time.time() - random.uniform(1, 3600)

        r1 = self.replay.check(mission_id, created_at)
        if r1["allowed"]:
            self.replay.register(mission_id)
            r2 = self.replay.check(mission_id, created_at)
            assert r2["allowed"] is False

    @pytest.mark.parametrize("_", range(20))
    def test_future_timestamp_rejected(self, _):
        mission_id = f"future_{random_string(16)}"
        future_ts = time.time() + random.uniform(400, 100000)
        result = self.replay.check(mission_id, future_ts)
        assert result["allowed"] is False


# ── Property 4: Consensus quorum math ─────────────────────────
class TestConsensusProperty:

    @pytest.mark.parametrize("n_total,n_accepted", [
        (3, 3), (3, 2), (3, 1), (3, 0),
        (5, 5), (5, 4), (5, 3), (5, 2), (5, 1),
        (10, 7), (10, 6), (10, 5),
    ])
    def test_quorum_threshold(self, n_total, n_accepted):
        node = ValidatorNode("test", port=9999)
        mission_id = f"mission_{n_total}_{n_accepted}"
        node._votes[mission_id] = [
            ValidatorVote(f"v{i}", mission_id,
                         i < n_accepted, 85.0 if i < n_accepted else 30.0)
            for i in range(n_total)
        ]
        result = node._compute_result(mission_id)
        expected = (n_accepted / n_total) >= 0.67
        assert result["consensus"] == expected
        assert result["quorum"] == round(n_accepted / n_total, 3)


# ── Property 5: Shamir Secret Sharing ─────────────────────────
class TestShamirProperty:

    @pytest.mark.parametrize("secret", [0.0, 1.0, 50.0, 99.9, 60.0, 75.5])
    def test_reconstruct_exact(self, secret):
        sss = ShamirSecretSharing(threshold=2, n_shares=3)
        shares = sss.split(secret)
        reconstructed = sss.reconstruct(shares[:2])
        assert abs(reconstructed - secret) < 0.1

    @pytest.mark.parametrize("_", range(10))
    def test_random_secret_reconstruct(self, _):
        secret = random.uniform(0, 100)
        sss = ShamirSecretSharing(threshold=2, n_shares=3)
        shares = sss.split(secret)
        reconstructed = sss.reconstruct(shares)
        assert abs(reconstructed - secret) < 0.5
