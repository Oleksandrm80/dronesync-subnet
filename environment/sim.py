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
    Multi-drone swarm simulation with predictive collision avoidance.

    Uses time-stepped trajectory comparison: at each flight step, checks
    pairwise distance between all drones. Flags conflicts before they happen
    and generates avoidance maneuvers (altitude separation).
    """

    SAFE_DISTANCE_M = 50.0   # minimum separation in meters
    STEP_TIME_S = 5.0        # seconds per trajectory step

    def __init__(self, n_drones: int = 3):
        self.n_drones = n_drones

    def run_swarm(self, trajectories: list) -> dict:
        """
        Run predictive swarm simulation across full trajectories.
        Checks all time steps, not just final positions.
        Returns per-drone results with collision predictions and avoidance actions.
        """
        drone_ids = [f"drone_{i}" for i in range(len(trajectories))]

        # Align all trajectories to the same number of steps
        max_steps = max(len(t.positions) for t in trajectories)
        padded = []
        for traj in trajectories:
            positions = list(traj.positions)
            while len(positions) < max_steps:
                positions.append(positions[-1])  # hover at final position
            padded.append(positions)

        # Predict collisions across all time steps
        all_conflicts = {drone_id: [] for drone_id in drone_ids}
        for step in range(max_steps):
            step_positions = [(drone_ids[i], padded[i][step])
                              for i in range(len(drone_ids))]
            for i, (drone_id, pos) in enumerate(step_positions):
                for j, (other_id, other_pos) in enumerate(step_positions):
                    if i >= j:
                        continue
                    dist = self._haversine(
                        pos[0], pos[1], other_pos[0], other_pos[1]
                    )
                    if dist < self.SAFE_DISTANCE_M:
                        conflict = {
                            "step": step,
                            "time_s": step * self.STEP_TIME_S,
                            "other_drone": other_id,
                            "distance_m": round(dist, 1),
                            "severity": "CRITICAL" if dist < 20 else "HIGH",
                            "avoidance": self._avoidance_action(pos, other_pos, dist)
                        }
                        all_conflicts[drone_id].append(conflict)

        results = {}
        for i, drone_id in enumerate(drone_ids):
            final_pos = padded[i][-1]
            conflicts = all_conflicts[drone_id]
            avoidance_applied = self._apply_avoidance(
                padded[i], [padded[j] for j in range(len(drone_ids)) if j != i]
            )
            sensor = self._simulate_sensor(final_pos, conflicts)
            results[drone_id] = {
                "sensor_data": sensor,
                "collision_risk": conflicts,
                "avoidance_maneuvers": avoidance_applied,
                "status": "WARNING" if conflicts else "CLEAR",
                "trajectory_steps": len(padded[i]),
                "conflicts_predicted": len(conflicts)
            }

        return results

    def _avoidance_action(self, pos: list, other_pos: list,
                          dist: float) -> dict:
        """Generate avoidance maneuver based on relative position."""
        alt_diff = pos[2] - other_pos[2]
        if abs(alt_diff) < 10:
            # Same altitude — one climbs, one descends
            action = "CLIMB_10M" if pos[0] < other_pos[0] else "DESCEND_10M"
        else:
            action = "MAINTAIN_SEPARATION"
        return {
            "action": action,
            "current_separation_m": round(dist, 1),
            "target_separation_m": self.SAFE_DISTANCE_M
        }

    def _apply_avoidance(self, my_positions: list,
                          other_trajectories: list) -> list:
        """
        Apply altitude separation to avoid predicted conflicts.
        Returns list of maneuvers applied.
        """
        maneuvers = []
        for step, pos in enumerate(my_positions):
            for other_traj in other_trajectories:
                other_pos = other_traj[min(step, len(other_traj) - 1)]
                dist = self._haversine(
                    pos[0], pos[1], other_pos[0], other_pos[1]
                )
                if dist < self.SAFE_DISTANCE_M:
                    alt_separation = abs(pos[2] - other_pos[2])
                    if alt_separation < 10:
                        # Apply altitude adjustment in-place
                        my_positions[step] = [
                            pos[0], pos[1], pos[2] + 10, pos[3]
                        ]
                        maneuvers.append({
                            "step": step,
                            "action": "altitude_adjusted",
                            "new_alt": pos[2] + 10
                        })
        return maneuvers

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
            timestamp=pos[3] if len(pos) > 3 else 0.0
        )

    def _haversine(self, lat1: float, lon1: float,
                   lat2: float, lon2: float) -> float:
        """Distance between two GPS points in meters."""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
