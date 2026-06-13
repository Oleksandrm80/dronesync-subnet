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

def fuse_sensors(sensor_data: SensorData) -> dict:
    """
    Fuse LiDAR, camera and IMU into a single situational picture.
    Returns unified state: position confidence, obstacles, motion.
    """
    # LiDAR — average point cloud to get centroid
    lidar = sensor_data.lidar_points
    if lidar:
        cx = sum(p[0] for p in lidar) / len(lidar)
        cy = sum(p[1] for p in lidar) / len(lidar)
        cz = sum(p[2] for p in lidar) / len(lidar)
        lidar_confidence = min(1.0, len(lidar) / 50.0)
    else:
        cx = cy = cz = 0.0
        lidar_confidence = 0.0

    # Camera — count high-confidence detections
    detections = sensor_data.camera_detections
    obstacles = [d for d in detections if d.get("confidence", 0) >= 0.8]
    drone_detected = any(d.get("object") == "drone" for d in detections)

    # IMU — check stability
    imu = sensor_data.imu_data
    acc = imu.get("acceleration", [0, 0, -9.8])
    gyro = imu.get("gyro", [0, 0, 0])
    lateral_acc = (acc[0] ** 2 + acc[1] ** 2) ** 0.5
    rotation_rate = (gyro[0] ** 2 + gyro[1] ** 2 + gyro[2] ** 2) ** 0.5
    imu_stable = lateral_acc < 1.0 and rotation_rate < 0.1

    # Fused confidence
    camera_confidence = len(obstacles) / max(len(detections), 1)
    fused_confidence = round(
        lidar_confidence * 0.5 + camera_confidence * 0.3 +
        (0.2 if imu_stable else 0.0), 3
    )

    return {
        "position": {"lat": round(cx, 6), "lon": round(cy, 6), "alt": round(cz, 1)},
        "lidar_confidence": round(lidar_confidence, 3),
        "camera_confidence": round(camera_confidence, 3),
        "imu_stable": imu_stable,
        "fused_confidence": fused_confidence,
        "obstacles_detected": len(obstacles),
        "drone_proximity": drone_detected,
        "lateral_acceleration": round(lateral_acc, 3),
        "rotation_rate": round(rotation_rate, 4),
        "sensor_agreement": fused_confidence >= 0.6
    }
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
        all_conflicts: dict = {drone_id: [] for drone_id in drone_ids}
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
            fused = fuse_sensors(sensor)
            results[drone_id] = {
                "sensor_data": sensor,
                "sensor_fusion": fused,
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
        for step in range(len(my_positions)):
            for other_traj in other_trajectories:
                pos = my_positions[step]  # re-read after each update
                other_pos = other_traj[min(step, len(other_traj) - 1)]
                dist = self._haversine(
                    pos[0], pos[1], other_pos[0], other_pos[1]
                )
                if dist < self.SAFE_DISTANCE_M:
                    pos = my_positions[step]
                    alt_separation = abs(pos[2] - other_pos[2])
                    if alt_separation < 10:
                        new_alt = pos[2] + 10
                        my_positions[step] = [
                            pos[0], pos[1], new_alt, pos[3]
                        ]
                        maneuvers.append({
                            "step": step,
                            "action": "altitude_adjusted",
                            "new_alt": new_alt
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
            timestamp=int(pos[3]) if len(pos) > 3 else 0
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
