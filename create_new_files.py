"""
Run this script once in your dronesync-subnet folder.
It creates all new files for Phase 1, Phase 2, Storage, ScoreRoot, SensorBundle.
"""
import os

files = {}

files["dronesync/reputation.py"] = '''"""
DroneSync - Drone Reputation Score
"""
import hashlib
import time


class DroneReputation:
    BASE_SCORE = 50
    MAX_SCORE = 100
    MIN_SCORE = 0

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.missions = []
        self.score = self.BASE_SCORE
        self.tier = "ROOKIE"

    def record_mission(self, mission_id: str, score: int,
                       mission_safe: bool, battery_used_pct: float):
        record = {
            "mission_id": mission_id,
            "score": score,
            "mission_safe": mission_safe,
            "battery_used_pct": battery_used_pct,
            "timestamp": int(time.time())
        }
        self.missions.append(record)
        self._update_score(score, mission_safe)
        return record

    def _update_score(self, mission_score: int, mission_safe: bool):
        if not mission_safe:
            self.score = max(self.MIN_SCORE, self.score - 10)
            return
        if mission_score >= 95:
            self.score = min(self.MAX_SCORE, self.score + 3)
        elif mission_score >= 80:
            self.score = min(self.MAX_SCORE, self.score + 1)
        elif mission_score < 60:
            self.score = max(self.MIN_SCORE, self.score - 3)
        self.tier = self._compute_tier()

    def _compute_tier(self) -> str:
        if self.score >= 90:
            return "ELITE"
        elif self.score >= 75:
            return "TRUSTED"
        elif self.score >= 50:
            return "ACTIVE"
        else:
            return "ROOKIE"

    def get_status(self) -> dict:
        reputation_hash = hashlib.sha256(str(self.missions).encode()).hexdigest()
        return {
            "drone_id": self.drone_id,
            "reputation_score": self.score,
            "tier": self.tier,
            "total_missions": len(self.missions),
            "reputation_hash": reputation_hash,
            "on_chain_ready": True
        }
'''

files["dronesync/firewall.py"] = '''"""
DroneSync - Drone Firewall
"""
import time
import hashlib


class DroneFirewall:
    MAX_COMMANDS_PER_MINUTE = 20
    ALLOWED_ACTIONS = {"fly", "hover", "land", "return_home", "scan", "deliver"}

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.blocked_log = []
        self.allowed_log = []
        self._command_times = []

    def filter(self, command: dict) -> dict:
        action = command.get("action", "")
        source = command.get("source", "unknown")
        timestamp = command.get("timestamp", 0)

        if action not in self.ALLOWED_ACTIONS:
            return self._block(command, "unknown_action")
        if "signature" not in command:
            return self._block(command, "missing_signature")

        now = int(time.time())
        if timestamp and (now - timestamp) > 30:
            return self._block(command, "stale_command")

        self._command_times = [t for t in self._command_times if now - t < 60]
        if len(self._command_times) >= self.MAX_COMMANDS_PER_MINUTE:
            return self._block(command, "rate_limit_exceeded")

        self._command_times.append(now)
        self.allowed_log.append({"action": action, "source": source, "timestamp": now, "status": "ALLOWED"})
        return {"status": "ALLOWED", "action": action}

    def _block(self, command: dict, reason: str) -> dict:
        self.blocked_log.append({
            "action": command.get("action", "unknown"),
            "source": command.get("source", "unknown"),
            "reason": reason,
            "timestamp": int(time.time())
        })
        return {"status": "BLOCKED", "reason": reason}

    def get_report(self) -> dict:
        log_hash = hashlib.sha256(str(self.blocked_log).encode()).hexdigest()
        return {
            "drone_id": self.drone_id,
            "total_allowed": len(self.allowed_log),
            "total_blocked": len(self.blocked_log),
            "blocked_log": self.blocked_log,
            "log_hash": log_hash,
            "on_chain_ready": True
        }
'''

