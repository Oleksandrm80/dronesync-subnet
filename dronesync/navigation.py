# dronesync/navigation.py
"""
DroneSync Navigation — Flight path analysis and safety logic.
"""

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from dronesync.protocol import (
    Waypoint, FlightSegment, NavAlert, AlertLevel
)


def haversine_distance(lat1: float, lon1: float,
                        lat2: float, lon2: float) -> float:
    """Distance between two GPS points in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1: float, lon1: float,
            lat2: float, lon2: float) -> float:
    """True bearing in degrees from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


@dataclass
class PathDeviation:
    """How far the drone strayed from its planned segment."""
    segment_index: int
    deviation_m: float
    max_allowed_m: float = 50.0

    @property
    def exceeded(self) -> bool:
        return self.deviation_m > self.max_allowed_m

    @property
    def severity(self) -> AlertLevel:
        if self.deviation_m > self.max_allowed_m * 2:
            return AlertLevel.CRITICAL
        if self.deviation_m > self.max_allowed_m:
            return AlertLevel.ALERT
        return AlertLevel.NOTICE


@dataclass
class NavETA:
    """Estimated time of arrival for each NavPoint."""
    waypoint_index: int
    planned_eta: float
    actual_eta: Optional[float] = None

    @property
    def delay_s(self) -> float:
        if self.actual_eta is None:
            return 0.0
        return max(0.0, self.actual_eta - self.planned_eta)


@dataclass
class SwarmTarget:
    """Another drone tracked in the operational zone."""
    drone_id: str
    lat: float
    lon: float
    alt: float
    speed: float
    bearing_deg: float
    last_seen: float = field(default_factory=time.time)

    def distance_to(self, lat: float, lon: float) -> float:
        return haversine_distance(self.lat, self.lon, lat, lon)


@dataclass
class SimFlight:
    """Virtual simulation of a manoeuvre before execution."""
    segments: List[FlightSegment]
    alerts: List[NavAlert] = field(default_factory=list)
    safe: bool = True

    def summary(self) -> Dict:
        return {
            "segments": len(self.segments),
            "alerts": len(self.alerts),
            "safe": self.safe,
            "critical": sum(1 for a in self.alerts if a.level == AlertLevel.CRITICAL),
        }


class NavigationEngine:
    """
    Core DroneSync navigation logic.
    Builds flight segments, checks safety, generates alerts.
    """

    FLOOR_ALTITUDE_DEFAULT = 20.0
    VERTICAL_CLEARANCE_MIN = 10.0
    PATH_DEVIATION_MAX_M = 50.0

    def build_segments(self, waypoints: List[Waypoint]) -> List[FlightSegment]:
        """Convert waypoint list into FlightSegments with distances and ETAs."""
        segments = []
        for i in range(len(waypoints) - 1):
            a, b = waypoints[i], waypoints[i + 1]
            dist = haversine_distance(a.lat, a.lon, b.lat, b.lon)
            speed = max(a.speed, 1.0)
            duration = dist / speed
            segments.append(FlightSegment(
                from_point=a,
                to_point=b,
                segment_index=i,
                planned_duration_s=round(duration, 2),
                floor_altitude=self.FLOOR_ALTITUDE_DEFAULT,
                vertical_clearance=self.VERTICAL_CLEARANCE_MIN,
            ))
        return segments

    def check_floor_altitude(self, segments: List[FlightSegment]) -> List[NavAlert]:
        """Generate alerts for segments that violate floor altitude."""
        alerts = []
        for seg in segments:
            min_alt = min(seg.from_point.alt, seg.to_point.alt)
            if min_alt < seg.floor_altitude:
                level = AlertLevel.CRITICAL if min_alt < seg.floor_altitude / 2 else AlertLevel.ALERT
                alerts.append(NavAlert(
                    level=level,
                    code="FLOOR_ALT_VIOLATION",
                    message=f"Segment {seg.segment_index}: altitude {min_alt}m below floor {seg.floor_altitude}m",
                    segment_index=seg.segment_index,
                ))
        return alerts

    def check_vertical_clearance(self, segments: List[FlightSegment]) -> List[NavAlert]:
        """Generate alerts for insufficient vertical clearance."""
        alerts = []
        for seg in segments:
            if seg.vertical_clearance < self.VERTICAL_CLEARANCE_MIN:
                alerts.append(NavAlert(
                    level=AlertLevel.ALERT,
                    code="VERT_CLEARANCE_LOW",
                    message=f"Segment {seg.segment_index}: clearance {seg.vertical_clearance}m below minimum {self.VERTICAL_CLEARANCE_MIN}m",
                    segment_index=seg.segment_index,
                ))
        return alerts

    def calculate_path_deviation(self, planned: List[Waypoint],
                                  actual: List[Waypoint]) -> List[PathDeviation]:
        """Compare planned vs actual waypoints and return deviations."""
        deviations = []
        for i, (p, a) in enumerate(zip(planned, actual)):
            dev_m = haversine_distance(p.lat, p.lon, a.lat, a.lon)
            deviations.append(PathDeviation(
                segment_index=i,
                deviation_m=round(dev_m, 2),
                max_allowed_m=self.PATH_DEVIATION_MAX_M,
            ))
        return deviations

    def calculate_etas(self, segments: List[FlightSegment],
                        start_time: Optional[float] = None) -> List[NavETA]:
        """Calculate NavETA for each segment endpoint."""
        t = start_time or time.time()
        etas = []
        for seg in segments:
            t += seg.planned_duration_s
            etas.append(NavETA(waypoint_index=seg.segment_index + 1, planned_eta=round(t, 2)))
        return etas

    def sim_flight(self, waypoints: List[Waypoint]) -> SimFlight:
        """Run a SimFlight — virtual check before real execution."""
        segments = self.build_segments(waypoints)
        alerts = self.check_floor_altitude(segments)
        alerts += self.check_vertical_clearance(segments)
        safe = not any(a.level == AlertLevel.CRITICAL for a in alerts)
        return SimFlight(segments=segments, alerts=alerts, safe=safe)

    def track_swarm(self, drone_data: List[Dict]) -> List[SwarmTarget]:
        """Build SwarmTarget list from raw drone telemetry."""
        targets = []
        for d in drone_data:
            targets.append(SwarmTarget(
                drone_id=d.get("drone_id", "UNKNOWN"),
                lat=d.get("lat", 0.0),
                lon=d.get("lon", 0.0),
                alt=d.get("alt", 0.0),
                speed=d.get("speed", 0.0),
                bearing_deg=d.get("bearing_deg", 0.0),
            ))
        return targets
