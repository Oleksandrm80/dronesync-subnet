"""
MPC Multi-Party Computation Test
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.mpc import ShamirSecretSharing, MPCVerifier


def test_shamir_split_and_reconstruct():
    sss = ShamirSecretSharing(threshold=2, n_shares=3)
    secret = 0.85
    shares = sss.split(secret)
    assert len(shares) == 3
    result = sss.reconstruct(shares[:2])
    assert abs(result - secret) < 0.001


def test_shamir_any_two_shares_work():
    sss = ShamirSecretSharing(threshold=2, n_shares=3)
    secret = 0.75
    shares = sss.split(secret)
    for pair in [(0,1), (1,2), (0,2)]:
        result = sss.reconstruct([shares[pair[0]], shares[pair[1]]])
        assert abs(result - secret) < 0.001


def test_shamir_threshold_3_of_5():
    sss = ShamirSecretSharing(threshold=3, n_shares=5)
    secret = 0.9
    shares = sss.split(secret)
    result = sss.reconstruct(shares[:3])
    assert abs(result - secret) < 0.001


def test_mpc_distribute_popw():
    validators = ["VAL_001", "VAL_002", "VAL_003"]
    mpc = MPCVerifier(validator_ids=validators, threshold=2)
    popw = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "hash123"}
    dist = mpc.distribute_popw(popw)
    assert dist["mission_id"] == "m1"
    assert dist["threshold"] == 2
    assert len(dist["shares"]) == 3
    for val_id in validators:
        assert val_id in dist["shares"]


def test_mpc_verify_with_threshold():
    validators = ["VAL_001", "VAL_002", "VAL_003"]
    mpc = MPCVerifier(validator_ids=validators, threshold=2)
    popw = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "hash123"}
    dist = mpc.distribute_popw(popw)
    result = mpc.collect_and_verify(dist, ["VAL_001", "VAL_002"])
    assert result["valid"] is True
    assert abs(result["reconstructed_score"] - 0.85) < 0.001


def test_mpc_insufficient_shares():
    validators = ["VAL_001", "VAL_002", "VAL_003"]
    mpc = MPCVerifier(validator_ids=validators, threshold=2)
    popw = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "hash123"}
    dist = mpc.distribute_popw(popw)
    result = mpc.collect_and_verify(dist, ["VAL_001"])
    assert result["valid"] is False
    assert result["reason"] == "insufficient_shares"


def test_mpc_low_score_rejected():
    validators = ["VAL_001", "VAL_002", "VAL_003"]
    mpc = MPCVerifier(validator_ids=validators, threshold=2)
    popw = {"mission_id": "m1", "score": 0.3, "trajectory_hash": "hash123"}
    dist = mpc.distribute_popw(popw)
    result = mpc.collect_and_verify(dist, ["VAL_001", "VAL_002"])
    assert result["valid"] is False


def test_mpc_commit_hash_changes_with_data():
    validators = ["VAL_001", "VAL_002", "VAL_003"]
    mpc = MPCVerifier(validator_ids=validators, threshold=2)
    popw1 = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "hash123"}
    popw2 = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "hash456"}
    dist1 = mpc.distribute_popw(popw1)
    dist2 = mpc.distribute_popw(popw2)
    assert dist1["commit_hash"] != dist2["commit_hash"]
