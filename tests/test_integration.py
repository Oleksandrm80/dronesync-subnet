import time
from miner.planner import DronePlanner, AIPlanner
from dronesync.protocol import MissionInstruction, MissionType, Waypoint
from dronesync.threat_defense import ThreatDefense
from dronesync.security import DroneSecuritySuite
from dronesync.verifier import TEEAttestation, PoPWRecord
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.reputation import DroneReputation
from dronesync.firewall import DroneFirewall
from dronesync.replay_guard import ReplayGuard
from dronesync.mission_history import MissionHistory
from validator.scorer import DroneEvaluator


ORIGIN = Waypoint(47.3769, 8.5417, 100.0)
DEST = Waypoint(47.3800, 8.5450, 100.0)
WAYPOINTS = [Waypoint(47.3780, 8.5430, 100.0)]


def make_mission(mission_id):
    return MissionInstruction(
        mission_id=mission_id,
        mission_type=MissionType.URBAN_DELIVERY,
        origin=ORIGIN,
        destination=DEST,
        waypoints=WAYPOINTS
    )


def test_full_mission_pipeline():
    # Step 1: Plan trajectory
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(make_mission("INTEG_001"))
    assert len(trajectory.positions) >= 2

    # Step 2: Threat defense
    td = ThreatDefense()
    threat = td.full_threat_assessment(trajectory.positions)
    assert threat["overall_threat_level"] == "NONE"

    # Step 3: Security check
    suite = DroneSecuritySuite()
    assessment = suite.full_security_check(trajectory, score=100)
    assert assessment["overall_status"] == "SECURE"

    # Step 4: Score
    scorer = DroneEvaluator()
    sensor_data = [{"battery_pct": 95, "signal_strength": 0.9, "lidar_points": 150}]
    score = scorer.score(trajectory, sensor_data)
    assert score >= 80

    # Step 5: PoPW attestation
    mission_id = f"DSYNC_INTEG_{int(time.time())}"
    tee = TEEAttestation()
    import hashlib
    traj_hash = hashlib.sha256(str(trajectory.positions).encode()).hexdigest()
    attestation = tee.attest_mission(mission_id, traj_hash, score)
    assert attestation["status"] == "SIGNED"
    record = PoPWRecord()
    popw = record.create_record(mission_id, trajectory, score)
    assert popw["on_chain_ready"] is True
    # Step 6: Replay guard
    rg = ReplayGuard()
    check = rg.check(mission_id, time.time())
    assert check["allowed"] is True
    rg.register(mission_id)
    check2 = rg.check(mission_id, time.time())
    assert check2["allowed"] is False

    # Step 7: Reputation update
    rep = DroneReputation("DRONE_001")
    rep.record_mission("INTEG_001", score, mission_safe=True, battery_used_pct=8.0)
    status = rep.get_status()
    assert status["score"] >= 50
    assert status["on_chain_ready"] is True

    # Step 8: Consensus
    consensus = SwarmConsensus(["drone_0", "drone_1", "drone_2"])
    votes = [("drone_0", True), ("drone_1", True), ("drone_2", True)]
    result = consensus.vote_on_route(mission_id, votes)
    assert result["status"] == "APPROVED"
def test_ai_planner_pipeline():
    planner = AIPlanner()
    trajectory = planner.plan_trajectory(make_mission("INTEG_002"))
    assert len(trajectory.positions) >= 2
    planner.learn_from_score(95)
    scorer = DroneEvaluator()
    sensor_data = [{"battery_pct": 90, "signal_strength": 0.85, "lidar_points": 120}]
    score = scorer.score(trajectory, sensor_data)
    assert score >= 80


def test_firewall_blocks_invalid_then_allows_valid():
    import json
    import hmac
    import hashlib
    fw = DroneFirewall("DRONE_001")
    bad_cmd = {"action": "fly", "source": "hacker", "timestamp": int(time.time()), "signature": "fake"}
    result = fw.filter(bad_cmd)
    assert result["status"] == "BLOCKED"
    good_cmd = {"action": "fly", "source": "op", "timestamp": int(time.time())}
    sig = hmac.new(fw._secret, json.dumps(good_cmd, sort_keys=True).encode(), hashlib.sha256).hexdigest()
    good_cmd["signature"] = sig
    result2 = fw.filter(good_cmd)
    assert result2["status"] == "ALLOWED"


def test_mission_history_integrity():
    history = MissionHistory()
    history.add("DSYNC_001", score=95, duration_s=120, battery_used=8.0)
    history.add("DSYNC_002", score=90, duration_s=130, battery_used=8.5)
    stats = history.stats()
    assert stats["total_missions"] >= 2
    assert stats["avg_score"] >= 90
    assert stats["chain_valid"] is True
    assert len(stats["chain_root"]) == 64
