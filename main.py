from dronesync.threat_defense import ThreatDefense
from dronesync.node import KonnexNode
from environment.obstacles import DynamicObstacleManager
from dronesync.mission_history import MissionHistory
from miner.planner import DronePlanner, AIPlanner
from miner.citymap import CityMap
from environment.sim import DroneEnvironment, SwarmEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import TEEAttestation, PoPWRecord
from dronesync.security import DroneSecuritySuite, CommandSigner
from miner.weather import WeatherService, WeatherImpactAnalyzer
from miner.energy import EnergyOptimizer, BatteryModel
from dronesync.reputation import DroneReputation
from dronesync.firewall import DroneFirewall
from dronesync.last_will import DroneLastWill
from dronesync.memory import DroneMemory
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.emergency import EmergencyOverride


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
    print("=" * 50)
    print("SINGLE DRONE MISSION")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    print("trajectory created")
    steps = trajectory.metadata.get("planner_steps", [])
    print("planner_steps: " + str(len(steps)))
    for s in steps:
        print("  step " + str(s["step"]) + ": " + s["action"] +
              " lat=" + str(s["lat"]) + " lon=" + str(s["lon"]))
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    print("environment simulation done")
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)
    print("score computed:", score)
    replay = validator.replay_validate(trajectory)
    print("replay_validation: " + replay["status"] +
          " | steps=" + str(replay.get("steps_count", 0)) +
          " | " + replay["reason"])
    print()


def run_swarm():
    print("=" * 50)
    print("SWARM MISSION - 3 DRONES")
    print("=" * 50)
    missions = [
        FakeMission(origin=(47.3769, 8.5417), destination=(47.3820, 8.5460)),
        FakeMission(origin=(47.3775, 8.5420), destination=(47.3825, 8.5465)),
        FakeMission(origin=(47.3780, 8.5425), destination=(47.3830, 8.5470)),
    ]
    planner = DronePlanner()
    trajectories = [planner.plan_trajectory(m) for m in missions]
    print(str(len(trajectories)) + " trajectories planned")
    swarm = SwarmEnvironment(n_drones=3)
    results = swarm.run_swarm(trajectories)
    for drone_id, result in results.items():
        status = result["status"]
        predicted = result["conflicts_predicted"]
        maneuvers = len(result["avoidance_maneuvers"])
        print(drone_id + ": status=" + status +
              ", conflicts_predicted=" + str(predicted) +
              ", avoidance_maneuvers=" + str(maneuvers))
    print()


def run_ai_planner():
    print("=" * 50)
    print("AI PLANNER - LEARNING MODE")
    print("=" * 50)
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
        print("mission " + str(i+1) + ": score=" + str(score) +
              " | safety=" + str(round(weights["safety"], 2)) +
              " efficiency=" + str(round(weights["efficiency"], 2)))
    print("AI planner trained on 3 missions")
    print()


def run_city_map():
    print("=" * 50)
    print("CITY MAP - ZURICH URBAN AIRSPACE")
    print("=" * 50)
    city = CityMap(city="zurich")
    stats = city.get_city_stats()
    print("city: " + stats["city"])
    print("no-fly zones: " + str(stats["no_fly_zones"]))
    print("zone types: " + str(stats["zone_types"]))
    test_points = [
        (47.3769, 8.5417, "city center"),
        (47.4647, 8.5492, "near airport"),
        (47.3744, 8.5373, "near hospital"),
    ]
    print()
    for lat, lon, name in test_points:
        no_fly, reason = city.is_no_fly(lat, lon)
        safe_alt = city.safe_altitude(lat, lon)
        status = "NO-FLY: " + str(reason) if no_fly else "CLEAR"
        print(name + ": " + status + " | safe_alt=" + str(safe_alt) + "m")
    print()


def run_tee():
    print("=" * 50)
    print("TEE ATTESTATION - PoPW RECORD")
    print("=" * 50)
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
    print("mission_id: " + record["mission_id"])
    print("score: " + str(record["score"]))
    print("trajectory_hash: " + record["trajectory_hash"][:16] + "...")
    print("attestation: " + record["attestation"]["attestation_id"])
    print("tee_status: " + record["attestation"]["status"])
    print("on_chain_ready: " + str(record["on_chain_ready"]))
    chain_str = popw.format_for_chain(record)
    print("on-chain string: " + chain_str)
    print()


