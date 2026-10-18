"""HTTP client and per-city in-memory cache (one backend process)."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
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



def fetch_many(cities):
    """Fetch small batches concurrently; failures remain local to a batch."""
    if not cities:
        return {}
    chunks = [cities[i:i+40] for i in range(0, len(cities), 40)]
    def fetch_chunk(chunk):
        params = {
            "latitude": ",".join(str(c["latitude"]) for c in chunk),
            "longitude": ",".join(str(c["longitude"]) for c in chunk),
            "current": ",".join(field[0] for field in FIELDS.values()),
            "timezone": "GMT", "temperature_unit": "celsius",
            "wind_speed_unit": "kmh", "precipitation_unit": "mm",
        }
        with urlopen("https://api.open-meteo.com/v1/forecast?" + urlencode(params),
                     timeout=REQUEST_TIMEOUT_SECONDS) as response:
            values = json.load(response)
        if len(chunk) == 1 and isinstance(values, dict):
            values = [values]
        if not isinstance(values, list) or len(values) != len(chunk):
            raise ValueError("Unexpected batch response length")
        result = {}
        for city, value in zip(chunk, values):
            if not isinstance(value, dict):
                result[city["id"]] = ValueError("Invalid city response")
                continue
            # Provider grid coordinates may differ slightly from city coordinates.
            if abs(value.get("latitude", 999) - city["latitude"]) > 1 or abs(value.get("longitude", 999) - city["longitude"]) > 1:
                result[city["id"]] = ValueError("Mismatched location")
            else:
                result[city["id"]] = value
        return result
    result = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                result.update(future.result())
            except (URLError, OSError, ValueError, TypeError) as error:
                result.update({c["id"]: error for c in chunk})
    return result

class WeatherService:
    def __init__(self, fetcher=fetch_current, clock=monotonic, now=utcnow, cities=CITIES, batch_fetcher=None):
        self.fetcher, self.clock, self.now = fetcher, clock, now
        self.cities, self.batch_fetcher = cities, batch_fetcher
        self.cache = {}
        self.next_attempt = {}
        self.errors = {}
        self.lock = Lock()

    def get_weather(self):
        # Serializes refreshes so simultaneous browsers cannot multiply requests.
        with self.lock:
            due = [c for c in self.cities if self.clock() >= self.next_attempt.get(c['id'], 0)]
            batch = self.batch_fetcher(due) if self.batch_fetcher and due else {}
            for city in self.cities:
                key = city["id"]
                if self.clock() < self.next_attempt.get(key, 0):
                    continue
                try:
                    raw = batch.get(key, ValueError('Missing batch result')) if self.batch_fetcher else self.fetcher(city)
                    if isinstance(raw, Exception):
                        raise raw
                    data = normalize(raw)
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
            for city in self.cities:
                key = city["id"]
                data = deepcopy(self.cache.get(key))
                if data is None:
                    data = {field: None for field in FIELDS}
                    data.update(effect="neutral", effect_reason="Погодные данные недоступны. Показана обычная надпись.", data_time=None, fetched_at=None,
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
