"""
DroneSync Environment - Simulation Layer
"""

import random
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