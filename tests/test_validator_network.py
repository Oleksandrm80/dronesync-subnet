"""Tests for validator node and network — no real WebSocket required."""

import time
import pytest
from dronesync.validator_node import ValidatorNode, ValidatorVote
from dronesync.validator_network import ValidatorNetwork, NetworkResult


def _make_popw(score: float = 80.0, constraints: bool = True,
               positions: int = 3) -> dict:
    return {
        "mission_id": f"test_mission_{int(time.time() * 1000)}",
        "score": score,
        "computation_hash": "a3f9c2e1b8d7f4a6c0e3b1d9f2a5c8e0",
        "constraints_satisfied": constraints,
        "trajectory_positions": [
            [50.45 + i * 0.001, 30.52 + i * 0.001, 50.0 + i, time.time() + i]
            for i in range(positions)
        ],
        "energy_estimate": 12.4,
        "simulation_steps": 150,
    }


def test_vote_accepted():
    node = ValidatorNode("test-node", port=9100)
    popw = _make_popw(score=85.0)
    vote = node._validate_popw(popw)
    assert vote.accepted is True
    assert vote.score == 85.0
    assert vote.reason == "accepted"


def test_vote_rejected_low_score():
    node = ValidatorNode("test-node", port=9100, min_score=60.0)
    popw = _make_popw(score=40.0)
    vote = node._validate_popw(popw)
    assert vote.accepted is False
    assert "score_too_low" in vote.reason


def test_vote_rejected_constraints():
    node = ValidatorNode("test-node", port=9100)
    popw = _make_popw(constraints=False)
    vote = node._validate_popw(popw)
    assert vote.accepted is False
    assert vote.reason == "constraints_failed"


def test_vote_rejected_missing_hash():
    node = ValidatorNode("test-node", port=9100)
    popw = _make_popw()
    popw["computation_hash"] = ""
    vote = node._validate_popw(popw)
    assert vote.accepted is False
    assert vote.reason == "missing_hash"


def test_vote_rejected_short_trajectory():
    node = ValidatorNode("test-node", port=9100)
    popw = _make_popw(positions=1)
    vote = node._validate_popw(popw)
    assert vote.accepted is False
    assert vote.reason == "trajectory_too_short"


def test_vote_signature():
    vote = ValidatorVote("node-1", "mission-1", True, 85.0)
    assert len(vote.signature) == 16
    assert isinstance(vote.signature, str)


def test_vote_to_dict():
    vote = ValidatorVote("node-1", "mission-1", True, 85.0, "accepted")
    d = vote.to_dict()
    assert d["validator_id"] == "node-1"
    assert d["mission_id"] == "mission-1"
    assert d["accepted"] is True
    assert d["score"] == 85.0


def test_compute_result_consensus():
    node = ValidatorNode("test-node", port=9100)
    mission_id = "mission-consensus"
    node._votes[mission_id] = [
        ValidatorVote("A", mission_id, True, 85.0),
        ValidatorVote("B", mission_id, True, 90.0),
        ValidatorVote("C", mission_id, True, 75.0),
        ValidatorVote("D", mission_id, False, 40.0),
    ]
    result = node._compute_result(mission_id)
    assert result["consensus"] is True
    assert result["quorum"] >= 0.67
    assert result["votes_total"] == 4
    assert result["votes_accepted"] == 3

def test_compute_result_no_consensus():
    node = ValidatorNode("test-node", port=9100)
    mission_id = "mission-no-consensus"
    node._votes[mission_id] = [
        ValidatorVote("A", mission_id, False, 30.0),
        ValidatorVote("B", mission_id, False, 25.0),
        ValidatorVote("C", mission_id, True, 80.0),
    ]
    result = node._compute_result(mission_id)
    assert result["consensus"] is False
    assert result["quorum"] < 0.67


def test_compute_result_no_votes():
    node = ValidatorNode("test-node", port=9100)
    result = node._compute_result("nonexistent")
    assert result["consensus"] is False
    assert result["reason"] == "no_votes"


def test_network_result_to_dict():
    result = NetworkResult("mission-123")
    result.votes = [
        {"accepted": True, "score": 85.0},
        {"accepted": True, "score": 90.0},
        {"accepted": False, "score": 30.0},
    ]
    result.consensus = True
    result.quorum = 0.67
    result.avg_score = 68.3
    result.duration_ms = 42.5

    d = result.to_dict()
    assert d["consensus"] is True
    assert d["votes_total"] == 3
    assert d["votes_accepted"] == 2
    assert d["duration_ms"] == 42.5
