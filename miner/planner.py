"""
DroneSync — Urban Path Planner
"""

import math
from typing import List, Tuple, Optional
from dronesync.protocol import Waypoint, MissionInstruction, TrajectoryPoint
import time


class UrbanPathPlanner:
    SAFE_ALTITUDE_MIN = 30.0
    SAFE_ALTITUDE_MAX = 120.0

    def __init__(self):
        self._no_fly_zones = []

    def add_no_fly_zone(self, lat: float, lon: float, radius_m: float):
        self._no_fly_zones.append((lat, lon, radius_m))

    def haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def is_in_no_fly_zone(self, lat: float, lon: float) -> bool:
        for nfz_lat, nfz_lon, radius in self._no_fly_zones:
            if self.haversine(lat, lon, nfz_lat, nfz_lon) < radius:
                return True
        return False

    def bearing(self, lat1, lon1, lat2, lon2) -> float:
        dlon = math.radians(lon2 - lon1)
        lat1r, lat2r = math.radians(lat1), math.radians(lat2)
        x = math.sin(dlon) * math.cos(lat2r)
        y = (math.cos(lat1r) * math.sin(lat2r) -
             math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon))
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    def plan_route(self, mission: MissionInstruction,
                   drone_id: str = "drone_0") -> list:
        origin = mission.origin
        dest = mission.destination
        trajectory = []
        t = time.time()

        # Takeoff
        trajectory.append({"t": t, "lat": origin.lat, "lon": origin.lon,
                           "alt": 0.0, "speed": 0.0, "drone_id": drone_id})
        t += 5.0

        # Climb
        trajectory.append({"t": t, "lat": origin.lat, "lon": origin.lon,
                           "alt": self.SAFE_ALTITUDE_MIN, "speed": 2.0,
                           "drone_id": drone_id})

        # En-route
        n = 10
        for i in range(1, n):
            frac = i / n
            lat = origin.lat + frac * (dest.lat - origin.lat)
            lon = origin.lon + frac * (dest.lon - origin.lon)
            if self.is_in_no_fly_zone(lat, lon):
                lat += 0.0003
            t += 2.0
            trajectory.append({"t": t, "lat": lat, "lon": lon,
                               "alt": self.SAFE_ALTITUDE_MIN,
                               "speed": origin.speed, "drone_id": drone_id})

        # Landing
        t += 5.0
        trajectory.append({"t": t, "lat": dest.lat, "lon": dest.lon,
                           "alt": 0.0, "speed": 0.0, "drone_id": drone_id})
        return trajectory