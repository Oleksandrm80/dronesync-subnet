"""
DroneSync Environment - Simulation Layer v2
Supports single drone and multi-drone swarm coordination
"""
import random
import math
from dronesync.protocol import Trajectory, SensorData


class DroneEnvironment:
    def run(self, trajectory: Trajectory) -> SensorData:
        last = trajectory.positions[-1]
        lidar = [
            [
                last[0] + random.uniform(-0.001, 0.001),
                last[1] + random.uniform(-0.001, 0.001),
                last[2]
            ]
            for _ in range(50)
        ]
        return SensorData(
            lidar_points=lidar,
            camera_detections=[
                {"object": "building", "confidence": 0.9},
                {"object": "tree", "confidence": 0.8}
            ],
            imu_data={
                "acceleration": [0.1, 0.2, -9.8],
                "gyro": [0.01, -0.02, 0.0]
            },
            timestamp=trajectory.timestamps[-1]
        )


class SwarmEnvironment:
    """
    Multi-drone swarm simulation.
    Coordinates N drones simultaneously with collision avoidance.
    """

    SAFE_DISTANCE = 0.0005  # ~50 meters in lat/lon

    def __init__(self, n_drones: int = 3):
        self.n_drones = n_drones
        self.drone_positions = {}

    def run_swarm(self, trajectories: list) -> dict:
        """
        Run simulation for multiple drones simultaneously.
        Returns sensor data and collision report for each drone.
        """
        results = {}
        all_positions = []

        for i, traj in enumerate(trajectories):
            drone_id = f"drone_{i}"
            last = traj.positions[-1]
            self.drone_positions[drone_id] = last
            all_positions.append((drone_id, last))

        for drone_id, pos in all_positions:
            collisions = self._check_collisions(drone_id, pos, all_positions)
            sensor = self._simulate_sensor(pos, collisions)
            results[drone_id] = {
                "sensor_data": sensor,
                "collision_risk": collisions,
                "status": "WARNING" if collisions else "CLEAR"
            }

        return results

    def _check_collisions(self, drone_id: str, pos: list,
                           all_positions: list) -> list:
        """Check if drone is too close to other drones."""
        risks = []
        for other_id, other_pos in all_positions:
            if other_id == drone_id:
                continue
            dist = math.sqrt(
                (pos[0] - other_pos[0]) ** 2 +
                (pos[1] - other_pos[1]) ** 2
            )
            if dist < self.SAFE_DISTANCE:
                risks.append({
                    "other_drone": other_id,
                    "distance": round(dist * 111000, 1),
                    "severity": "HIGH" if dist < self.SAFE_DISTANCE / 2 else "LOW"
                })
        return risks

    def _simulate_sensor(self, pos: list, collisions: list) -> SensorData:
        """Generate sensor data with collision awareness."""
        detections = [
            {"object": "building", "confidence": 0.9},
            {"object": "tree", "confidence": 0.8}
        ]
        if collisions:
            detections.append({
                "object": "drone",
                "confidence": 0.99,
                "action": "AVOID"
            })

        lidar = [
            [
                pos[0] + random.uniform(-0.001, 0.001),
                pos[1] + random.uniform(-0.001, 0.001),
                pos[2]
            ]
            for _ in range(100)
        ]

        return SensorData(
            lidar_points=lidar,
            camera_detections=detections,
            imu_data={
                "acceleration": [
                    random.uniform(-0.2, 0.2),
                    random.uniform(-0.2, 0.2),
                    -9.8
                ],
                "gyro": [
                    random.uniform(-0.05, 0.05),
                    random.uniform(-0.05, 0.05),
                    random.uniform(-0.02, 0.02)
                ]
            },
            timestamp=pos[2] if len(pos) > 2 else 0.0
        )