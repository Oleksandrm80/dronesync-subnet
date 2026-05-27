from miner.planner import DronePlanner, AIPlanner
from environment.sim import DroneEnvironment, SwarmEnvironment
from validator.scorer import DroneEvaluator


class FakeMission:
    def __init__(self, origin=(0, 0), destination=(3, 3)):
        self.origin = type("obj", (), {
            "lat": origin[0], "lon": origin[1], "alt": 50, "speed": 5
        })
        self.waypoints = [
            type("obj", (), {"lat": 1, "lon": 1, "alt": 50, "speed": 5}),
            type("obj", (), {"lat": 2, "lon": 2, "alt": 50, "speed": 5}),
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
        FakeMission(origin=(0, 0), destination=(3, 3)),
        FakeMission(origin=(0, 1), destination=(3, 4)),
        FakeMission(origin=(0, 2), destination=(3, 5)),
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


def run_demo():
    print("\nDroneSync MVP starting...\n")
    run_single_drone()
    run_swarm()
    run_ai_planner()
    print("DroneSync pipeline completed successfully")
    print("PoPW artifact ready for on-chain submission")


if __name__ == "__main__":
    run_demo()