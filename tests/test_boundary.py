"""
Boundary and edge case tests for DroneSync.
Tests system behavior with invalid, extreme, and null inputs.
"""
import time
from dronesync.synapse import DroneNavSynapseHandler
from dronesync.mission_history import MissionHistory
from dronesync.replay_guard import ReplayGuard
from dronesync.firewall import DroneFirewall
from dronesync.reputation import DroneReputation
from dronesync.swarm_consensus import SwarmConsensus


def test_synapse_handles_none_input():
    handler = DroneNavSynapseHandler()
    result = handler.handle(None)
    assert result["status"] in ("REJECTED", "ERROR")
    assert result["on_chain_ready"] is False


def test_synapse_handles_empty_dict():
    handler = DroneNavSynapseHandler()
    result = handler.handle({})
    assert result["status"] in ("OK", "REJECTED", "ERROR")


def test_synapse_handles_null_destination():
    handler = DroneNavSynapseHandler()
    result = handler.handle({"task_id": "TEST_001", "destination": None})
    assert "status" in result


def test_synapse_handles_invalid_coordinates():
    handler = DroneNavSynapseHandler()
    result = handler.handle({
        "task_id": "TEST_002",
        "origin": {"lat": 999999, "lon": -999999, "alt": -100},
        "destination": {"lat": 999999, "lon": 999999, "alt": 99999},
    })
    assert "status" in result


def test_synapse_handles_string_instead_of_dict():
    handler = DroneNavSynapseHandler()
    result = handler.handle("invalid input")
    assert result["status"] == "REJECTED"


def test_replay_guard_blocks_duplicate():
    rg = ReplayGuard()
    mission_id = f"TEST_{int(time.time())}"
    rg.check(mission_id, time.time())
    rg.register(mission_id)
    result = rg.check(mission_id, time.time())
    assert result["allowed"] is False


def test_replay_guard_blocks_old_mission():
    rg = ReplayGuard()
    old_time = time.time() - 7200
    result = rg.check("OLD_MISSION_999", old_time)
    assert result["allowed"] is False


def test_firewall_blocks_empty_command():
    fw = DroneFirewall("DRONE_TEST")
    result = fw.filter({})
    assert result["status"] == "BLOCKED"


def test_firewall_blocks_none_signature():
    fw = DroneFirewall("DRONE_TEST")
    result = fw.filter({"action": "fly", "source": "op",
                        "timestamp": int(time.time()), "signature": None})
    assert result["status"] == "BLOCKED"


def test_reputation_handles_zero_score():
    rep = DroneReputation("DRONE_BOUNDARY")
    rep.record_mission("TEST_001", score=0, mission_safe=False, battery_used_pct=100.0)
    status = rep.get_status()
    assert status["score"] >= 0


def test_reputation_handles_max_score():
    rep = DroneReputation("DRONE_BOUNDARY_MAX")
    rep.record_mission("TEST_002", score=100, mission_safe=True, battery_used_pct=5.0)
    status = rep.get_status()
    assert status["score"] <= 100


def test_mission_history_empty_stats():
    history = MissionHistory()
    stats = history.stats()
    assert stats["total_missions"] == 0


def test_mission_history_chain_valid_after_multiple():
    history = MissionHistory()
    for i in range(10):
        history.add(f"MISSION_{i}", score=90+i % 10,
                    duration_s=100+i, battery_used=7.0+i*0.1)
    stats = history.stats()
    assert stats["chain_valid"] is True


def test_swarm_consensus_empty_votes():
    consensus = SwarmConsensus(["drone_0", "drone_1", "drone_2"])
    result = consensus.vote_on_route("TEST_EMPTY", [])
    assert result["status"] in ("APPROVED", "REJECTED")


def test_swarm_consensus_all_reject():
    consensus = SwarmConsensus(["drone_0", "drone_1", "drone_2"])
    votes = [("drone_0", False), ("drone_1", False), ("drone_2", False)]
    result = consensus.vote_on_route("TEST_REJECT", votes)
    assert result["status"] == "REJECTED"
