"""
DroneSync - Weather Module
Real-time weather impact on drone flight operations
Affects trajectory planning, safety scores, and mission clearance
"""
import os
import random
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class WeatherCondition:
    """Represents current weather at a location."""
    def __init__(self, wind_speed: float, wind_dir: float,
                 visibility: float, precipitation: str,
                 temperature: float):
        self.wind_speed = wind_speed
        self.wind_dir = wind_dir
        self.visibility = visibility
        self.precipitation = precipitation
        self.temperature = temperature

    def is_flyable(self) -> bool:
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
    Uses OpenWeatherMap API by coordinates (lat/lon).
    Falls back to simulated data if API key not set.
    """

    API_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, lat: float = None, lon: float = None):
        self.lat = lat
        self.lon = lon
        self.api_key = os.environ.get("OPENWEATHER_API_KEY", "")

    def get_current(self) -> WeatherCondition:
        if self.api_key and REQUESTS_AVAILABLE and self.lat is not None and self.lon is not None:
            try:
                resp = requests.get(self.API_URL, params={
                    "lat": self.lat,
                    "lon": self.lon,
                    "appid": self.api_key,
                    "units": "metric"
                }, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    wind = data.get("wind", {})
                    rain = data.get("rain", {})
                    snow = data.get("snow", {})
                    precip = "none"
                    if rain.get("1h", 0) > 2 or snow.get("1h", 0) > 0:
                        precip = "heavy"
                    elif rain.get("1h", 0) > 0:
                        precip = "light"
                    return WeatherCondition(
                        wind_speed=round(wind.get("speed", 0), 1),
                        wind_dir=round(wind.get("deg", 0), 1),
                        visibility=data.get("visibility", 10000),
                        precipitation=precip,
                        temperature=round(data["main"]["temp"], 1)
                    )
            except Exception:
                pass
        return self._simulated()

    def _simulated(self) -> WeatherCondition:
        wind = max(0, random.gauss(5.0, 2.0))
        rain = random.random() < 0.30
        precip = "light" if rain else "none"
        if rain and random.random() < 0.2:
            precip = "heavy"
        visibility = max(200, random.gauss(8000, 1000))
        return WeatherCondition(
            wind_speed=round(wind, 1),
            wind_dir=round(random.uniform(0, 360), 1),
            visibility=round(visibility),
            precipitation=precip,
            temperature=round(random.gauss(10.0, 3), 1)
        )

    def get_forecast(self, hours: int = 3) -> list:
        return [self.get_current() for _ in range(hours)]


class WeatherImpactAnalyzer:
    """
    Analyzes weather impact on drone mission parameters.
    Adjusts speed, altitude, and energy consumption.
    """

    def analyze(self, weather: WeatherCondition,
                 trajectory: list) -> dict:
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
        factor = 1.0
        factor -= min(0.4, w.wind_speed / 40)
        if w.precipitation == "light":
            factor -= 0.1
        elif w.precipitation == "heavy":
            factor -= 0.3
        return max(0.3, factor)

    def _energy_factor(self, w: WeatherCondition) -> float:
        factor = 1.0
        factor += w.wind_speed * 0.03
        if w.precipitation != "none":
            factor += 0.15
        if w.temperature < 0:
            factor += 0.10
        return round(factor, 2)

    def _safety_factor(self, w: WeatherCondition) -> float:
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
