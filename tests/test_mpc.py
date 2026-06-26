"""Tests for MPC — Multi-Party Computation."""

import pytest
from dronesync.mpc import (
    ShamirSecretSharing, MPCCoordinator, SecretShare, _commitment
)


def test_shamir_split_reconstruct():
    sss = ShamirSecretSharing(threshold=2, n_shares=3)
    secret = 87.5
    shares = sss.split(secret)
    assert len(shares) == 3
    reconstructed = sss.reconstruct(shares[:2])
    assert abs(reconstructed - secret) < 0.01


def test_shamir_any_threshold_shares():
    sss = ShamirSecretSharing(threshold=2, n_shares=3)
    secret = 75.0
    shares = sss.split(secret)
    r1 = sss.reconstruct([shares[0], shares[1]])
    r2 = sss.reconstruct([shares[1], shares[2]])
    r3 = sss.reconstruct([shares[0], shares[2]])
    assert abs(r1 - secret) < 0.01
    assert abs(r2 - secret) < 0.01
    assert abs(r3 - secret) < 0.01


def test_shamir_threshold_3_of_5():
    sss = ShamirSecretSharing(threshold=3, n_shares=5)
    secret = 92.0
    shares = sss.split(secret)
    reconstructed = sss.reconstruct(shares[:3])
    assert abs(reconstructed - secret) < 0.01


def test_shamir_not_enough_shares():
    sss = ShamirSecretSharing(threshold=3, n_shares=5)
    shares = sss.split(80.0)
    with pytest.raises(ValueError):
        sss.reconstruct(shares[:2])


def test_shamir_threshold_exceeds_n():
    with pytest.raises(ValueError):
        ShamirSecretSharing(threshold=5, n_shares=3)


def test_commitment_unique():
    c1 = _commitment("v1", 1, 0.5)
    c2 = _commitment("v2", 1, 0.5)
    c3 = _commitment("v1", 2, 0.5)
    assert c1 != c2
    assert c1 != c3


def test_mpc_coordinator_split():
    validators = ["v1", "v2", "v3"]
    coord = MPCCoordinator(validators, threshold=2)
    popw = {"mission_id": "m1", "score": 85.0}
    shares = coord.split_popw(popw)
    assert len(shares) == 3
    assert set(shares.keys()) == set(validators)
    for s in shares.values():
        assert s.commitment


def test_mpc_coordinator_validate_accepted():
    validators = ["v1", "v2", "v3"]
    coord = MPCCoordinator(validators, threshold=2)
    popw = {"mission_id": "m1", "score": 85.0}
    result = coord.validate_popw_private(popw, min_score=60.0)
    assert result.accepted is True
    assert abs(result.reconstructed_score - 85.0) < 0.5
    assert result.shares_used >= 2


def test_mpc_coordinator_validate_rejected():
    validators = ["v1", "v2", "v3"]
    coord = MPCCoordinator(validators, threshold=2)
    popw = {"mission_id": "m2", "score": 40.0}
    result = coord.validate_popw_private(popw, min_score=60.0)
    assert result.accepted is False
    assert result.reconstructed_score < 60.0


def test_mpc_result_to_dict():
    validators = ["v1", "v2", "v3"]
    coord = MPCCoordinator(validators, threshold=2)
    popw = {"mission_id": "m3", "score": 75.0}
    result = coord.validate_popw_private(popw)
    d = result.to_dict()
    assert d["mission_id"] == "m3"
    assert "reconstructed_score" in d
    assert "accepted" in d
    assert "validators" in d


def test_mpc_not_enough_shares():
    validators = ["v1", "v2", "v3"]
    coord = MPCCoordinator(validators, threshold=3)
    popw = {"mission_id": "m4", "score": 80.0}
    shares = coord.split_popw(popw)
    partial = {k: v for k, v in list(shares.items())[:2]}
    result = coord.reconstruct_and_validate(partial, "m4", min_score=60.0)
    assert result.accepted is False
    assert result.shares_used == 2


def test_mpc_score_zero():
    validators = ["v1", "v2"]
    coord = MPCCoordinator(validators, threshold=2)
    popw = {"mission_id": "m5", "score": 0.0}
    result = coord.validate_popw_private(popw, min_score=60.0)
    assert result.accepted is False
