from dronesync.synapse import demo_synapse
from dronesync.threat_defense import ThreatDefense
from dronesync.node import KonnexNode
from environment.obstacles import DynamicObstacleManager
from dronesync.mission_history import MissionHistory
from miner.planner import DronePlanner, AIPlanner
from miner.citymap import CityMap
from environment.sim import DroneEnvironment, SwarmEnvironment
from validator.scorer import DroneEvaluator
from validator.scoreroot import ScoreRoot
from dronesync.verifier import PoPWRecord
from dronesync.security import DroneSecuritySuite, CommandSigner
from miner.weather import WeatherService, WeatherImpactAnalyzer
from miner.energy import EnergyOptimizer, BatteryModel
from dronesync.reputation import DroneReputation
from dronesync.firewall import DroneFirewall
from dronesync.last_will import DroneLastWill
from dronesync.memory import DroneMemory
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.emergency import EmergencyOverride
from dronesync.storage import DroneStorage
from dronesync.sensor_bundle import SensorBundle
from dronesync.logger import get_logger
logger = get_logger("dronesync.main")

class FakeMission:
    def __init__(self, origin=(47.3769, 8.5417), destination=(47.3800, 8.5450)):
        self.mission_id = "DSYNC_" + str(int(__import__("time").time()))
        self.origin = type("obj", (), {
            "lat": origin[0], "lon": origin[1], "alt": 50, "speed": 5
        })
        self.waypoints = [
            type("obj", (), {"lat": 47.3780, "lon": 8.5430, "alt": 50, "speed": 5}),
        ]
        self.destination = type("obj", (), {
            "lat": destination[0], "lon": destination[1], "alt": 50, "speed": 5
        })
        self.mission_type = type("obj", (), {"value": "urban_delivery"})


def run_single_drone():
    logger.info("=" * 50)
    logger.info("SINGLE DRONE MISSION")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    logger.info("trajectory created")
    steps = trajectory.metadata.get("planner_steps", [])
    logger.info("planner_steps: " + str(len(steps)))
    for s in steps:
        logger.info("  step " + str(s["step"]) + ": " + s["action"] +
              " lat=" + str(s["lat"]) + " lon=" + str(s["lon"]))
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    logger.info("environment simulation done")
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)
    logger.info("score computed: %s", score)
    replay = validator.replay_validate(trajectory)
    logger.info("replay_validation: " + replay["status"] +
          " | steps=" + str(replay.get("steps_count", 0)) +
          " | " + replay["reason"])
    logger.info("")


def run_swarm():
    logger.info("=" * 50)
    logger.info("SWARM MISSION - 3 DRONES")
    logger.info("=" * 50)
    missions = [
        FakeMission(origin=(47.3769, 8.5417), destination=(47.3820, 8.5460)),
        FakeMission(origin=(47.3775, 8.5420), destination=(47.3825, 8.5465)),
        FakeMission(origin=(47.3780, 8.5425), destination=(47.3830, 8.5470)),
    ]
    planner = DronePlanner()
    trajectories = [planner.plan_trajectory(m) for m in missions]
    logger.info(str(len(trajectories)) + " trajectories planned")
    swarm = SwarmEnvironment(n_drones=3)
    results = swarm.run_swarm(trajectories)
    for drone_id, result in results.items():
        status = result["status"]
        predicted = result["conflicts_predicted"]
        maneuvers = len(result["avoidance_maneuvers"])
        logger.info(drone_id + ": status=" + status +
              ", conflicts_predicted=" + str(predicted) +
              ", avoidance_maneuvers=" + str(maneuvers))
    logger.info("")


def run_ai_planner():
    logger.info("=" * 50)
    logger.info("AI PLANNER - LEARNING MODE")
    logger.info("=" * 50)
    ai_planner = AIPlanner()
    validator = DroneEvaluator()
    env = DroneEnvironment()
    for i in range(3):
        mission = FakeMission()
        trajectory = ai_planner.plan_trajectory(mission)
        sensor_data = env.run(trajectory)
        score = validator.score(trajectory, sensor_data)
        ai_planner.learn_from_score(score)
        weights = ai_planner.learned_weights
        logger.info("mission " + str(i+1) + ": score=" + str(score) +
              " | safety=" + str(round(weights["safety"], 2)) +
              " efficiency=" + str(round(weights["efficiency"], 2)))
    logger.info("AI planner trained on 3 missions")
    logger.info("")


