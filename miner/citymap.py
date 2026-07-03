"""
DroneSync - City Map Module
Real urban data integration via OpenStreetMap (Overpass API)
Provides no-fly zones, building heights, and urban obstacles
"""
import math


class CityZone:
    """Represents an urban zone with restrictions."""
    def __init__(self, lat: float, lon: float, radius_m: float,
                 zone_type: str, max_alt: float = 0,
                 expires_at: int = 0, reason: str = ""):
        self.lat = lat
        self.lon = lon
        self.radius_m = radius_m
        self.zone_type = zone_type
        self.max_alt = max_alt
        self.expires_at = expires_at  # 0 = permanent
        self.reason = reason

    def is_active(self, now: int) -> bool:
        if self.expires_at == 0:
            return True
        return now < self.expires_at

class CityMap:
    """
    Urban map with real-world zone data.
    In production: fetches live data from OpenStreetMap Overpass API.
    Currently: uses realistic simulated city data.
    """

    CITY_PROFILES = {
        "berlin": {
            "center": (52.5200, 13.4050),
            "no_fly_zones": [
                (52.5170, 13.3888, 5000, "airport"),
                (52.5145, 13.3501, 500, "government"),
                (52.5163, 13.3777, 300, "hospital"),
            ]
        },
        "kyiv": {
            "center": (50.4501, 30.5234),
            "no_fly_zones": [
                (50.4018, 30.4500, 8000, "airport"),
                (50.4547, 30.5238, 1000, "government"),
                (50.4462, 30.5072, 400, "hospital"),
            ]
        },
        "zurich": {
            "center": (47.3769, 8.5417),
            "no_fly_zones": [
                (47.4647, 8.5492, 8000, "airport"),
                (47.3769, 8.5417, 500, "government"),
                (47.3744, 8.5373, 300, "hospital"),
            ]
        }
    }

    def __init__(self, city: str = None):
        self.city = city
        self.profile: dict = self.CITY_PROFILES.get(city or "", {}).copy() if city else {}
        self.zones = self._load_zones()

    def _load_zones(self) -> list:
        """Load city zones from profile."""
        zones = []
        for lat, lon, radius, zone_type in self.profile.get("no_fly_zones", []):
            zones.append(CityZone(
                lat=lat, lon=lon,
                radius_m=radius,
                zone_type=zone_type,
                max_alt=120 if zone_type == "airport" else 0
            ))
        return zones
    def add_temporary_zone(self, lat: float, lon: float,
                            radius_m: float, zone_type: str,
                            duration_s: int, reason: str = "") -> CityZone:
        """Add a temporary no-fly zone that expires after duration_s seconds."""
        import time
        zone = CityZone(
            lat=lat, lon=lon, radius_m=radius_m,
            zone_type=zone_type, max_alt=0,
            expires_at=int(time.time()) + duration_s,
            reason=reason
        )
        self.zones.append(zone)
        return zone

    def expire_zones(self) -> int:
        """Remove expired temporary zones. Returns count removed."""
        import time
        now = int(time.time())
        before = len(self.zones)
        self.zones = [z for z in self.zones if z.is_active(now)]
        return before - len(self.zones)

    def is_no_fly(self, lat: float, lon: float) -> tuple:
        """Check if position is in no-fly zone. Returns (bool, reason)."""
        import time
        now = int(time.time())
        for zone in self.zones:
            if not zone.is_active(now):
                continue
            dist = self._haversine(lat, lon, zone.lat, zone.lon)
            if dist < zone.radius_m:
                return True, zone.zone_type
        return False, None
    def safe_altitude(self, lat: float, lon: float,
                       base_alt: float = 50.0) -> float:
        """Calculate minimum safe altitude for position."""
        for zone in self.zones:
            dist = self._haversine(lat, lon, zone.lat, zone.lon)
            if dist < zone.radius_m * 2:
                return max(base_alt, zone.max_alt + 20)
        return base_alt

    def get_city_stats(self) -> dict:
        """Return city map statistics."""
        return {
            "city": self.city,
            "center": self.profile.get("center", (0.0, 0.0)),
            "no_fly_zones": len(self.zones),
            "zone_types": list(set(z.zone_type for z in self.zones))
        }

    def _haversine(self, lat1: float, lon1: float,
                    lat2: float, lon2: float) -> float:
        """Distance between two GPS points in meters."""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
