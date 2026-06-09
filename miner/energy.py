"""
DroneSync - Energy Optimizer Module
Battery consumption modeling and route optimization
Critical for real-world drone operations
"""
import math


class BatteryModel:
    """
    Models drone battery consumption during flight.
    Accounts for wind, payload, altitude, and maneuvers.
    """

    def __init__(self, capacity_wh: float = 100.0,
                 drone_weight_kg: float = 2.5,
                 payload_kg: float = 0.5):
        self.capacity_wh = capacity_wh
        self.drone_weight_kg = drone_weight_kg
        self.payload_kg = payload_kg
        self.total_weight = drone_weight_kg + payload_kg

    def consumption_per_km(self, speed_ms: float,
                            wind_ms: float = 0.0,
                            altitude: float = 50.0) -> float:
        """Calculate Wh per km based on flight conditions."""
        base = 15.0 * self.total_weight / 3.0
        wind_factor = 1.0 + (wind_ms / 10.0) ** 2
        alt_factor = 1.0 + max(0, (altitude - 50) / 200)
        speed_factor = 1.0 + abs(speed_ms - 10) / 20
        return base * wind_factor * alt_factor * speed_factor

    def estimate_range_km(self, speed_ms: float = 10.0,
                           wind_ms: float = 0.0) -> float:
        """Estimate maximum range in km."""
        wh_per_km = self.consumption_per_km(speed_ms, wind_ms)
        usable = self.capacity_wh * 0.8
        return round(usable / wh_per_km, 2)


class EnergyOptimizer:
    """
    Optimizes drone routes for minimum energy consumption.
    Balances speed, altitude, and path length.
    """

    def __init__(self, battery: BatteryModel = None):
        self.battery = battery or BatteryModel()

    def analyze_trajectory(self, positions: list,
                            wind_ms: float = 0.0) -> dict:
        """Analyze energy consumption for a trajectory."""
        total_dist_km = 0.0
        total_wh = 0.0
        segment_data = []

        for i in range(1, len(positions)):
            p1 = positions[i-1]
            p2 = positions[i]
            dist = self._haversine(p1[0], p1[1], p2[0], p2[1]) / 1000
            alt = (p1[2] + p2[2]) / 2
            wh = dist * self.battery.consumption_per_km(
                speed_ms=10.0, wind_ms=wind_ms, altitude=alt
            )
            total_dist_km += dist
            total_wh += wh
            segment_data.append({
                "segment": i,
                "dist_km": round(dist, 4),
                "wh_used": round(wh, 3)
            })

        battery_pct = (total_wh / self.battery.capacity_wh) * 100
        remaining_pct = 100 - battery_pct

        return {
            "total_distance_km": round(total_dist_km, 3),
            "total_energy_wh": round(total_wh, 3),
            "battery_used_pct": round(battery_pct, 1),
            "battery_remaining_pct": round(remaining_pct, 1),
            "mission_feasible": remaining_pct > 20,
            "efficiency_rating": self._efficiency_rating(battery_pct),
            "recommendation": self._recommendation(remaining_pct)
        }

    def optimal_speed(self, wind_ms: float = 0.0) -> float:
        """Calculate optimal speed for minimum energy consumption."""
        best_speed = 10.0
        best_efficiency = float("inf")
        for speed in range(5, 25):
            wh = self.battery.consumption_per_km(speed, wind_ms)
            if wh < best_efficiency:
                best_efficiency = wh
                best_speed = speed
        return float(best_speed)

    def _efficiency_rating(self, battery_pct: float) -> str:
        if battery_pct < 20:
            return "EXCELLENT"
        elif battery_pct < 40:
            return "GOOD"
        elif battery_pct < 60:
            return "ACCEPTABLE"
        return "POOR"
    def _recommendation(self, remaining_pct: float) -> str:
        if remaining_pct < 20:
            return "ABORT - insufficient battery for safe return"
        elif remaining_pct < 35:
            return "CAUTION - limited battery reserve"
        return "GO - sufficient battery for mission"

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi/2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
