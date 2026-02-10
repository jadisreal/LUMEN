import requests
from tts import speak

# Open-Meteo geocoding + forecast (free, no API key)
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code descriptions
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}


def _geocode(city: str) -> tuple[float, float, str] | None:
    """Get latitude, longitude, and resolved name for a city."""
    try:
        resp = requests.get(GEOCODE_URL, params={"name": city, "count": 1}, timeout=10)
        data = resp.json()
        results = data.get("results")
        if not results:
            return None
        r = results[0]
        return r["latitude"], r["longitude"], r.get("name", city)
    except Exception:
        return None


def _get_forecast(lat: float, lon: float) -> dict | None:
    """Fetch current weather from Open-Meteo."""
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
        }
        resp = requests.get(FORECAST_URL, params=params, timeout=10)
        data = resp.json()
        return data.get("current")
    except Exception:
        return None


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None
):
    """
    Weather report action.
    Fetches real weather data from Open-Meteo and speaks it.
    """

    city = parameters.get("city")
    if not city or not isinstance(city, str):
        msg = "The city is missing for the weather report."
        _speak_and_log(msg, player)
        return msg

    city = city.strip()

    geo = _geocode(city)
    if not geo:
        msg = f"I couldn't find the location for {city}."
        _speak_and_log(msg, player)
        return msg

    lat, lon, resolved_name = geo
    current = _get_forecast(lat, lon)

    if not current:
        msg = f"I couldn't fetch weather data for {resolved_name}."
        _speak_and_log(msg, player)
        return msg

    temp = current.get("temperature_2m", "?")
    humidity = current.get("relative_humidity_2m", "?")
    wind = current.get("wind_speed_10m", "?")
    code = current.get("weather_code", -1)
    condition = WMO_CODES.get(code, "unknown conditions")

    msg = (
        f"Weather in {resolved_name}: {temp}°C, {condition}, "
        f"humidity {humidity}%, wind {wind} km/h."
    )
    _speak_and_log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=f"weather {city}", response=msg)
        except Exception:
            pass

    return msg


def _speak_and_log(message: str, player=None):
    """Helper: log + TTS safely"""
    if player:
        try:
            player.write_log(f"Lumen: {message}")
        except Exception:
            pass

    try:
        speak(message)
    except Exception:
        pass