def run_city_map():
    logger.info("=" * 50)
    logger.info("CITY MAP - ZURICH URBAN AIRSPACE")
    logger.info("=" * 50)
    city = CityMap(city="zurich")
    stats = city.get_city_stats()
    logger.info("city: " + stats["city"])
    logger.info("no-fly zones: " + str(stats["no_fly_zones"]))
    logger.info("zone types: " + str(stats["zone_types"]))
    test_points = [
        (47.3769, 8.5417, "city center"),
        (47.4647, 8.5492, "near airport"),
        (47.3744, 8.5373, "near hospital"),
    ]
    logger.info("")
    for lat, lon, name in test_points:
        no_fly, reason = city.is_no_fly(lat, lon)
        safe_alt = city.safe_altitude(lat, lon)
        status = "NO-FLY: " + str(reason) if no_fly else "CLEAR"
        logger.info(name + ": " + status + " | safe_alt=" + str(safe_alt) + "m")
    logger.info("")


def run_tee():
    logger.info("=" * 50)
    logger.info("TEE ATTESTATION - PoPW RECORD")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    validator = DroneEvaluator()
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    score = validator.score(trajectory, sensor_data)
    popw = PoPWRecord()
    record = popw.create_record(
        mission_id=mission.mission_id,
        trajectory=trajectory,
        score=score
    )
    logger.info("mission_id: " + record["mission_id"])
    logger.info("score: " + str(record["score"]))
    logger.info("trajectory_hash: " + record["trajectory_hash"][:16] + "...")
    logger.info("attestation: " + record["attestation"]["attestation_id"])
    logger.info("tee_status: " + record["attestation"]["status"])
    logger.info("on_chain_ready: " + str(record["on_chain_ready"]))
    chain_str = popw.format_for_chain(record)
    logger.info("on-chain string: " + chain_str)
    logger.info("")


def run_security():
    logger.info("=" * 50)
    logger.info("SECURITY SUITE - THREAT DETECTION")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)

    security = DroneSecuritySuite()
    result = security.full_security_check(trajectory, score)

    logger.info("overall_status: " + result["overall_status"])
    logger.info("gps_spoofing: " + result["gps_spoofing"])
    logger.info("hijacking: " + result["hijacking"])
    logger.info("threat_level: " + result["threat_level"])
    logger.info("mission_cleared: " + str(result["mission_cleared"]))

    signer = CommandSigner()
    cmd = {"action": "fly", "destination": "47.3800,8.5450", "priority": 1}
    signed = signer.sign_command(cmd)
    verified = signer.verify_command(signed)
    logger.info("command_signed: True")
    logger.info("command_verified: " + str(verified))
    logger.info("")

def run_weather():
    logger.info("=" * 50)
    logger.info("WEATHER MODULE - ZURICH CONDITIONS")
    logger.info("=" * 50)
    weather_service = WeatherService(city="zurich")
    weather = weather_service.get_current()
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    analyzer = WeatherImpactAnalyzer()
    impact = analyzer.analyze(weather, trajectory.positions)
    logger.info("flyable: " + str(impact["flyable"]))
    logger.info("severity: " + impact["severity"])
    logger.info("wind: " + str(impact["wind_speed_ms"]) + " m/s")
    logger.info("visibility: " + str(impact["visibility_m"]) + "m")
    logger.info("precipitation: " + impact["precipitation"])
    logger.info("speed_factor: " + str(impact["speed_factor"]))
    logger.info("energy_factor: " + str(impact["energy_factor"]))
    logger.info("recommendation: " + impact["recommendation"])
    logger.info("")
def run_energy():
    logger.info("=" * 50)
    logger.info("ENERGY OPTIMIZER")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    battery = BatteryModel(capacity_wh=100.0, payload_kg=0.5)
    optimizer = EnergyOptimizer(battery=battery)
    result = optimizer.analyze_trajectory(trajectory.positions, wind_ms=3.0)
    logger.info("total_distance_km: " + str(result["total_distance_km"]))
    logger.info("battery_used_pct: " + str(result["battery_used_pct"]) + "%")
    logger.info("battery_remaining_pct: " + str(result["battery_remaining_pct"]) + "%")
    logger.info("efficiency_rating: " + result["efficiency_rating"])
    logger.info("mission_feasible: " + str(result["mission_feasible"]))
    logger.info("recommendation: " + result["recommendation"])
    optimal = optimizer.optimal_speed(wind_ms=3.0)
    logger.info("optimal_speed_ms: " + str(optimal))
    logger.info("")
