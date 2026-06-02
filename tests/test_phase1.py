"""Tests for Phase 1: Reputation, Firewall, Last Will"""
import time
from dronesync.reputation import DroneReputation
from dronesync.firewall import DroneFirewall
from dronesync.last_will import DroneLastWill


# --- Reputation ---

def test_reputation_starts_at_50():
    rep = DroneReputation("DRONE_001")
    assert rep.score == 50

def test_reputation_increases_on_good_mission():
    rep = DroneReputation("DRONE_001")
    rep.record_mission("M1", 97, True, 7.0)
    assert rep.score > 50

def test_reputation_decreases_on_unsafe_mission():
    rep = DroneReputation("DRONE_001")
    rep.record_mission("M1", 55, False, 45.0)
    assert rep.score < 50

def test_reputation_tier_elite():
    rep = DroneReputation("DRONE_001")
    rep.score = 95
    rep.tier = rep._compute_tier()
    assert rep.tier == "ELITE"

def test_reputation_on_chain_ready():
    rep = DroneReputation("DRONE_001")
    rep.record_mission("M1", 97, True, 7.0)
    status = rep.get_status()
    assert status["on_chain_ready"] is True


# --- Firewall ---

def test_firewall_allows_valid_command():
    fw = DroneFirewall("DRONE_001")
    cmd = {"action": "fly", "source": "op", "timestamp": int(time.time()), "signature": "abc"}
    result = fw.filter(cmd)
    assert result["status"] == "ALLOWED"

def test_firewall_blocks_missing_signature():
    fw = DroneFirewall("DRONE_001")
    cmd = {"action": "fly", "source": "op", "timestamp": int(time.time())}
    result = fw.filter(cmd)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "missing_signature"

def test_firewall_blocks_unknown_action():
    fw = DroneFirewall("DRONE_001")
    cmd = {"action": "hack", "source": "op", "timestamp": int(time.time()), "signature": "abc"}
    result = fw.filter(cmd)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "unknown_action"

def test_firewall_blocks_stale_command():
    fw = DroneFirewall("DRONE_001")
    cmd = {"action": "fly", "source": "op", "timestamp": int(time.time()) - 60, "signature": "abc"}
    result = fw.filter(cmd)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "stale_command"

def test_firewall_report_on_chain_ready():
    fw = DroneFirewall("DRONE_001")
    report = fw.get_report()
    assert report["on_chain_ready"] is True


# --- Last Will ---

def test_last_will_trigger():
    lw = DroneLastWill("DRONE_001")
    record = lw.trigger([47.38, 8.545, 50.0], "BATTERY_FAILURE", 2.1, "M1")
    assert record["type"] == "LAST_WILL"
    assert record["on_chain_ready"] is True
    assert record["insurance_claim_ready"] is True

def test_last_will_has_hash():
    lw = DroneLastWill("DRONE_001")
    record = lw.trigger([47.38, 8.545, 50.0], "BATTERY_FAILURE", 2.1, "M1")
    assert len(record["will_hash"]) == 64

def test_last_will_simulate_crash():
    lw = DroneLastWill("DRONE_001")
    positions = [[47.37, 8.54, 50, 0], [47.38, 8.545, 50, 5]]
    record = lw.simulate_crash(positions, "DSYNC_001")
    assert record["failure_cause"] == "CRITICAL_BATTERY_FAILURE"
    assert record["last_position"]["lat"] == 47.38