files["dronesync/last_will.py"] = '''"""
DroneSync - Drone Last Will
"""
import hashlib
import time


class DroneLastWill:
    def __init__(self, drone_id: str):
        self.drone_id = drone_id

    def trigger(self, last_position: list, failure_cause: str,
                battery_pct: float, mission_id: str) -> dict:
        timestamp = int(time.time())
        payload = {
            "drone_id": self.drone_id,
            "mission_id": mission_id,
            "last_position": {"lat": last_position[0], "lon": last_position[1], "alt": last_position[2]},
            "failure_cause": failure_cause,
            "battery_pct": battery_pct,
            "timestamp": timestamp
        }
        will_hash = hashlib.sha256(str(payload).encode()).hexdigest()
        return {
            "type": "LAST_WILL",
            "drone_id": self.drone_id,
            "mission_id": mission_id,
            "last_position": payload["last_position"],
            "failure_cause": failure_cause,
            "battery_pct": battery_pct,
            "timestamp": timestamp,
            "will_hash": will_hash,
            "on_chain_ready": True,
            "insurance_claim_ready": True
        }

    def simulate_crash(self, trajectory_positions: list, mission_id: str) -> dict:
        last = trajectory_positions[-1]
        return self.trigger(last[:3], "CRITICAL_BATTERY_FAILURE", 2.1, mission_id)
'''

files["dronesync/memory.py"] = '''"""
DroneSync - Drone Memory
"""
import hashlib
import time


class DroneMemory:
    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self.dangerous_zones = []
        self.wind_patterns = []
        self.obstacle_encounters = []
        self.total_flight_hours = 0.0
        self.missions_completed = 0

    def record_flight(self, positions: list, duration_s: float,
                      obstacles: list = None, wind_ms: float = 0.0):
        self.total_flight_hours += duration_s / 3600
        self.missions_completed += 1
        if wind_ms > 8.0:
            self.wind_patterns.append({
                "lat": positions[0][0], "lon": positions[0][1],
                "wind_ms": wind_ms, "timestamp": int(time.time())
            })
        if obstacles:
            for obs in obstacles:
                self.obstacle_encounters.append({
                    "obstacle_id": obs.get("obstacle_id", "unknown"),
                    "type": obs.get("type", "unknown"),
                    "timestamp": int(time.time())
                })

    def is_zone_dangerous(self, lat: float, lon: float, radius_m: float = 100) -> bool:
        import math
        for zone in self.dangerous_zones:
            dlat = math.radians(lat - zone["lat"])
            dlon = math.radians(lon - zone["lon"])
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(zone["lat"])) * math.sin(dlon/2)**2
            dist = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            if dist < radius_m:
                return True
        return False

    def get_memory_record(self) -> dict:
        memory_data = {
            "drone_id": self.drone_id,
            "missions_completed": self.missions_completed,
            "total_flight_hours": round(self.total_flight_hours, 2),
            "dangerous_zones": len(self.dangerous_zones),
            "wind_patterns": len(self.wind_patterns),
            "obstacle_encounters": len(self.obstacle_encounters)
        }
        memory_data["memory_hash"] = hashlib.sha256(str(memory_data).encode()).hexdigest()
        memory_data["on_chain_ready"] = True
        memory_data["asset_value"] = self._compute_asset_value()
        return memory_data

    def _compute_asset_value(self) -> str:
        if self.missions_completed >= 100:
            return "HIGH"
        elif self.missions_completed >= 20:
            return "MEDIUM"
        else:
            return "LOW"
'''