def run_history():
    logger.info("=" * 50)
    logger.info("MISSION HISTORY & STATISTICS")
    logger.info("=" * 50)
    history = MissionHistory()
    for i in range(5):
        history.add(
            mission_id="DSYNC_" + str(1780000000 + i),
            score=97 - i,
            duration_s=25.0 + i,
            battery_used=7.0 + i * 0.5,
            weather="CLEAR",
            security="SECURE"
        )
    stats = history.stats()
    logger.info("total_missions: " + str(stats["total_missions"]))
    logger.info("avg_score: " + str(stats["avg_score"]))
    logger.info("max_score: " + str(stats["max_score"]))
    logger.info("success_rate: " + str(stats["success_rate_pct"]) + "%")
    logger.info("")
    logger.info("last 3 missions:")
    for m in history.last(3):
        logger.info("  " + m["mission_id"] + " | score=" + str(m["score"]) +
              " | battery=" + str(m["battery_used_pct"]) + "%")
    logger.info("")
def run_obstacles():
    logger.info("=" * 50)
    logger.info("DYNAMIC OBSTACLES - URBAN AIRSPACE")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    manager = DynamicObstacleManager()
    result = manager.check_trajectory(trajectory.positions)
    logger.info("obstacles_tracked: " + str(result["obstacles_tracked"]))
    logger.info("conflicts_found: " + str(result["conflicts_found"]))
    logger.info("trajectory_safe: " + str(result["trajectory_safe"]))
    logger.info("recommendation: " + result["recommendation"])
    if result["conflicts"]:
        for c in result["conflicts"]:
            logger.info("  conflict: " + c["obstacle_id"] +
                  " type=" + c["type"] +
                  " dist=" + str(c["distance_m"]) + "m")
def run_threat_defense():
    logger.info("=" * 50)
    logger.info("THREAT DEFENSE - REAL ATTACK VECTORS")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    defense = ThreatDefense()
    result = defense.full_threat_assessment(
        trajectory.positions,
        signal_strength=0.92
    )
    logger.info("overall_threat_level: " + result["overall_threat_level"])
    logger.info("gps_status: " + result["gps_status"])
    logger.info("jamming_status: " + result["jamming_status"])
    logger.info("swarm_integrity: " + result["swarm_integrity"])
    logger.info("mission_safe: " + str(result["mission_safe"]))
    logger.info("total_threats: " + str(result["total_threats"]))
    node = KonnexNode(
        wallet_address="0x5a4E...51f2",
        network="testnet"
    )
    node.connect()
    status = node.get_status()
    logger.info("")
    logger.info("node_connected: " + str(status["connected"]))
    logger.info("network: " + status["network"])
    logger.info("session_id: " + str(status["session_id"]))
    logger.info("")
    logger.info("")
def run_reputation():
    logger.info("=" * 50)
    logger.info("DRONE REPUTATION SCORE")
    logger.info("=" * 50)
    rep = DroneReputation(drone_id="DRONE_001")
    missions = [
        ("DSYNC_001", 97, True, 7.0),
        ("DSYNC_002", 95, True, 7.5),
        ("DSYNC_003", 92, True, 8.0),
        ("DSYNC_004", 55, False, 45.0),
        ("DSYNC_005", 98, True, 6.5),
    ]
    for mission_id, score, safe, battery in missions:
        rep.record_mission(mission_id, score, safe, battery)
    status = rep.get_status()
    logger.info("drone_id: " + status["drone_id"])
    logger.info("reputation_score: " + str(status["score"]))
    logger.info("tier: " + status["tier"])
    logger.info("total_missions: " + str(status["missions_count"]))
    logger.info("on_chain_ready: " + str(status["on_chain_ready"]))
    logger.info("")


def run_firewall():
    logger.info("=" * 50)
    logger.info("DRONE FIREWALL - COMMAND FILTER")
    logger.info("=" * 50)
    fw = DroneFirewall(drone_id="DRONE_001")
    import time
    now = int(time.time())
    commands = [
        {"action": "fly", "source": "operator", "timestamp": now, "signature": "abc123"},
        {"action": "fly", "source": "operator", "timestamp": now},
        {"action": "hack", "source": "unknown", "timestamp": now, "signature": "xyz"},
        {"action": "land", "source": "operator", "timestamp": now - 60, "signature": "abc123"},
        {"action": "hover", "source": "operator", "timestamp": now, "signature": "def456"},
    ]
    for cmd in commands:
        result = fw.filter(cmd)
        logger.info("action=" + cmd["action"] + " → " + result["status"] +
              (" | reason=" + result["reason"] if result["status"] == "BLOCKED" else ""))
    report = fw.get_report()
    logger.info("total_allowed: " + str(report["total_allowed"]))
    logger.info("total_blocked: " + str(report["total_blocked"]))
    logger.info("on_chain_ready: " + str(report["on_chain_ready"]))
    logger.info("")


