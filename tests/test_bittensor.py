"""
Bittensor Integration Test
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.bittensor_integration import (
    MinerAxon, ValidatorAxon, SubnetMetagraph, SubnetConfig
)


def test_miner_submit_popw():
    miner = MinerAxon("0xABC", "hotkey_001")
    popw = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "abc123"}
    result = miner.submit_popw(popw)
    assert result["status"] == "submitted"
    assert result["mission_id"] == "m1"
    assert len(result["proof_hash"]) == 64


def test_miner_status():
    miner = MinerAxon("0xABC", "hotkey_001")
    miner.submit_popw({"mission_id": "m1", "score": 0.85, "trajectory_hash": "abc"})
    status = miner.get_status()
    assert status["missions_completed"] == 1
    assert status["network"] == SubnetConfig.NETWORK
    assert status["netuid"] == SubnetConfig.NETUID


def test_validator_verify_valid_popw():
    val = ValidatorAxon("0xDEF", "hotkey_val_001")
    popw = {"mission_id": "m1", "score": 0.85, "trajectory_hash": "abc123"}
    result = val.verify_popw(popw)
    assert result["valid"] is True


def test_validator_reject_low_score():
    val = ValidatorAxon("0xDEF", "hotkey_val_001")
    popw = {"mission_id": "m1", "score": 0.3, "trajectory_hash": "abc123"}
    result = val.verify_popw(popw)
    assert result["valid"] is False


def test_validator_reject_missing_fields():
    val = ValidatorAxon("0xDEF", "hotkey_val_001")
    result = val.verify_popw({})
    assert result["valid"] is False


def test_validator_set_weights():
    val = ValidatorAxon("0xDEF", "hotkey_val_001")
    scores = {0: 0.9, 1: 0.7, 2: 0.5}
    result = val.set_weights(scores)
    assert result["status"] == "weights_set"
    assert result["miners_count"] == 3
    weights = val.get_weights()
    assert abs(sum(weights.values()) - 1.0) < 0.001


def test_metagraph_register_miners():
    graph = SubnetMetagraph()
    m1 = MinerAxon("0xA", "hot_a")
    m2 = MinerAxon("0xB", "hot_b")
    m3 = MinerAxon("0xC", "hot_c")
    graph.register_miner(m1)
    graph.register_miner(m2)
    graph.register_miner(m3)
    state = graph.get_state()
    assert state["n_miners"] == 3
    assert m1.uid == 0
    assert m2.uid == 1
    assert m3.uid == 2


def test_metagraph_register_validators():
    graph = SubnetMetagraph()
    v1 = ValidatorAxon("0xV1", "val_hot_1")
    v2 = ValidatorAxon("0xV2", "val_hot_2")
    graph.register_validator(v1)
    graph.register_validator(v2)
    state = graph.get_state()
    assert state["n_validators"] == 2
    assert v1.uid == 1000
    assert v2.uid == 1001


def test_metagraph_state():
    graph = SubnetMetagraph()
    state = graph.get_state()
    assert state["netuid"] == SubnetConfig.NETUID
    assert state["on_chain_ready"] is True
    assert state["tempo"] == SubnetConfig.TEMPO


def test_full_subnet_flow():
    graph = SubnetMetagraph()
    miner = MinerAxon("0xMINER", "miner_hot")
    validator = ValidatorAxon("0xVAL", "val_hot")
    graph.register_miner(miner)
    graph.register_validator(validator)

    popw = {"mission_id": "m1", "score": 0.9, "trajectory_hash": "hash123"}
    submit_result = miner.submit_popw(popw)
    verify_result = validator.verify_popw(popw)
    weights_result = validator.set_weights({miner.uid: verify_result["score"]})

    assert submit_result["status"] == "submitted"
    assert verify_result["valid"] is True
    assert weights_result["status"] == "weights_set"
