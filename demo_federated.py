"""
demo_federated.py

Demo: Federated Learning across drone swarm → AIPlanner improvement

Run:
    python3 demo_federated.py
"""

import sys
sys.path.insert(0, ".")

from dronesync.federated_learning import FederatedSwarm
from miner.planner import AIPlanner


def main():
    print(f"\n{'='*60}")
    print("DroneSync — Federated Learning + AIPlanner")
    print("Drones learn together WITHOUT sharing flight data")
    print(f"{'='*60}")

    drone_ids = ["drone-kyiv", "drone-berlin", "drone-newyork"]
    swarm = FederatedSwarm(drone_ids=drone_ids, min_drones=2)

    planners = {did: AIPlanner() for did in drone_ids}

    print(f"\n[1] Initial AIPlanner weights (before federation):")
    for did, planner in planners.items():
        w = planner.learned_weights
        print(f"    {did}: safety={w['safety']:.3f} efficiency={w['efficiency']:.3f} energy={w['energy']:.3f}")

    print(f"\n[2] Running 3 federation rounds...")

    flight_scenarios = [
        {"drone-kyiv":    [{"score": 0.92, "avg_speed": 0.8, "avg_altitude": 0.7,
                            "battery_efficiency": 0.9, "obstacle_avoidance_rate": 0.95,
                            "path_deviation": 0.1, "weather_impact": 0.3}] * 5,
         "drone-berlin":  [{"score": 0.75, "avg_speed": 0.6, "avg_altitude": 0.8,
                            "battery_efficiency": 0.7, "obstacle_avoidance_rate": 0.85,
                            "path_deviation": 0.2, "weather_impact": 0.5}] * 5,
         "drone-newyork": [{"score": 0.85, "avg_speed": 0.75, "avg_altitude": 0.65,
                            "battery_efficiency": 0.8, "obstacle_avoidance_rate": 0.90,
                            "path_deviation": 0.15, "weather_impact": 0.4}] * 5},
        {"drone-kyiv":    [{"score": 0.88, "avg_speed": 0.82, "avg_altitude": 0.72,
                            "battery_efficiency": 0.88, "obstacle_avoidance_rate": 0.93,
                            "path_deviation": 0.09, "weather_impact": 0.25}] * 8,
         "drone-berlin":  [{"score": 0.80, "avg_speed": 0.65, "avg_altitude": 0.78,
                            "battery_efficiency": 0.75, "obstacle_avoidance_rate": 0.88,
                            "path_deviation": 0.18, "weather_impact": 0.45}] * 6,
         "drone-newyork": [{"score": 0.90, "avg_speed": 0.78, "avg_altitude": 0.68,
                            "battery_efficiency": 0.85, "obstacle_avoidance_rate": 0.92,
                            "path_deviation": 0.12, "weather_impact": 0.35}] * 7},
        {"drone-kyiv":    [{"score": 0.95, "avg_speed": 0.85, "avg_altitude": 0.75,
                            "battery_efficiency": 0.92, "obstacle_avoidance_rate": 0.97,
                            "path_deviation": 0.07, "weather_impact": 0.2}] * 10,
         "drone-berlin":  [{"score": 0.83, "avg_speed": 0.68, "avg_altitude": 0.80,
                            "battery_efficiency": 0.78, "obstacle_avoidance_rate": 0.90,
                            "path_deviation": 0.15, "weather_impact": 0.4}] * 8,
         "drone-newyork": [{"score": 0.93, "avg_speed": 0.80, "avg_altitude": 0.70,
                            "battery_efficiency": 0.88, "obstacle_avoidance_rate": 0.94,
                            "path_deviation": 0.10, "weather_impact": 0.3}] * 9},
    ]

    for round_num, flight_data in enumerate(flight_scenarios, 1):
        global_weights = swarm.run_round(flight_data)

        for did, planner in planners.items():
            planner.apply_federated_weights(global_weights)

        print(f"\n    Round {round_num} — Global weights after aggregation:")
        for k, v in global_weights.items():
            print(f"      {k}: {v:.4f}")
    print(f"\n[3] Final AIPlanner weights (after federation):")
    for did, planner in planners.items():
        w = planner.learned_weights
        print(f"    {did}: safety={w['safety']:.3f} efficiency={w['efficiency']:.3f} energy={w['energy']:.3f}")

    print(f"\n[4] Federation summary:")
    s = swarm.aggregator.summary()
    print(f"    Rounds completed: {s['federation_rounds']}")
    print(f"    History entries:  {s['history_rounds']}")

    print(f"\n[5] Prediction test — drone-kyiv estimates mission score:")
    features = {"avg_speed": 0.82, "avg_altitude": 0.72, "battery_efficiency": 0.90}
    score = swarm.predict("drone-kyiv", features)
    print(f"    Predicted score: {score:.3f} ({score*100:.1f}/100)")

    print(f"\n{'='*60}")
    print("✅ Federated Learning complete — all drones improved together")
    print("   Raw flight data never left individual drones")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
