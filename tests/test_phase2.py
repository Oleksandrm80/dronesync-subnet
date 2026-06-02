"""Tests for Phase 2: Memory, Swarm Consensus, Emergency Override"""
from dronesync.memory import DroneMemory
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.emergency import EmergencyOverride


# --- Memory ---

def test_memory_records_flight():
    mem = DroneMemory("DRONE_001")
    positions = [[47.37, 8.54, 50, 0], [47.38, 8.545, 50, 5]]
    mem.record_flight(positions, duration_s=120.0)
    assert mem.missions_completed == 1

def test_memory_flight_hours():
    mem = DroneMemory("DRONE_001")
    positions = [[47.37, 8.54, 50, 0]]
    mem.record_flight(positions, duration_s=3600.0)
    assert mem.total_flight_hours == 1.0

def test_memory_on_chain_ready():
    mem = DroneMemory("DRONE_001")
    record = mem.get_memory_record()
    assert record["on_chain_ready"] is True

def test_memory_asset_value_low():
    mem = DroneMemory("DRONE_001")
    record = mem.get_memory_record()
    assert record["asset_value"] == "LOW"

def test_memory_asset_value_high():
    mem = DroneMemory("DRONE_001")
    mem.missions_completed = 100
    record = mem.get_memory_record()
    assert record["asset_value"] == "HIGH"


# --- Swarm Consensus ---

def test_consensus_approves_majority_vote():
    c = SwarmConsensus(["d0", "d1", "d2"])
    votes = [("d0", True), ("d1", True), ("d2", False)]
    result = c.vote_on_route("M1", votes)
    assert result["status"] == "APPROVED"

def test_consensus_rejects_minority_vote():
    c = SwarmConsensus(["d0", "d1", "d2"])
    votes = [("d0", True), ("d1", False), ("d2", False)]
    result = c.vote_on_route("M1", votes)
    assert result["status"] == "REJECTED"

def test_consensus_blacklist_drone():
    c = SwarmConsensus(["d0", "d1", "d2", "d3"])
    votes = [("d0", True), ("d1", True), ("d2", True)]
    result = c.vote_blacklist("d3", votes)
    assert result["status"] == "BLACKLISTED"
    assert "d3" in c.blacklist

def test_consensus_on_chain_ready():
    c = SwarmConsensus(["d0", "d1"])
    status = c.get_swarm_status()
    assert status["on_chain_ready"] is True


# --- Emergency Override ---

def test_emergency_broadcast():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.38, "lon": 8.54}, "AUTH_001")
    assert em["type"] == "FIRE"
    assert em["status"] == "ACTIVE"

def test_emergency_overrides_drone_in_radius():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em)
    assert result["override"] is True
    assert result["action"] == "ASSIST_FIRE"

def test_emergency_no_override_outside_radius():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    result = eo.check_drone_override([47.4500, 8.6000, 50.0], em)
    assert result["override"] is False

def test_emergency_on_chain_ready():
    eo = EmergencyOverride()
    status = eo.get_status()
    assert status["on_chain_ready"] is True

def test_medical_not_redirected_by_fire():
    # fire doesn't need medical drones
    eo = EmergencyOverride()
    em = eo.broadcast_emergency('FIRE', {'lat': 47.3780, 'lon': 8.5430}, 'AUTH_001')
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type='organ_delivery')
    assert result['override'] is False
    assert result['reason'] == 'incompatible_drone_type'

def test_fire_overrides_cargo_delivery():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency('FIRE', {'lat': 47.3780, 'lon': 8.5430}, 'AUTH_001')
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type='urban_delivery')
    assert result['override'] is True

def test_medical_emergency_redirects_medical_drone():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency('MEDICAL_EMERGENCY', {'lat': 47.3780, 'lon': 8.5430}, 'AUTH_001')
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type='medical_delivery')
    assert result['override'] is True

def test_protected_drones_counted():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency('FIRE', {'lat': 47.3780, 'lon': 8.5430}, 'AUTH_001')
    eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type='organ_delivery')
    assert eo.get_status()['protected_drones'] == 1