def run_last_will():
    logger.info("=" * 50)
    logger.info("DRONE LAST WILL - EMERGENCY PoPW")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    last_will = DroneLastWill(drone_id="DRONE_001")
    record = last_will.simulate_crash(trajectory.positions, mission.mission_id)
    logger.info("type: " + record["type"])
    logger.info("drone_id: " + record["drone_id"])
    logger.info("failure_cause: " + record["failure_cause"])
    logger.info("battery_pct: " + str(record["battery_pct"]) + "%")
    logger.info("last_position: lat=" + str(record["last_position"]["lat"]) +
          " lon=" + str(record["last_position"]["lon"]))
    logger.info("will_hash: " + record["will_hash"][:16] + "...")
    logger.info("insurance_claim_ready: " + str(record["insurance_claim_ready"]))
    logger.info("on_chain_ready: " + str(record["on_chain_ready"]))
    logger.info("")


def run_memory():
    logger.info("=" * 50)
    logger.info("DRONE MEMORY - FLIGHT EXPERIENCE")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    mem = DroneMemory(drone_id="DRONE_001")
    for i in range(5):
        mem.record_flight(trajectory.positions, duration_s=120.0, wind_ms=3.0)
    record = mem.get_memory_record()
    logger.info("drone_id: " + record["drone_id"])
    logger.info("missions_completed: " + str(record["missions_completed"]))
    logger.info("total_flight_hours: " + str(record["total_flight_hours"]))
    logger.info("asset_value: " + record["asset_value"])
    logger.info("on_chain_ready: " + str(record["on_chain_ready"]))
    logger.info("")


def run_swarm_consensus():
    logger.info("=" * 50)
    logger.info("SWARM CONSENSUS - DECENTRALIZED VOTING")
    logger.info("=" * 50)
    drones = ["drone_0", "drone_1", "drone_2", "drone_3", "drone_4"]
    consensus = SwarmConsensus(drone_ids=drones)
    votes = [(d, True) for d in drones[:4]] + [("drone_4", False)]
    result = consensus.vote_on_route("DSYNC_001", votes)
    logger.info("mission_id: DSYNC_001")
    logger.info("approval_weight: " + str(result["approval_weight"]) + "/" + str(result["total_weight"]))    
    logger.info("approval_rate: " + str(result["approval_rate"]))
    logger.info("route_status: " + result["status"])
    bl_votes = [(d, True) for d in ["drone_0", "drone_1", "drone_2"]] + [("drone_3", False)]
    bl_result = consensus.vote_blacklist("drone_4", bl_votes)
    logger.info("blacklist_vote: drone_4 -> " + bl_result["status"])
    status = consensus.get_swarm_status()
    logger.info("active_drones: " + str(status["active_drones"]) + "/" + str(status["total_drones"]))
    logger.info("on_chain_ready: " + str(status["on_chain_ready"]))
    logger.info("")


def run_emergency():
    logger.info("=" * 50)
    logger.info("EMERGENCY OVERRIDE PROTOCOL")
    logger.info("=" * 50)
    override = EmergencyOverride()
    emergency = override.broadcast_emergency(
        emergency_type="FIRE",
        location={"lat": 47.3780, "lon": 8.5430},
        authority_id="ZURICH_FIRE_DEPT_001"
    )
    logger.info("emergency_id: " + emergency["emergency_id"])
    logger.info("type: " + emergency["type"] + " | needs: " + str(emergency["needs"]))
    drone_pos = [47.3782, 8.5432, 50.0]
    # cargo дрон — перехватывается пожаром
    c1 = override.check_drone_override(drone_pos, emergency, mission_type="urban_delivery")
    logger.info("urban_delivery (cargo): override=" + str(c1["override"]) + " -> " + c1.get("action", c1.get("reason", "")))
    # medical дрон — пожарной службе не нужен
    c2 = override.check_drone_override(drone_pos, emergency, mission_type="organ_delivery")
    logger.info("organ_delivery (medical): override=" + str(c2["override"]) + " -> " + c2.get("reason", "") + " | " + c2.get("note", ""))
    # medical emergency — нужен именно medical дрон
    med_em = override.broadcast_emergency("MEDICAL_EMERGENCY", {"lat": 47.3780, "lon": 8.5430}, "ZURICH_HOSPITAL_001")
    c3 = override.check_drone_override(drone_pos, med_em, mission_type="organ_delivery")
    logger.info("organ_delivery vs MEDICAL_EMERGENCY: override=" + str(c3["override"]) + " -> " + c3.get("action", c3.get("reason", "")))
    status = override.get_status()
    logger.info("redirected_drones: " + str(status["redirected_drones"]))
    logger.info("protected_drones: " + str(status["protected_drones"]))
    logger.info("on_chain_ready: " + str(status["on_chain_ready"]))
    logger.info("")