files["dronesync/swarm_consensus.py"] = '''"""
DroneSync - Swarm Consensus
"""
import hashlib
import time


class SwarmConsensus:
    QUORUM = 0.51

    def __init__(self, drone_ids: list):
        self.drone_ids = drone_ids
        self.blacklist = []
        self.votes_log = []

    def vote_on_route(self, mission_id: str, route_safe_votes: list) -> dict:
        active_drones = [d for d in self.drone_ids if d not in self.blacklist]
        total = len(active_drones)
        if total == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}
        approvals = sum(1 for _, vote in route_safe_votes if vote)
        approval_rate = approvals / total
        result = {
            "mission_id": mission_id,
            "total_voters": total,
            "approvals": approvals,
            "approval_rate": round(approval_rate, 2),
            "status": "APPROVED" if approval_rate >= self.QUORUM else "REJECTED",
            "timestamp": int(time.time())
        }
        self.votes_log.append(result)
        return result

    def vote_blacklist(self, suspect_drone_id: str, blacklist_votes: list) -> dict:
        active_drones = [d for d in self.drone_ids if d not in self.blacklist and d != suspect_drone_id]
        total = len(active_drones)
        if total == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}
        votes_for = sum(1 for _, vote in blacklist_votes if vote)
        vote_rate = votes_for / total
        if vote_rate >= self.QUORUM:
            if suspect_drone_id not in self.blacklist:
                self.blacklist.append(suspect_drone_id)
            status = "BLACKLISTED"
        else:
            status = "CLEARED"
        return {
            "suspect": suspect_drone_id,
            "total_voters": total,
            "votes_for_blacklist": votes_for,
            "vote_rate": round(vote_rate, 2),
            "status": status,
            "timestamp": int(time.time())
        }

    def get_swarm_status(self) -> dict:
        log_hash = hashlib.sha256(str(self.votes_log).encode()).hexdigest()
        return {
            "total_drones": len(self.drone_ids),
            "active_drones": len(self.drone_ids) - len(self.blacklist),
            "blacklisted": self.blacklist,
            "votes_cast": len(self.votes_log),
            "log_hash": log_hash,
            "on_chain_ready": True
        }
'''

files["dronesync/emergency.py"] = '''"""
DroneSync - Emergency Override Protocol
"""
import hashlib
import time

EMERGENCY_TYPES = {
    "FIRE":          {"priority": 10, "action": "ASSIST_FIRE",    "radius_m": 500,  "needs": ["fire", "cargo", "patrol"]},
    "ACCIDENT":      {"priority": 8,  "action": "SCOUT_AREA",     "radius_m": 300,  "needs": ["patrol", "surveillance", "cargo"]},
    "SEARCH_RESCUE": {"priority": 9,  "action": "SEARCH_PATTERN", "radius_m": 1000, "needs": ["patrol", "surveillance", "cargo", "medical"]},
    "HAZMAT":        {"priority": 10, "action": "EVACUATE_ZONE",  "radius_m": 800,  "needs": ["hazmat", "patrol", "cargo"]},
    "MEDICAL_EMERGENCY": {"priority": 9, "action": "DELIVER_SUPPLIES", "radius_m": 400, "needs": ["medical", "cargo"]},
}

MISSION_DRONE_TYPE = {
    "organ_delivery":    "medical",
    "medical_delivery":  "medical",
    "urban_delivery":    "cargo",
    "patrol":            "patrol",
    "surveillance":      "surveillance",
    "inspection":        "patrol",
    "fire_support":      "fire",
    "hazmat_support":    "hazmat",
}


class EmergencyOverride:
    def __init__(self):
        self.active_emergencies = []
        self.redirected_drones = []
        self.protected_drones = []

    def broadcast_emergency(self, emergency_type: str, location: dict, authority_id: str) -> dict:
        if emergency_type not in EMERGENCY_TYPES:
            return {"status": "REJECTED", "reason": "unknown_emergency_type"}
        config = EMERGENCY_TYPES[emergency_type]
        timestamp = int(time.time())
        emergency = {
            "emergency_id": "EMG_" + str(timestamp),
            "type": emergency_type,
            "location": location,
            "authority_id": authority_id,
            "action": config["action"],
            "priority": config["priority"],
            "radius_m": config["radius_m"],
            "needs": config["needs"],
            "timestamp": timestamp,
            "status": "ACTIVE"
        }
        self.active_emergencies.append(emergency)
        return emergency

    def check_drone_override(self, drone_position: list, emergency: dict,
                              mission_type: str = "urban_delivery") -> dict:
        import math
        elat = emergency["location"]["lat"]
        elon = emergency["location"]["lon"]
        dlat = math.radians(drone_position[0] - elat)
        dlon = math.radians(drone_position[1] - elon)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(drone_position[0])) *
             math.cos(math.radians(elat)) *
             math.sin(dlon/2)**2)
        dist = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        if dist > emergency["radius_m"]:
            return {"override": False, "reason": "outside_radius"}

        drone_type = MISSION_DRONE_TYPE.get(mission_type, "cargo")
        needed_types = emergency.get("needs", [])

        if drone_type not in needed_types:
            self.protected_drones.append({
                "position": drone_position[:2],
                "mission_type": mission_type,
                "drone_type": drone_type,
                "emergency_type": emergency["type"],
                "reason": "incompatible_type",
                "timestamp": int(time.time())
            })
            return {
                "override": False,
                "reason": "incompatible_drone_type",
                "drone_type": drone_type,
                "emergency_needs": needed_types,
                "note": "wrong drone type - emergency has dedicated resources"
            }

        self.redirected_drones.append({
            "position": drone_position[:2],
            "emergency_id": emergency["emergency_id"],
            "distance_m": round(dist, 1),
            "timestamp": int(time.time())
        })
        return {
            "override": True,
            "action": emergency["action"],
            "emergency_id": emergency["emergency_id"],
            "distance_to_emergency_m": round(dist, 1),
            "drone_type": drone_type,
            "mission_type": mission_type
        }

    def get_status(self) -> dict:
        status_hash = hashlib.sha256(str(self.active_emergencies).encode()).hexdigest()
        return {
            "active_emergencies": len(self.active_emergencies),
            "redirected_drones": len(self.redirected_drones),
            "protected_drones": len(self.protected_drones),
            "status_hash": status_hash,
            "on_chain_ready": True
        }
'''

