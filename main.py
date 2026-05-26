from miner.planner import DronePlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator


def run_demo():
    print("🚀 DroneSync MVP starting...\n")

    # fake mission (если у тебя уже есть MissionInstruction — скажешь, адаптируем)
    class FakeMission:
        def __init__(self):
            self.origin = type("obj", (), {"lat": 0, "lon": 0, "alt": 0, "speed": 1})
            self.waypoints = [
                type("obj", (), {"lat": 1, "lon": 1, "alt": 1, "speed": 1}),
                type("obj", (), {"lat": 2, "lon": 2, "alt": 2, "speed": 1}),
            ]
            self.destination = type("obj", (), {"lat": 3, "lon": 3, "alt": 3, "speed": 1})
            self.mission_type = type("obj", (), {"value": "test"})

    mission = FakeMission()

    # 1. MINER
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    print("✅ trajectory created")

    # 2. ENVIRONMENT
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    print("✅ environment simulation done")

    # 3. VALIDATOR
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)
    print("✅ score computed:", score)

    print("\n🎯 DroneSync run completed")


if __name__ == "__main__":
    run_demo()