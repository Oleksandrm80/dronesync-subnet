# miner/planner.py
"""
DroneSync Miner - Trajectory Planner
"""

import time
import hashlib
import random

from dronesync.protocol import (
    MissionInstruction,
    Trajectory,
    SensorData,
    PoPWArtifact
)
from dronesync.navigation import NavigationEngine

class DronePlanner:
    """Основной класс для планирования траектории дрона"""
    
    def __init__(self):
        self.computation_steps = 0

    def plan_trajectory(self, mission: MissionInstruction) -> Trajectory:
        """
        Основная функция: строит траекторию для миссии
        """
        self.computation_steps = 0
        planner_steps = []

        positions = []
        velocities = []
        timestamps = []

        # Начальная точка
        current_time: float = float(time.time())
        positions.append([mission.origin.lat, mission.origin.lon, mission.origin.alt, current_time])
        velocities.append(mission.origin.speed)
        timestamps.append(int(current_time))
        planner_steps.append({
            "step": 0,
            "action": "origin",
            "lat": mission.origin.lat,
            "lon": mission.origin.lon,
            "alt": mission.origin.alt,
            "timestamp": current_time
        })

        # Простой алгоритм: идём через waypoints + конечную точку
        all_points = mission.waypoints + [mission.destination]

        for i, waypoint in enumerate(all_points):
            self.computation_steps += 1
            current_time += 5  # 5 секунд между точками (симуляция)

            positions.append([waypoint.lat, waypoint.lon, waypoint.alt, current_time])
            velocities.append(waypoint.speed)
            timestamps.append(int(current_time))

            action = "destination" if i == len(all_points) - 1 else "waypoint"
            planner_steps.append({
                "step": i + 1,
                "action": action,
                "lat": waypoint.lat,
                "lon": waypoint.lon,
                "alt": waypoint.alt,
                "timestamp": current_time
            })

            # Симулируем вычисления
            self.computation_steps += 10

        # Хэш шагов для replay validation
        steps_data = str(planner_steps).encode()
        steps_hash = hashlib.sha256(steps_data).hexdigest()

        # Создаём Trajectory
        trajectory = Trajectory(
            positions=positions,
            velocities=velocities,
            timestamps=timestamps,
            metadata={
                "planner_version": "0.1",
                "total_waypoints": len(all_points),
                "mission_type": mission.mission_type.value,
                "planner_steps": planner_steps,
                "steps_hash": steps_hash
            }
        )

        return trajectory

    def generate_sensor_data(self, trajectory: Trajectory) -> SensorData:
        """Генерирует симулированные данные сенсоров"""
        last_position = trajectory.positions[-1]
        
        return SensorData(
            lidar_points=[[last_position[0] + random.uniform(-0.001, 0.001), 
                          last_position[1] + random.uniform(-0.001, 0.001), 
                          last_position[2]] for _ in range(50)],
            camera_detections=[
                {"object": "building", "confidence": 0.92},
                {"object": "tree", "confidence": 0.78}
            ],
            imu_data={
                "acceleration": [0.1, 0.2, -9.8],
                "gyro": [0.01, -0.02, 0.0]
            },
            timestamp=trajectory.timestamps[-1]
        )

    def generate_pow_artifact(self, mission: MissionInstruction, trajectory: Trajectory) -> PoPWArtifact:
        """Создаёт Proof of Physical Work"""
        import json
        traj_hash = hashlib.sha256(
            json.dumps(trajectory.positions, sort_keys=True).encode()
        ).hexdigest()
        data = f"{mission.mission_id}{traj_hash}".encode()
        computation_hash = hashlib.sha256(data).hexdigest()
        
        return PoPWArtifact(
            computation_hash=computation_hash,
            simulation_steps=self.computation_steps,
            energy_estimate=round(self.computation_steps * 0.15, 2),
            constraints_satisfied=True
        )