def run_storage():
    logger.info("=" * 50)
    logger.info("PERSISTENT STORAGE - DRONE STATE")
    logger.info("=" * 50)
    storage = DroneStorage(drone_id="DRONE_001")
    storage.clear()
    for i in range(3):
        storage.append_mission({
            "mission_id": "DSYNC_" + str(1780000000 + i),
            "score": 97 - i,
            "duration_s": 120.0,
            "timestamp": int(__import__("time").time())
        })
    storage.update_reputation(score=72, tier="TRUSTED")
    missions = storage.get_missions()
    rep = storage.get_reputation()
    logger.info("drone_id: DRONE_001")
    logger.info("missions_saved: " + str(len(missions)))
    logger.info("last_mission: " + missions[-1]["mission_id"] + " | score=" + str(missions[-1]["score"]))
    logger.info("reputation_score: " + str(rep["score"]) + " | tier: " + rep["tier"])
    logger.info("persisted_to_disk: True")
    logger.info("survives_restart: True")
    logger.info("")


def run_sensor_bundle():
    logger.info("=" * 50)
    logger.info("SENSOR BUNDLE - EVIDENCE PACKAGE")
    logger.info("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    popw = PoPWRecord()
    record = popw.create_record(mission.mission_id, trajectory, 97)
    bundle = SensorBundle().pack(
        mission_id=mission.mission_id,
        trajectory=trajectory,
        sensor_data=sensor_data,
        popw_record=record
    )
    verify = SensorBundle().verify(bundle)
    logger.info("mission_id: " + bundle["mission_id"])
    logger.info("sensor_hash: " + bundle["sensor_hash"][:16] + "...")
    logger.info("bundle_hash: " + bundle["bundle_hash"][:16] + "...")
    logger.info("tee_status: " + bundle["popw"]["tee_status"])
    logger.info("bundle_valid: " + str(verify["valid"]))
    logger.info("on_chain_ready: " + str(bundle["on_chain_ready"]))
    logger.info("")


def run_scoreroot():
    logger.info("=" * 50)
    logger.info("SCORE ROOT - VALIDATOR COMMITMENT")
    logger.info("=" * 50)
    sr = ScoreRoot(validator_id="VALIDATOR_001")
    missions = [
        ("DSYNC_001", 97, "abc123", "def456"),
        ("DSYNC_002", 94, "bcd234", "efg567"),
        ("DSYNC_003", 91, "cde345", "fgh678"),
    ]
    for mid, score, th, sh in missions:
        sr.add_score(mid, score, th, sh)
    commitment = sr.commit()
    logger.info("validator_id: " + sr.validator_id)
    logger.info("scores_count: " + str(commitment["scores_count"]))
    logger.info("score_root: " + commitment["score_root"][:16] + "...")
    logger.info("on_chain_ready: " + str(commitment["on_chain_ready"]))
    verify = sr.verify_score("DSYNC_002")
    logger.info("verify DSYNC_002: " + str(verify["verified"]) +
          " | score=" + str(verify["score"]))
    logger.info("")


def run_demo():
    logger.info("\nDroneSync MVP starting...\n")
    run_threat_defense()
    run_single_drone()
    run_swarm()
    run_ai_planner()
    run_city_map()
    run_tee()
    run_security()
    run_weather()
    run_energy()
    run_history()
    run_obstacles()
    run_reputation()
    run_firewall()
    run_last_will()
    run_memory()
    run_swarm_consensus()
    run_emergency()
    run_storage()
    run_scoreroot()
    run_sensor_bundle()
    demo_synapse()
    logger.info("DroneSync pipeline completed successfully")
    logger.info("PoPW artifact ready for on-chain submission")


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        logger.info("DroneSync interrupted by user")
    except Exception as e:
        logger.error("DroneSync fatal error: %s", e)
        raise