files["dronesync/storage.py"] = '''"""
DroneSync - Persistent Storage
"""
import json
import os
import time

STORAGE_DIR = ".dronesync_data"


class DroneStorage:
    def __init__(self, drone_id: str, storage_dir: str = STORAGE_DIR):
        self.drone_id = drone_id
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.path = os.path.join(storage_dir, drone_id + ".json")

    def save(self, data: dict):
        data["drone_id"] = self.drone_id
        data["last_saved"] = int(time.time())
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def append_mission(self, mission_record: dict):
        state = self.load()
        if "missions" not in state:
            state["missions"] = []
        state["missions"].append(mission_record)
        state["missions"] = state["missions"][-1000:]
        self.save(state)

    def get_missions(self) -> list:
        return self.load().get("missions", [])

    def update_reputation(self, score: int, tier: str):
        state = self.load()
        state["reputation_score"] = score
        state["reputation_tier"] = tier
        self.save(state)

    def get_reputation(self) -> dict:
        state = self.load()
        return {
            "score": state.get("reputation_score", 50),
            "tier": state.get("reputation_tier", "ROOKIE")
        }

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
'''

files["dronesync/sensor_bundle.py"] = '''"""
DroneSync - Sensor Bundle
"""
import hashlib
import json
import time


class SensorBundle:
    VERSION = "1.0"

    def pack(self, mission_id: str, trajectory, sensor_data, popw_record: dict,
             drone_id: str = "DRONE_001") -> dict:
        trajectory_summary = {
            "positions_count": len(trajectory.positions),
            "origin": trajectory.positions[0][:2],
            "destination": trajectory.positions[-1][:2],
            "planner_steps": trajectory.metadata.get("planner_steps", []),
            "steps_hash": trajectory.metadata.get("steps_hash", ""),
        }
        sensor_summary = {
            "lidar_points": len(sensor_data.lidar_points),
            "camera_detections": sensor_data.camera_detections,
            "imu_data": sensor_data.imu_data,
            "timestamp": sensor_data.timestamp,
        }
        sensor_hash = hashlib.sha256(json.dumps(sensor_summary, sort_keys=True).encode()).hexdigest()
        bundle = {
            "bundle_version": self.VERSION,
            "mission_id": mission_id,
            "drone_id": drone_id,
            "timestamp": int(time.time()),
            "trajectory": trajectory_summary,
            "sensor_hash": sensor_hash,
            "sensor_detections": sensor_data.camera_detections,
            "popw": {
                "mission_id": popw_record["mission_id"],
                "trajectory_hash": popw_record["trajectory_hash"],
                "score": popw_record["score"],
                "attestation_id": popw_record["attestation"]["attestation_id"],
                "tee_status": popw_record["attestation"]["status"],
                "on_chain_string": self._format_chain_string(popw_record),
            },
        }
        bundle["bundle_hash"] = hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest()
        bundle["on_chain_ready"] = True
        return bundle

    def verify(self, bundle: dict) -> dict:
        stored_hash = bundle.get("bundle_hash")
        check = {k: v for k, v in bundle.items() if k not in ("bundle_hash", "on_chain_ready")}
        recomputed = hashlib.sha256(json.dumps(check, sort_keys=True).encode()).hexdigest()
        if stored_hash == recomputed:
            return {"valid": True, "mission_id": bundle["mission_id"],
                    "bundle_hash": stored_hash, "score": bundle["popw"]["score"],
                    "tee_status": bundle["popw"]["tee_status"]}
        return {"valid": False, "reason": "bundle_hash_mismatch"}

    def _format_chain_string(self, popw_record: dict) -> str:
        return ("POPW|" + popw_record["mission_id"] + "|" +
                popw_record["trajectory_hash"][:16] + "|" +
                str(popw_record["score"]) + "|" +
                popw_record["attestation"]["attestation_hash"][:16])
'''