def run_security():
    print("=" * 50)
    print("SECURITY SUITE - THREAT DETECTION")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)

    security = DroneSecuritySuite()
    result = security.full_security_check(trajectory, score)

    print("overall_status: " + result["overall_status"])
    print("gps_spoofing: " + result["gps_spoofing"])
    print("hijacking: " + result["hijacking"])
    print("threat_level: " + result["threat_level"])
    print("mission_cleared: " + str(result["mission_cleared"]))

    signer = CommandSigner()
    cmd = {"action": "fly", "destination": "47.3800,8.5450", "priority": 1}
    signed = signer.sign_command(cmd)
    verified = signer.verify_command(signed)
    print("command_signed: True")
    print("command_verified: " + str(verified))
    print()

def run_weather():
    print("=" * 50)
    print("WEATHER MODULE - ZURICH CONDITIONS")
    print("=" * 50)
    weather_service = WeatherService(city="zurich")
    weather = weather_service.get_current()
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    analyzer = WeatherImpactAnalyzer()
    impact = analyzer.analyze(weather, trajectory.positions)
    print("flyable: " + str(impact["flyable"]))
    print("severity: " + impact["severity"])
    print("wind: " + str(impact["wind_speed_ms"]) + " m/s")
    print("visibility: " + str(impact["visibility_m"]) + "m")
    print("precipitation: " + impact["precipitation"])
    print("speed_factor: " + str(impact["speed_factor"]))
    print("energy_factor: " + str(impact["energy_factor"]))
    print("recommendation: " + impact["recommendation"])
    print()
def run_energy():
    print("=" * 50)
    print("ENERGY OPTIMIZER")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    battery = BatteryModel(capacity_wh=100.0, payload_kg=0.5)
    optimizer = EnergyOptimizer(battery=battery)
    result = optimizer.analyze_trajectory(trajectory.positions, wind_ms=3.0)
    print("total_distance_km: " + str(result["total_distance_km"]))
    print("battery_used_pct: " + str(result["battery_used_pct"]) + "%")
    print("battery_remaining_pct: " + str(result["battery_remaining_pct"]) + "%")
    print("efficiency_rating: " + result["efficiency_rating"])
    print("mission_feasible: " + str(result["mission_feasible"]))
    print("recommendation: " + result["recommendation"])
    optimal = optimizer.optimal_speed(wind_ms=3.0)
    print("optimal_speed_ms: " + str(optimal))
    print()
def run_history():
    print("=" * 50)
    print("MISSION HISTORY & STATISTICS")
    print("=" * 50)
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
    print("total_missions: " + str(stats["total_missions"]))
    print("avg_score: " + str(stats["avg_score"]))
    print("max_score: " + str(stats["max_score"]))
    print("success_rate: " + str(stats["success_rate_pct"]) + "%")
    print()
    print("last 3 missions:")
    for m in history.last(3):
        print("  " + m["mission_id"] + " | score=" + str(m["score"]) +
              " | battery=" + str(m["battery_used_pct"]) + "%")
    print()
def run_obstacles():
    print("=" * 50)
    print("DYNAMIC OBSTACLES - URBAN AIRSPACE")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    manager = DynamicObstacleManager()
    result = manager.check_trajectory(trajectory.positions)
    print("obstacles_tracked: " + str(result["obstacles_tracked"]))
    print("conflicts_found: " + str(result["conflicts_found"]))
    print("trajectory_safe: " + str(result["trajectory_safe"]))
    print("recommendation: " + result["recommendation"])
    if result["conflicts"]:
        for c in result["conflicts"]:
            print("  conflict: " + c["obstacle_id"] +
                  " type=" + c["type"] +
                  " dist=" + str(c["distance_m"]) + "m")
def run_threat_defense():
    print("=" * 50)
    print("THREAT DEFENSE - REAL ATTACK VECTORS")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    defense = ThreatDefense()
    result = defense.full_threat_assessment(
        trajectory.positions,
        signal_strength=0.92
    )
    print("overall_threat_level: " + result["overall_threat_level"])
    print("gps_status: " + result["gps_status"])
    print("jamming_status: " + result["jamming_status"])
    print("swarm_integrity: " + result["swarm_integrity"])
    print("mission_safe: " + str(result["mission_safe"]))
    print("total_threats: " + str(result["total_threats"]))
    node = KonnexNode(
        wallet_address="0x5a4E...51f2",
        network="testnet"
    )
    node.connect()
    status = node.get_status()
    print()
    print("node_connected: " + str(status["connected"]))
    print("network: " + status["network"])
    print("session_id: " + str(status["session_id"]))
    print()
    print()
def run_reputation():
    print("=" * 50)
    print("DRONE REPUTATION SCORE")
    print("=" * 50)
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
    print("drone_id: " + status["drone_id"])
    print("reputation_score: " + str(status["reputation_score"]))
    print("tier: " + status["tier"])
    print("total_missions: " + str(status["total_missions"]))
    print("on_chain_ready: " + str(status["on_chain_ready"]))
    print()