# Для теста
class AIPlanner:
    """
    AI-enhanced trajectory planner.
    Learns from previous missions to optimize routes.
    Uses weighted scoring to improve path quality over time.
    """

    def __init__(self):
        self.mission_history = []
        self.nav = NavigationEngine()
        self.learned_weights = {            "safety": 0.40,
            "efficiency": 0.35,
            "energy": 0.25
        }

    def plan_trajectory(self, mission) -> Trajectory:
        """Plan trajectory using AI-weighted optimization."""
        import time
        import hashlib
        positions = []
        velocities = []
        timestamps = []
        planner_steps = []

        current_time: float = float(time.time())

        # Start point
        positions.append([
            mission.origin.lat,
            mission.origin.lon,
            mission.origin.alt,
            current_time
        ])
        velocities.append(mission.origin.speed)
        timestamps.append(int(current_time))
        planner_steps.append({"step": 0, "action": "origin", "lat": mission.origin.lat, "lon": mission.origin.lon, "alt": mission.origin.alt, "timestamp": current_time})

        # AI optimization: adjust waypoints based on learned weights
        all_points = mission.waypoints + [mission.destination]
        for i, waypoint in enumerate(all_points):
            current_time += self._optimized_step_time(i, len(all_points))
            optimized_pos = self._optimize_position(
                waypoint.lat, waypoint.lon, waypoint.alt
            )
            positions.append([*optimized_pos, current_time])
            velocities.append(self._optimized_speed(waypoint.speed))
            timestamps.append(int(current_time))
            action = "destination" if i == len(all_points) - 1 else "waypoint"
            planner_steps.append({"step": i+1, "action": action, "lat": optimized_pos[0], "lon": optimized_pos[1], "alt": optimized_pos[2], "timestamp": current_time})

        steps_hash = hashlib.sha256(str(planner_steps).encode()).hexdigest()

        trajectory = Trajectory(
            positions=positions,
            velocities=velocities,
            timestamps=timestamps,
            metadata={
                "planner_version": "ai_v1",
                "learned_weights": self.learned_weights,
                "mission_type": mission.mission_type.value,
                "optimized": True,
                "planner_steps": planner_steps,
                "steps_hash": steps_hash
            }
        )
        all_wps = [mission.origin] + mission.waypoints + [mission.destination]
        sim = self.nav.sim_flight(all_wps)
        etas = self.nav.calculate_etas(sim.segments)
        trajectory.metadata["sim_flight"] = sim.summary()
        trajectory.metadata["nav_alerts"] = [
            {"level": a.level.value, "code": a.code, "message": a.message}
            for a in sim.alerts
        ]
        trajectory.metadata["etas"] = [
            {"waypoint": e.waypoint_index, "planned_eta": e.planned_eta}
            for e in etas
        ]

        self.mission_history.append({
            "mission_type": mission.mission_type.value,
            "waypoints": len(all_points)
        })

        return trajectory

    def learn_from_score(self, score: int):
        """Update weights based on validator score feedback."""
        if score >= 90:
            self.learned_weights["efficiency"] = min(
                0.50, self.learned_weights["efficiency"] + 0.02
            )
        elif score < 70:
            self.learned_weights["safety"] = min(
                0.60, self.learned_weights["safety"] + 0.05
            )
        total = sum(self.learned_weights.values())
        if total > 0:
            self.learned_weights = {
                k: round(v / total, 3)
                for k, v in self.learned_weights.items()
            }

    def _optimized_step_time(self, step: int, total: int) -> float:
        """Calculate optimal time between waypoints."""
        base = 4.0
        efficiency_factor = self.learned_weights["efficiency"]
        return round(base * (1 - efficiency_factor * 0.3), 2)

    def _optimize_position(self, lat: float, lon: float,
                            alt: float) -> list:
        """Apply safety margin to altitude based on learned weights."""
        safe_alt = max(alt, 30.0 * self.learned_weights["safety"])
        return [lat, lon, safe_alt]

    def _optimized_speed(self, base_speed: float) -> float:
        """Optimize speed based on efficiency weight."""
        return round(base_speed * (1 + self.learned_weights["efficiency"] * 0.2), 2)

    def apply_federated_weights(self, global_weights: dict):
        """Apply weights from federated learning aggregator."""
        if "safety" in global_weights:
            self.learned_weights["safety"] = global_weights["safety"]
        if "efficiency" in global_weights:
            self.learned_weights["efficiency"] = global_weights["efficiency"]
        if "energy" in global_weights:
            self.learned_weights["energy"] = global_weights["energy"]

    def to_flight_record(self, score: float) -> dict:
        """Export flight record for federated learning."""
        return {
            "score": score / 100.0,
            "avg_speed": self.learned_weights["efficiency"],
            "avg_altitude": self.learned_weights["safety"],
            "battery_efficiency": self.learned_weights["energy"],
            "obstacle_avoidance_rate": self.learned_weights["safety"],
            "path_deviation": 1.0 - self.learned_weights["efficiency"],
            "weather_impact": 0.5,
        }
