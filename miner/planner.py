# miner/planner.py
"""
DroneSync Miner - Trajectory Planner
"""

from typing import List, Dict
import time
import hashlib
import random

from dronesync.protocol import (
    MissionInstruction, 
    Trajectory, 
    SensorData, 
    PoPWArtifact,
    Waypoint
)


class DronePlanner:
    """Основной класс для планирования траектории дрона"""
    
    def __init__(self):
        self.computation_steps = 0

    def plan_trajectory(self, mission: MissionInstruction) -> Trajectory:
        """
        Основная функция: строит траекторию для миссии
        """
        self.computation_steps = 0
        
        positions = []
        velocities = []
        timestamps = []
        
        # Начальная точка
        current_time = int(time.time())
        positions.append([mission.origin.lat, mission.origin.lon, mission.origin.alt, current_time])
        velocities.append(mission.origin.speed)
        timestamps.append(current_time)
        
        # Простой алгоритм: идём через waypoints + конечную точку
        all_points = mission.waypoints + [mission.destination]
        
        for waypoint in all_points:
            self.computation_steps += 1
            current_time += 5  # 5 секунд между точками (симуляция)
            
            positions.append([waypoint.lat, waypoint.lon, waypoint.alt, current_time])
            velocities.append(waypoint.speed)
            timestamps.append(current_time)
            
            # Симулируем sensor data
            self.computation_steps += 10  # условные вычисления
        
        # Создаём Trajectory
        trajectory = Trajectory(
            positions=positions,
            velocities=velocities,
            timestamps=timestamps,
            metadata={
                "planner_version": "0.1",
                "total_waypoints": len(all_points),
                "mission_type": mission.mission_type.value
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
        data = f"{mission.mission_id}{trajectory.positions[-1]}".encode()
        computation_hash = hashlib.sha256(data).hexdigest()
        
        return PoPWArtifact(
            computation_hash=computation_hash,
            simulation_steps=self.computation_steps,
            energy_estimate=round(self.computation_steps * 0.15, 2),
            constraints_satisfied=True
        )


# Для теста
if __name__ == "__main__":
    planner = DronePlanner()
    # Здесь можно будет протестировать
    print("DronePlanner loaded successfully")