"""Validate Open-Meteo data; keep a primary effect and optional wind overlay."""
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


def select_effect_with_reason(metrics):
    """Return effect and explanation from the same decision branch."""
    code = metrics.get("weather_code")
    snow = metrics.get("snowfall_cm")
    if (snow or 0) > 0 or code in SNOW_CODES:
        evidence = f"Снегопад {snow:g} см за интервал данных" if (snow or 0) > 0 else f"Код погоды {code:g} указывает на снег"
        return "snow", evidence + ". Снег имеет приоритет над дождём и ветром."
    rain = metrics.get("rain_mm")
    showers = metrics.get("showers_mm")
    if (rain or 0) > 0 or (showers or 0) > 0 or code in RAIN_CODES:
        evidence = []
        if (rain or 0) > 0:
            evidence.append(f"дождь {rain:g} мм")
        if (showers or 0) > 0:
            evidence.append(f"ливни {showers:g} мм")
        reason = "Осадки за интервал данных: " + ", ".join(evidence) if evidence else f"Код погоды {code:g} относится к дождевому эффекту"
        return "rain", reason + ". Дождь имеет приоритет над ветром."
    wind = metrics.get("wind_speed_kmh")
    if (wind or 0) >= WIND_THRESHOLD_KMH:
        return "wind", f"Ветер {wind / 3.6:g} м/с ({wind:g} км/ч) достигает порога {WIND_THRESHOLD_KMH / 3.6:g} м/с ({WIND_THRESHOLD_KMH:g} км/ч). Признаков снега или дождя для более приоритетного эффекта нет."
    cloud = metrics.get("cloud_cover_pct")
    if cloud is not None and cloud > SUN_MAX_CLOUD_PCT:
        return "cloudy", f"Облачность {cloud:g}% выше {SUN_MAX_CLOUD_PCT:g}%. Серые буквы с тёмными облаками; снег, дождь и ветер имеют приоритет."
    precipitation_keys = ("precipitation_mm", "snowfall_cm", "rain_mm", "showers_mm")
    dry = all(metrics.get(key) == 0 for key in precipitation_keys)
    if code in {0, 1, 2, 3} and metrics.get("is_day") == 1 and cloud is not None and cloud <= SUN_MAX_CLOUD_PCT and dry:
        return "sun", f"День, код погоды {code:g}, облачность {cloud:g}% не выше {SUN_MAX_CLOUD_PCT:g}%, осадки отсутствуют. Условия более приоритетных эффектов не выполнены."
    reasons = []
    if wind is None:
        reasons.append("скорость ветра неизвестна")
    else:
        reasons.append(f"ветер {wind:g} км/ч ниже порога {WIND_THRESHOLD_KMH:g} км/ч")
    if code is None:
        reasons.append("код погоды неизвестен")
    elif code not in {0, 1, 2, 3}:
        reasons.append(f"код погоды {code:g} не входит в разрешённые для солнца 0, 1, 2 и 3")
    if metrics.get("is_day") == 0:
        reasons.append("ночью солнечный эффект отключён")
    elif metrics.get("is_day") is None:
        reasons.append("нет данных о времени суток")
    if cloud is None:
        reasons.append("облачность неизвестна")
    elif cloud > SUN_MAX_CLOUD_PCT:
        reasons.append(f"облачность {cloud:g}% выше порога {SUN_MAX_CLOUD_PCT:g}%")
    if any(metrics.get(key) is None for key in precipitation_keys):
        reasons.append("данных об осадках недостаточно для солнечного эффекта")
    elif not dry:
        reasons.append("осадки не равны нулю, но их тип не позволяет выбрать дождь или снег")
    return "neutral", "Условия погодных эффектов не выполнены: " + "; ".join(reasons) + "."


def select_effect(metrics):
    return select_effect_with_reason(metrics)[0]


def select_effects(metrics, primary):
    """Wind may bend precipitation/cloudy letters at the existing 5 m/s threshold."""
    if (metrics.get("wind_speed_kmh") or 0) < WIND_THRESHOLD_KMH:
        return [primary]
    if primary in {"rain", "snow"}:
        return [primary, "wind"]
    if primary == "wind" and (metrics.get("cloud_cover_pct") or 0) > SUN_MAX_CLOUD_PCT:
        return ["cloudy", "wind"]
    return [primary]


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
    effect, reason = select_effect_with_reason(metrics)
    return {
        **metrics, "data_time": dt.isoformat().replace("+00:00", "Z"),
        "precipitation_interval_seconds": interval,
        "effect": effect, "effects": select_effects(metrics, effect), "effect_reason": reason,
        "missing_fields": [key for key, value in metrics.items() if value is None],
    }
