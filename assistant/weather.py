"""Weather via Open-Meteo (no API key)."""
from __future__ import annotations

from typing import Optional

import config

_UNITS = config.WEATHER_UNITS if hasattr(config, "WEATHER_UNITS") else "imperial"


def get_weather(city_or_zip: Optional[str] = None) -> str:
    """
    Get current weather. If city_or_zip is None, tries to use IP-based location.
    Otherwise pass a city name or "zip: 90210" style.
    """
    try:
        import requests
    except ImportError:
        return "Requests library is required for weather."

    base = "https://api.open-meteo.com/v1/forecast"
    params = {
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation",
        "temperature_unit": "fahrenheit" if _UNITS == "imperial" else "celsius",
        "wind_speed_unit": "mph" if _UNITS == "imperial" else "kmh",
    }
    lat, lon = None, None
    if city_or_zip and city_or_zip.strip():
        place = city_or_zip.strip()
        if place.lower().startswith("zip") or place[0].isdigit():
            # Geocode zip/code
            try:
                r = requests.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": place.replace("zip", "").strip(), "count": 1},
                    timeout=5,
                )
                if r.ok and r.json().get("results"):
                    res = r.json()["results"][0]
                    lat, lon = res["latitude"], res["longitude"]
                    place = res.get("name", place)
            except Exception:
                pass
        if lat is None:
            try:
                r = requests.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": place, "count": 1},
                    timeout=5,
                )
                if r.ok and r.json().get("results"):
                    res = r.json()["results"][0]
                    lat, lon = res["latitude"], res["longitude"]
                    place = res.get("name", place)
            except Exception:
                pass
    if lat is None:
        try:
            r = requests.get("https://ipapi.co/json/", timeout=5)
            if r.ok:
                data = r.json()
                lat, lon = data.get("latitude"), data.get("longitude")
                place = data.get("city", "your location")
        except Exception:
            place = "your location"
            lat, lon = 40.7, -74.0
    if lat is None or lon is None:
        lat, lon = 40.7, -74.0
    params["latitude"] = lat
    params["longitude"] = lon
    try:
        r = requests.get(base, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        cur = data.get("current", {})
        temp = cur.get("temperature_2m", "?")
        unit = "°F" if _UNITS == "imperial" else "°C"
        code = cur.get("weather_code", 0)
        desc = _weather_desc(code)
        wind = cur.get("wind_speed_10m", "?")
        return f"In {place}: {temp}{unit}, {desc}. Wind {wind}."
    except Exception as e:
        return f"Weather unavailable: {e}"


def _weather_desc(code: int) -> str:
    codes = {
        0: "clear",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy",
        51: "drizzle",
        53: "drizzle",
        55: "drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        71: "snow",
        73: "snow",
        75: "heavy snow",
        80: "rain showers",
        81: "rain showers",
        82: "heavy rain showers",
        95: "thunderstorm",
        96: "thunderstorm with hail",
    }
    return codes.get(code, "unknown conditions")