files["validator/scoreroot.py"] = '''"""
DroneSync - ScoreRoot
"""
import hashlib
import time
import json


class ScoreRoot:
    def __init__(self, validator_id: str):
        self.validator_id = validator_id
        self.scores = []
        self.commitments = []

    def add_score(self, mission_id: str, score: int, trajectory_hash: str, sensor_hash: str):
        entry = {
            "mission_id": mission_id,
            "score": score,
            "trajectory_hash": trajectory_hash,
            "sensor_hash": sensor_hash,
            "timestamp": int(time.time()),
            "validator_id": self.validator_id
        }
        entry["entry_hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        self.scores.append(entry)

    def compute_root(self) -> str:
        if not self.scores:
            return hashlib.sha256(b"empty").hexdigest()
        hashes = [s["entry_hash"] for s in self.scores]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def commit(self) -> dict:
        root = self.compute_root()
        commitment = {
            "score_root": root,
            "validator_id": self.validator_id,
            "scores_count": len(self.scores),
            "timestamp": int(time.time()),
            "on_chain_ready": True
        }
        commitment["commitment_hash"] = hashlib.sha256(json.dumps(commitment, sort_keys=True).encode()).hexdigest()
        self.commitments.append(commitment)
        return commitment

    def verify_score(self, mission_id: str) -> dict:
        entry = next((s for s in self.scores if s["mission_id"] == mission_id), None)
        if not entry:
            return {"verified": False, "reason": "mission_not_found"}
        if not self.commitments:
            return {"verified": False, "reason": "no_commitment_yet"}
        return {
            "verified": True,
            "mission_id": mission_id,
            "score": entry["score"],
            "entry_hash": entry["entry_hash"],
            "score_root": self.commitments[-1]["score_root"]
        }
'''

