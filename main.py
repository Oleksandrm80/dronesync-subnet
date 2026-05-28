from miner.planner import DronePlanner, AIPlanner
from miner.citymap import CityMap
from environment.sim import DroneEnvironment, SwarmEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import TEEAttestation, PoPWRecord
from dronesync.security import DroneSecuritySuite, CommandSigner
from miner.weather import WeatherService, WeatherImpactAnalyzer


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
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    print("environment simulation done")
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)
    print("score computed:", score)
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
        risks = len(result["collision_risk"])
        print(drone_id + ": status=" + status + ", collision_risks=" + str(risks))
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
def run_demo():
    print("\nDroneSync MVP starting...\n")
    run_single_drone()
    run_swarm()
    run_ai_planner()
    run_city_map()
    run_tee()
    run_security()
    run_weather()
    print("DroneSync pipeline completed successfully")
    print("PoPW artifact ready for on-chain submission")


if __name__ == "__main__":
    run_demo()