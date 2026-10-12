"""HTTP client and per-city in-memory cache (one backend process)."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from threading import Lock
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.config import CITIES, CACHE_SECONDS, RETRY_SECONDS, REQUEST_TIMEOUT_SECONDS, MAX_DATA_AGE_SECONDS
from backend.weather_logic import FIELDS, normalize

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def fetch_current(city):
    query = urlencode({
        "latitude": city["latitude"], "longitude": city["longitude"],
        "current": ",".join(field[0] for field in FIELDS.values()),
        "timezone": "GMT", "temperature_unit": "celsius",
        "wind_speed_unit": "kmh", "precipitation_unit": "mm",
    })
    with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


class WeatherService:
    def __init__(self, fetcher=fetch_current, clock=monotonic, now=utcnow):
        self.fetcher, self.clock, self.now = fetcher, clock, now
        self.cache = {}
        self.next_attempt = {}
        self.errors = {}
        self.lock = Lock()

    def get_weather(self):
        # Serializes refreshes so simultaneous browsers cannot multiply requests.
        with self.lock:
            for city in CITIES:
                key = city["id"]
                if self.clock() < self.next_attempt.get(key, 0):
                    continue
                try:
                    data = normalize(self.fetcher(city))
                    timestamp = datetime.fromisoformat(data["data_time"].replace("Z", "+00:00"))
                    if (timestamp - self.now()).total_seconds() > 300:
                        raise ValueError("Future data timestamp")
                    self.cache[key] = {**data, "fetched_at": iso(self.now())}
                    self.errors.pop(key, None)
                    self.next_attempt[key] = self.clock() + CACHE_SECONDS
                except (URLError, OSError, ValueError, TypeError) as error:
                    logger.warning("Weather refresh failed for %s: %s", key, type(error).__name__)
                    self.errors[key] = "upstream_unavailable"
                    self.next_attempt[key] = self.clock() + RETRY_SECONDS

            cities = []
            for city in CITIES:
                key = city["id"]
                data = deepcopy(self.cache.get(key))
                if data is None:
                    data = {field: None for field in FIELDS}
                    data.update(effect="neutral", data_time=None, fetched_at=None,
                                precipitation_interval_seconds=None, missing_fields=list(FIELDS))
                    status = "unavailable"
                else:
                    dt = datetime.fromisoformat(data["data_time"].replace("Z", "+00:00"))
                    status = "stale" if key in self.errors or (self.now() - dt).total_seconds() > MAX_DATA_AGE_SECONDS else "fresh"
                cities.append({**city, **data, "status": status, "error": self.errors.get(key)})
            return {
                "source": "Open-Meteo", "source_url": "https://open-meteo.com/",
                "data_kind": "weather_model", "mode": "live",
                "generated_at": iso(self.now()), "refresh_interval_seconds": CACHE_SECONDS,
                "retry_interval_seconds": RETRY_SECONDS,
                "status": "ok" if all(c["status"] == "fresh" for c in cities) else "degraded",
                "cities": cities,
            }
