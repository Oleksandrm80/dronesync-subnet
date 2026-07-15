import math
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class GeoZone:
    zone_id: str
    name: str
    zone_type: str  # "restricted", "no_fly", "allowed"
    center_lat: float
    center_lon: float
    radius_m: float
    min_alt: float = 0.0
    max_alt: float = 500.0


class GeoFencer:
    def __init__(self):
        self.zones: List[GeoZone] = []

    def add_zone(self, zone: GeoZone):
        self.zones.append(zone)

    def remove_zone(self, zone_id: str):
        self.zones = [z for z in self.zones if z.zone_id != zone_id]

    def _distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def check(self, lat: float, lon: float, alt: float = 0.0) -> Tuple[bool, Optional[GeoZone]]:
        """Returns (is_allowed, violated_zone)"""
        for zone in self.zones:
            dist = self._distance_m(lat, lon, zone.center_lat, zone.center_lon)
            if dist <= zone.radius_m and zone.min_alt <= alt <= zone.max_alt:
                if zone.zone_type in ("restricted", "no_fly"):
                    return False, zone
        return True, None

    def get_violations(self, lat: float, lon: float, alt: float = 0.0) -> List[GeoZone]:
        violations = []
        for zone in self.zones:
            dist = self._distance_m(lat, lon, zone.center_lat, zone.center_lon)
            if dist <= zone.radius_m and zone.min_alt <= alt <= zone.max_alt:
                if zone.zone_type in ("restricted", "no_fly"):
                    violations.append(zone)
        return violations


geofencer = GeoFencer()
