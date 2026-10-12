"""Validate Open-Meteo current data and choose a single visual effect."""
from datetime import datetime, timezone
from math import isfinite

from backend.config import SUN_MAX_CLOUD_PCT, WIND_THRESHOLD_KMH

# output field: (provider field, expected unit, lower bound, upper bound)
FIELDS = {
    "temperature_c": ("temperature_2m", "°C", -100, 70),
    "precipitation_mm": ("precipitation", "mm", 0, None),
    "rain_mm": ("rain", "mm", 0, None),
    "showers_mm": ("showers", "mm", 0, None),
    "snowfall_cm": ("snowfall", "cm", 0, None),
    "wind_speed_kmh": ("wind_speed_10m", "km/h", 0, None),
    "wind_direction_deg": ("wind_direction_10m", "°", 0, 360),
    "cloud_cover_pct": ("cloud_cover", "%", 0, 100),
    "weather_code": ("weather_code", "wmo code", 0, 99),
    "is_day": ("is_day", "", 0, 1),
}
SNOW_CODES = {71, 73, 75, 77, 85, 86}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
VALID_CODES = {0, 1, 2, 3, 45, 48} | SNOW_CODES | RAIN_CODES


def number(value, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        return None
    if (low is not None and value < low) or (high is not None and value > high):
        return None
    return value


def select_effect(metrics):
    code = metrics.get("weather_code")
    if (metrics.get("snowfall_cm") or 0) > 0 or code in SNOW_CODES:
        return "snow"
    if any((metrics.get(key) or 0) > 0 for key in ("rain_mm", "showers_mm")) or code in RAIN_CODES:
        return "rain"
    if (metrics.get("wind_speed_kmh") or 0) >= WIND_THRESHOLD_KMH:
        return "wind"
    cloud = metrics.get("cloud_cover_pct")
    # Missing precipitation information must not imply sunshine.
    dry = all(metrics.get(key) == 0 for key in ("precipitation_mm", "snowfall_cm", "rain_mm", "showers_mm"))
    if code in {0, 1} and metrics.get("is_day") == 1 and cloud is not None and cloud <= SUN_MAX_CLOUD_PCT and dry:
        return "sun"
    return "neutral"


def normalize(payload):
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("Invalid provider response")
    current, units = payload.get("current"), payload.get("current_units")
    if not isinstance(current, dict) or not isinstance(units, dict):
        raise ValueError("Missing current data or units")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Expected UTC timestamps")
    stamp = current.get("time")
    if not isinstance(stamp, str):
        raise ValueError("Missing data timestamp")
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    interval = number(current.get("interval"), 1)
    if interval is None or units.get("interval") != "seconds":
        raise ValueError("Missing aggregation interval")
    metrics = {}
    for output, (field, unit, low, high) in FIELDS.items():
        metrics[output] = number(current.get(field), low, high) if units.get(field) == unit else None
    if metrics["weather_code"] not in VALID_CODES:
        metrics["weather_code"] = None
    if metrics["is_day"] not in (0, 1):
        metrics["is_day"] = None
    if all(metrics[key] is None for key in ("weather_code", "snowfall_cm", "rain_mm", "wind_speed_kmh", "cloud_cover_pct")):
        raise ValueError("No usable weather metrics")
    return {
        **metrics, "data_time": dt.isoformat().replace("+00:00", "Z"),
        "precipitation_interval_seconds": interval,
        "effect": select_effect(metrics),
        "missing_fields": [key for key, value in metrics.items() if value is None],
    }
