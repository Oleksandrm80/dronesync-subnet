"""
DroneSync - Dynamic Obstacles Module
Moving obstacles: other drones, birds, helicopters, vehicles
Real-time collision prediction and avoidance
"""
import math
import random


class MovingObstacle:
    def __init__(self, obstacle_id: str, obs_type: str,
                 lat: float, lon: float, alt: float,
                 speed_ms: float, heading: float):
        self.obstacle_id = obstacle_id
        self.obs_type = obs_type  # drone, bird, helicopter, vehicle
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.speed_ms = speed_ms
        self.heading = heading

    def predict_position(self, seconds: float) -> tuple:
        """Predict position after N seconds."""
        dist = self.speed_ms * seconds
        dlat = (dist * math.cos(math.radians(self.heading))) / 111000
        dlon = (dist * math.sin(math.radians(self.heading))) / (
            111000 * math.cos(math.radians(self.lat))
        )
        return self.lat + dlat, self.lon + dlon, self.alt


class DynamicObstacleManager:
    """
    Manages moving obstacles in urban airspace.
    Predicts collisions and generates avoidance maneuvers.
    """

    SAFE_DISTANCE_M = 50.0
    PREDICTION_TIME_S = 10.0

    def __init__(self, seed: int = 42):
        self.obstacles: list = []
        self._rng = random.Random(seed)
        self._generate_urban_obstacles()

    def _generate_urban_obstacles(self):
        """Generate realistic urban airspace obstacles."""
        types = [
            ("drone", 8.0), ("bird", 12.0),
            ("helicopter", 20.0), ("drone", 6.0)
        ]
        for i, (obs_type, speed) in enumerate(types):
            self.obstacles.append(MovingObstacle(
                obstacle_id="OBS_" + str(i).zfill(3),
                obs_type=obs_type,
                lat=47.3769 + self._rng.uniform(-0.01, 0.01),
                lon=8.5417 + self._rng.uniform(-0.01, 0.01),
                alt=self._rng.uniform(30, 100),
                speed_ms=speed + self._rng.uniform(-2, 2),
                heading=self._rng.uniform(0, 360)
            ))

    def check_trajectory(self, positions: list) -> dict:
        """Check trajectory against all moving obstacles."""
        conflicts = []
        for obs in self.obstacles:
            for i, pos in enumerate(positions):
                pred_lat, pred_lon, pred_alt = obs.predict_position(
                    i * 5.0
                )
                dist = self._haversine(
                    pos[0], pos[1], pred_lat, pred_lon
                )
                alt_diff = abs(pos[2] - pred_alt)
                if dist < self.SAFE_DISTANCE_M and alt_diff < 20:
                    conflicts.append({
                        "obstacle_id": obs.obstacle_id,
                        "type": obs.obs_type,
                        "step": i,
                        "distance_m": round(dist, 1),
                        "severity": "HIGH" if dist < 20 else "MEDIUM"
                    })

        return {
            "conflicts_found": len(conflicts),
            "trajectory_safe": len(conflicts) == 0,
            "conflicts": conflicts[:3],
            "recommendation": "REROUTE" if conflicts else "PROCEED",
            "obstacles_tracked": len(self.obstacles)
        }

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))