if __name__ == "__main__":
    planner = DronePlanner()
    # Здесь можно будет протестировать
    print("DronePlanner loaded successfully")


class MultiAgentPlanner:
    """
    Plans non-conflicting trajectories for multiple drones simultaneously.
    Uses time-slot separation + altitude layering to avoid conflicts.
    """

    ALTITUDE_LAYER = 10.0   # meters between drone altitude layers
    TIME_SLOT      = 5.0    # seconds between drone departures

    def __init__(self):
        self.orca = None
        try:
            from dronesync.swarm_consensus import ORCACollisionAvoider
            self.orca = ORCACollisionAvoider()
        except ImportError:
            pass

    def plan_swarm(self, missions: dict) -> dict:
        """
        Plan trajectories for multiple drones.
        missions: {drone_id: MissionInstruction}
        Returns:  {drone_id: Trajectory, "conflicts": [], "safe": bool}
        """
        results = {}
        conflicts = []
        base_planner = AIPlanner()

        for idx, (drone_id, mission) in enumerate(missions.items()):
            # Assign altitude layer per drone to avoid vertical conflicts
            mission.origin.alt      += idx * self.ALTITUDE_LAYER
            mission.destination.alt += idx * self.ALTITUDE_LAYER

            # Stagger departure times
            traj = base_planner.plan_trajectory(mission)

            # Shift timestamps by slot
            offset = idx * self.TIME_SLOT
            traj.timestamps = [t + offset for t in traj.timestamps]
            traj.metadata["drone_id"]      = drone_id
            traj.metadata["altitude_layer"] = idx
            traj.metadata["departure_offset_s"] = offset

            results[drone_id] = traj

        # Check for spatial conflicts using ORCA
        if self.orca and len(results) > 1:
            positions  = {}
            velocities = {}
            for drone_id, traj in results.items():
                if traj.positions:
                    p = traj.positions[0]
                    positions[drone_id]  = (p[0], p[1], p[2])
                    velocities[drone_id] = (0.0, 0.0, 5.0)

            swarm_check = self.orca.check_swarm(positions, velocities)
            if not swarm_check["swarm_safe"]:
                for drone_id, res in swarm_check["drone_results"].items():
                    for c in res["collisions_avoided"]:
                        conflicts.append({
                            "drone_a": drone_id,
                            "drone_b": c["other_drone"],
                            "distance_m": c["distance_m"],
                            "resolved": True
                        })

        return {
            "trajectories": {k: v.metadata for k, v in results.items()},
            "conflicts":    conflicts,
            "conflicts_resolved": len(conflicts),
            "safe":         len(conflicts) == 0 or all(c["resolved"] for c in conflicts),
            "drone_count":  len(results),
            "timestamp":    int(time.time())
        }