files["tests/test_phase1.py"] = '''"""Tests for Phase 1: Reputation, Firewall, Last Will"""
import time
from dronesync.reputation import DroneReputation
from dronesync.firewall import DroneFirewall
from dronesync.last_will import DroneLastWill


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
    assert rep.get_status()["on_chain_ready"] is True


def test_firewall_allows_valid_command():
    fw = DroneFirewall("DRONE_001")
    cmd = {"action": "fly", "source": "op", "timestamp": int(time.time()), "signature": "abc"}
    assert fw.filter(cmd)["status"] == "ALLOWED"

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
    assert fw.get_report()["on_chain_ready"] is True


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
'''

files["tests/test_phase2.py"] = '''"""Tests for Phase 2: Memory, Swarm Consensus, Emergency Override"""
from dronesync.memory import DroneMemory
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.emergency import EmergencyOverride


def test_memory_records_flight():
    mem = DroneMemory("DRONE_001")
    positions = [[47.37, 8.54, 50, 0], [47.38, 8.545, 50, 5]]
    mem.record_flight(positions, duration_s=120.0)
    assert mem.missions_completed == 1

def test_memory_flight_hours():
    mem = DroneMemory("DRONE_001")
    mem.record_flight([[47.37, 8.54, 50, 0]], duration_s=3600.0)
    assert mem.total_flight_hours == 1.0

def test_memory_on_chain_ready():
    mem = DroneMemory("DRONE_001")
    assert mem.get_memory_record()["on_chain_ready"] is True

def test_memory_asset_value_low():
    mem = DroneMemory("DRONE_001")
    assert mem.get_memory_record()["asset_value"] == "LOW"

def test_memory_asset_value_high():
    mem = DroneMemory("DRONE_001")
    mem.missions_completed = 100
    assert mem.get_memory_record()["asset_value"] == "HIGH"


def test_consensus_approves_majority_vote():
    c = SwarmConsensus(["d0", "d1", "d2"])
    result = c.vote_on_route("M1", [("d0", True), ("d1", True), ("d2", False)])
    assert result["status"] == "APPROVED"

def test_consensus_rejects_minority_vote():
    c = SwarmConsensus(["d0", "d1", "d2"])
    result = c.vote_on_route("M1", [("d0", True), ("d1", False), ("d2", False)])
    assert result["status"] == "REJECTED"

def test_consensus_blacklist_drone():
    c = SwarmConsensus(["d0", "d1", "d2", "d3"])
    result = c.vote_blacklist("d3", [("d0", True), ("d1", True), ("d2", True)])
    assert result["status"] == "BLACKLISTED"
    assert "d3" in c.blacklist

def test_consensus_on_chain_ready():
    c = SwarmConsensus(["d0", "d1"])
    assert c.get_swarm_status()["on_chain_ready"] is True


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
    assert eo.get_status()["on_chain_ready"] is True

def test_medical_not_redirected_by_fire():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type="organ_delivery")
    assert result["override"] is False
    assert result["reason"] == "incompatible_drone_type"

def test_fire_overrides_cargo_delivery():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type="urban_delivery")
    assert result["override"] is True

def test_medical_emergency_redirects_medical_drone():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("MEDICAL_EMERGENCY", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    result = eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type="medical_delivery")
    assert result["override"] is True

def test_protected_drones_counted():
    eo = EmergencyOverride()
    em = eo.broadcast_emergency("FIRE", {"lat": 47.3780, "lon": 8.5430}, "AUTH_001")
    eo.check_drone_override([47.3782, 8.5432, 50.0], em, mission_type="organ_delivery")
    assert eo.get_status()["protected_drones"] == 1
'''

# Create all files
created = []
for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    created.append(path)
    print("created: " + path)

print("\nDone! Created " + str(len(created)) + " files.")
print("Now run:")
print("  python -m pytest tests/ -v")
print("  git add .")
print("  git commit -m 'Add Phase 1+2: Reputation, Firewall, LastWill, Memory, Consensus, Emergency, Storage, SensorBundle, ScoreRoot'")
print("  git push")