def run_firewall():
    print("=" * 50)
    print("DRONE FIREWALL - COMMAND FILTER")
    print("=" * 50)
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
        print("action=" + cmd["action"] + " → " + result["status"] +
              (" | reason=" + result["reason"] if result["status"] == "BLOCKED" else ""))
    report = fw.get_report()
    print("total_allowed: " + str(report["total_allowed"]))
    print("total_blocked: " + str(report["total_blocked"]))
    print("on_chain_ready: " + str(report["on_chain_ready"]))
    print()


def run_last_will():
    print("=" * 50)
    print("DRONE LAST WILL - EMERGENCY PoPW")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    last_will = DroneLastWill(drone_id="DRONE_001")
    record = last_will.simulate_crash(trajectory.positions, mission.mission_id)
    print("type: " + record["type"])
    print("drone_id: " + record["drone_id"])
    print("failure_cause: " + record["failure_cause"])
    print("battery_pct: " + str(record["battery_pct"]) + "%")
    print("last_position: lat=" + str(record["last_position"]["lat"]) +
          " lon=" + str(record["last_position"]["lon"]))
    print("will_hash: " + record["will_hash"][:16] + "...")
    print("insurance_claim_ready: " + str(record["insurance_claim_ready"]))
    print("on_chain_ready: " + str(record["on_chain_ready"]))
    print()


def run_memory():
    print("=" * 50)
    print("DRONE MEMORY - FLIGHT EXPERIENCE")
    print("=" * 50)
    mission = FakeMission()
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    mem = DroneMemory(drone_id="DRONE_001")
    for i in range(5):
        mem.record_flight(trajectory.positions, duration_s=120.0, wind_ms=3.0)
    record = mem.get_memory_record()
    print("drone_id: " + record["drone_id"])
    print("missions_completed: " + str(record["missions_completed"]))
    print("total_flight_hours: " + str(record["total_flight_hours"]))
    print("asset_value: " + record["asset_value"])
    print("on_chain_ready: " + str(record["on_chain_ready"]))
    print()


def run_swarm_consensus():
    print("=" * 50)
    print("SWARM CONSENSUS - DECENTRALIZED VOTING")
    print("=" * 50)
    drones = ["drone_0", "drone_1", "drone_2", "drone_3", "drone_4"]
    consensus = SwarmConsensus(drone_ids=drones)
    votes = [(d, True) for d in drones[:4]] + [("drone_4", False)]
    result = consensus.vote_on_route("DSYNC_001", votes)
    print("mission_id: DSYNC_001")
    print("approvals: " + str(result["approvals"]) + "/" + str(result["total_voters"]))
    print("approval_rate: " + str(result["approval_rate"]))
    print("route_status: " + result["status"])
    bl_votes = [(d, True) for d in ["drone_0", "drone_1", "drone_2"]] + [("drone_3", False)]
    bl_result = consensus.vote_blacklist("drone_4", bl_votes)
    print("blacklist_vote: drone_4 -> " + bl_result["status"])
    status = consensus.get_swarm_status()
    print("active_drones: " + str(status["active_drones"]) + "/" + str(status["total_drones"]))
    print("on_chain_ready: " + str(status["on_chain_ready"]))
    print()


def run_emergency():
    print("=" * 50)
    print("EMERGENCY OVERRIDE PROTOCOL")
    print("=" * 50)
    override = EmergencyOverride()
    emergency = override.broadcast_emergency(
        emergency_type="FIRE",
        location={"lat": 47.3780, "lon": 8.5430},
        authority_id="ZURICH_FIRE_DEPT_001"
    )
    print("emergency_id: " + emergency["emergency_id"])
    print("type: " + emergency["type"])
    print("action: " + emergency["action"])
    print("radius_m: " + str(emergency["radius_m"]))
    drone_pos = [47.3782, 8.5432, 50.0]
    check = override.check_drone_override(drone_pos, emergency)
    print("drone_override: " + str(check["override"]))
    if check["override"]:
        print("redirect_action: " + check["action"])
        print("distance_to_emergency_m: " + str(check["distance_to_emergency_m"]))
    status = override.get_status()
    print("redirected_drones: " + str(status["redirected_drones"]))
    print("on_chain_ready: " + str(status["on_chain_ready"]))
    print()


def run_demo():
    print("\nDroneSync MVP starting...\n")
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
    print("DroneSync pipeline completed successfully")
    print("PoPW artifact ready for on-chain submission")


if __name__ == "__main__":
    run_demo()