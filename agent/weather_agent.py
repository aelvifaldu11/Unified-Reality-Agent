import os
import requests
from typing import Dict, Any

from utils.logger import log

class WeatherAgent:
    """
    WeatherAgent:
    - If secrets_loader.mode == 'real' and WEATHER_API_KEY present -> call OpenWeather 
    - Otherwise dynamically simulate weather based on location and event_type in demo mode.
    """

    def __init__(self, secrets_loader, default_city: str = "Mumbai"):
        self.secrets = secrets_loader
        self.default_city = default_city
        self.api_key = self.secrets.get_secret("WEATHER_API_KEY")

    def _call_real_api(self, city: str) -> Dict[str, Any]:
        try:
            if not self.api_key:
                raise RuntimeError("no weather api key")

            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"

            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            d = resp.json()

            out = {
                "city": city,
                "temp_c": d.get("main", {}).get("temp"),
                "condition": d.get("weather", [{}])[0].get("description"),
                "humidity": f"{d.get('main', {}).get('humidity')}%",
                "wind_speed": f"{d.get('wind', {}).get('speed')} km/h",
                "raw": d
            }
            return out
        except Exception as e:
            log(f"weather_agent: real API call failed: {e}")
            return {}

    def get_weather(self, city: str = None, event_type: str = None) -> Dict[str, Any]:
        city = city or self.default_city
        
        if getattr(self.secrets, "mode", "demo") == "real" and self.api_key:
            return self._call_real_api(city)

        # Demo mode: Dynamic weather simulation to showcase URA capabilities
        condition = "Clear"
        temperature = "29°C"
        humidity = "72%"
        wind_speed = "12 km/h"

        city_lower = city.lower().strip()
        event_lower = (event_type or "").lower().strip()

        # London: typically rainy/drizzle
        if "london" in city_lower:
            condition = "Drizzle"
            temperature = "15°C"
            humidity = "85%"
            wind_speed = "18 km/h"
        # Paris: typically cloudy
        elif "paris" in city_lower:
            condition = "Cloudy"
            temperature = "17°C"
            humidity = "68%"
            wind_speed = "11 km/h"
        # Seattle: rainy
        elif "seattle" in city_lower:
            condition = "Rainy"
            temperature = "12°C"
            humidity = "90%"
            wind_speed = "14 km/h"
        # Mumbai/General: dynamic based on event type
        else:
            if event_lower == "meeting":
                # Force rain prediction for meetings to trigger the umbrella suggestion proactively
                condition = "Heavy Rain"
                temperature = "22°C"
                humidity = "95%"
                wind_speed = "22 km/h"
            elif event_lower in ["viva", "exam", "test"]:
                # Force nice clear weather for viva/exams
                condition = "Clear"
                temperature = "29°C"
                humidity = "65%"
                wind_speed = "10 km/h"
            else:
                condition = "Sunny"
                temperature = "30°C"
                humidity = "60%"
                wind_speed = "15 km/h"

        return {
            "city": city,
            "temperature": temperature,
            "condition": condition,
            "humidity": humidity,
            "wind_speed": wind_speed
        }
