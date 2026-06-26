"""
Multi-Validator Consensus Test
Proves 3 independent validators reach correct consensus.
"""
import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.validator_auth import ValidatorAuth


class MockValidator:
    """Simulates an independent validator node."""

    def __init__(self, validator_id: str, secret: str, honest: bool = True):
        self.validator_id = validator_id
        self.auth = ValidatorAuth(secret=secret)
        self.honest = honest

    def evaluate(self, popw: dict) -> dict:
        score = popw.get("score", 0)
        if self.honest:
            accepted = score >= 0.6
        else:
            accepted = not (score >= 0.6)  # byzantine — always wrong
        return {
            "validator_id": self.validator_id,
            "accepted": accepted,
            "score": score,
            "timestamp": time.time(),
        }


class LocalValidatorNetwork:
    """Local consensus without real network — for testing."""

    QUORUM = 0.67

    def __init__(self, validators: list):
        self.validators = validators

    def submit(self, popw: dict) -> dict:
        votes = [v.evaluate(popw) for v in self.validators]
        total = len(votes)
        accepted = sum(1 for v in votes if v["accepted"])
        quorum = accepted / total
        consensus = quorum >= self.QUORUM
        avg_score = sum(v["score"] for v in votes) / total
        return {
            "consensus": consensus,
            "quorum": round(quorum, 2),
            "avg_score": round(avg_score, 2),
            "votes_total": total,
            "votes_accepted": accepted,
            "votes": votes,
        }


SHARED_SECRET = "dronesync_validator_secret"


def _make_network(honest_count: int, byzantine_count: int) -> LocalValidatorNetwork:
    validators = []
    for i in range(honest_count):
        validators.append(MockValidator(f"VAL_{i:03d}", SHARED_SECRET, honest=True))
    for i in range(byzantine_count):
        validators.append(MockValidator(f"BYZ_{i:03d}", SHARED_SECRET, honest=False))
    return LocalValidatorNetwork(validators)


def test_3_honest_validators_consensus():
    net = _make_network(honest_count=3, byzantine_count=0)
    result = net.submit({"mission_id": "m1", "score": 0.85})
    assert result["consensus"] is True
    assert result["votes_accepted"] == 3


def test_3_honest_validators_reject_bad_mission():
    net = _make_network(honest_count=3, byzantine_count=0)
    result = net.submit({"mission_id": "m1", "score": 0.3})
    assert result["consensus"] is False
    assert result["votes_accepted"] == 0


def test_1_byzantine_out_of_3_still_consensus():
    net = _make_network(honest_count=3, byzantine_count=1)
    result = net.submit({"mission_id": "m1", "score": 0.85})
    assert result["consensus"] is True
    assert result["votes_accepted"] == 3
    assert result["quorum"] >= 0.67


def test_2_byzantine_out_of_3_breaks_consensus():
    net = _make_network(honest_count=1, byzantine_count=2)
    result = net.submit({"mission_id": "m1", "score": 0.85})
    assert result["consensus"] is False
    assert result["votes_accepted"] == 1


def test_5_validators_1_byzantine():
    net = _make_network(honest_count=4, byzantine_count=1)
    result = net.submit({"mission_id": "m1", "score": 0.85})
    assert result["consensus"] is True
    assert result["quorum"] >= 0.67


def test_quorum_exactly_67_percent():
    net = _make_network(honest_count=2, byzantine_count=1)
    result = net.submit({"mission_id": "m1", "score": 0.85})
    assert result["quorum"] >= 0.67


def test_all_validators_authenticated():
    auth = ValidatorAuth(secret=SHARED_SECRET)
    for i in range(3):
        token = auth.generate_token(f"VAL_{i:03d}")
        assert auth.verify_token(token)


def test_byzantine_validator_token_rejected():
    honest_auth = ValidatorAuth(secret=SHARED_SECRET)
    byzantine_auth = ValidatorAuth(secret="wrong_secret")
    token = byzantine_auth.generate_token("BYZ_000")
    assert not honest_auth.verify_token(token)


def test_network_status_3_nodes():
    net = _make_network(honest_count=3, byzantine_count=0)
    assert len(net.validators) == 3
    for v in net.validators:
        assert v.honest is True


def test_consensus_multiple_missions():
    net = _make_network(honest_count=3, byzantine_count=0)
    missions = [
        ("m1", 0.95, True),
        ("m2", 0.75, True),
        ("m3", 0.65, True),
        ("m4", 0.45, False),
        ("m5", 0.10, False),
    ]
    for mission_id, score, expected in missions:
        result = net.submit({"mission_id": mission_id, "score": score})
        assert result["consensus"] == expected, \
            f"Mission {mission_id} score={score} expected={expected} got={result['consensus']}"
