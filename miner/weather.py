"""
DroneSync - Weather Module
Real-time weather impact on drone flight operations
Affects trajectory planning, safety scores, and mission clearance
"""
import math
import random


class WeatherCondition:
    """Represents current weather at a location."""
    def __init__(self, wind_speed: float, wind_dir: float,
                 visibility: float, precipitation: str,
                 temperature: float):
        self.wind_speed = wind_speed      # m/s
        self.wind_dir = wind_dir          # degrees 0-360
        self.visibility = visibility      # meters
        self.precipitation = precipitation # none/light/heavy
        self.temperature = temperature    # celsius

    def is_flyable(self) -> bool:
        """Check if conditions allow safe flight."""
        if self.wind_speed > 15.0:
            return False
        if self.visibility < 500:
            return False
        if self.precipitation == "heavy":
            return False
        return True

    def severity(self) -> str:
        if self.wind_speed > 15 or self.precipitation == "heavy":
            return "SEVERE"
        elif self.wind_speed > 8 or self.precipitation == "light":
            return "MODERATE"
        return "CLEAR"


class WeatherService:
    """
    Weather data service for drone operations.
    In production: integrates with OpenWeatherMap API or similar.
    Currently: realistic simulated weather profiles per city.
    """

    CITY_WEATHER = {
        "zurich": {
            "avg_wind": 4.5,
            "rain_prob": 0.35,
            "avg_temp": 12.0,
            "avg_visibility": 8000
        },
        "berlin": {
            "avg_wind": 5.2,
            "rain_prob": 0.40,
            "avg_temp": 10.0,
            "avg_visibility": 7000
        },
        "kyiv": {
            "avg_wind": 4.0,
            "rain_prob": 0.30,
            "avg_temp": 8.0,
            "avg_visibility": 9000
        }
    }

    def __init__(self, city: str = "zurich"):
        self.city = city
        self.profile = self.CITY_WEATHER.get(
            city, self.CITY_WEATHER["zurich"]
        )

    def get_current(self) -> WeatherCondition:
        """Get simulated current weather conditions."""
        p = self.profile
        wind = max(0, random.gauss(p["avg_wind"], 2.0))
        rain = random.random() < p["rain_prob"]
        precip = "light" if rain else "none"
        if rain and random.random() < 0.2:
            precip = "heavy"
        visibility = max(200, random.gauss(
            p["avg_visibility"], 1000
        ))
        return WeatherCondition(
            wind_speed=round(wind, 1),
            wind_dir=round(random.uniform(0, 360), 1),
            visibility=round(visibility),
            precipitation=precip,
            temperature=round(random.gauss(p["avg_temp"], 3), 1)
        )

    def get_forecast(self, hours: int = 3) -> list:
        """Get weather forecast for next N hours."""
        return [self.get_current() for _ in range(hours)]


class WeatherImpactAnalyzer:
    """
    Analyzes weather impact on drone mission parameters.
    Adjusts speed, altitude, and energy consumption.
    """

    def analyze(self, weather: WeatherCondition,
                 trajectory: list) -> dict:
        """Calculate weather impact on mission."""
        speed_factor = self._speed_factor(weather)
        energy_factor = self._energy_factor(weather)
        safety_factor = self._safety_factor(weather)
        adjusted_duration = len(trajectory) * 5 / speed_factor

        return {
            "flyable": weather.is_flyable(),
            "severity": weather.severity(),
            "wind_speed_ms": weather.wind_speed,
            "wind_direction": weather.wind_dir,
            "visibility_m": weather.visibility,
            "precipitation": weather.precipitation,
            "temperature_c": weather.temperature,
            "speed_factor": round(speed_factor, 2),
            "energy_factor": round(energy_factor, 2),
            "safety_factor": round(safety_factor, 2),
            "adjusted_duration_s": round(adjusted_duration, 1),
            "recommendation": self._recommendation(weather)
        }

    def _speed_factor(self, w: WeatherCondition) -> float:
        """How much weather reduces speed (1.0 = normal)."""
        factor = 1.0
        factor -= min(0.4, w.wind_speed / 40)
        if w.precipitation == "light":
            factor -= 0.1
        elif w.precipitation == "heavy":
            factor -= 0.3
        return max(0.3, factor)

    def _energy_factor(self, w: WeatherCondition) -> float:
        """How much more energy is needed (1.0 = normal)."""
        factor = 1.0
        factor += w.wind_speed * 0.03
        if w.precipitation != "none":
            factor += 0.15
        if w.temperature < 0:
            factor += 0.10
        return round(factor, 2)

    def _safety_factor(self, w: WeatherCondition) -> float:
        """Safety score adjustment (1.0 = no impact)."""
        factor = 1.0
        if w.wind_speed > 10:
            factor -= 0.2
        if w.visibility < 1000:
            factor -= 0.15
        if w.precipitation == "heavy":
            factor -= 0.25
        return max(0.3, factor)

    def _recommendation(self, w: WeatherCondition) -> str:
        if not w.is_flyable():
            return "GROUND_ALL - conditions unsafe for flight"
        elif w.severity() == "MODERATE":
            return "FLY_WITH_CAUTION - reduce speed and altitude"
        return "FLY_NORMAL - conditions optimal"