from copy import deepcopy
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

from backend.config import CITIES, CACHE_SECONDS, RETRY_SECONDS
from backend.weather_logic import FIELDS, normalize, select_effect
from backend.weather_api import WeatherService
from backend import main

NOW = datetime(2026, 10, 12, 10, tzinfo=timezone.utc)


def payload(**changes):
    current = dict(temperature_2m=12, precipitation=0, rain=0, showers=0, snowfall=0,
                   wind_speed_10m=10, wind_direction_10m=230, cloud_cover=10,
                   weather_code=0, is_day=1, time="2026-10-12T10:00", interval=900)
    current.update(changes)
    return {"utc_offset_seconds": 0, "current": current,
            "current_units": {**{v[0]: v[1] for v in FIELDS.values()}, "interval": "seconds"}}


@pytest.mark.parametrize("changes,effect", [
    ({}, "sun"), ({"snowfall": 0.1, "rain": 1, "wind_speed_10m": 40}, "snow"),
    ({"weather_code": 85}, "snow"), ({"rain": 0.1, "wind_speed_10m": 40}, "rain"),
    ({"weather_code": 61}, "rain"), ({"wind_speed_10m": 25}, "wind"),
    ({"wind_speed_10m": 17.9}, "sun"), ({"cloud_cover": 30}, "sun"),
    ({"cloud_cover": 60.1}, "cloudy"), ({"weather_code": 3, "cloud_cover": 100}, "cloudy"),
    ({"is_day": 0}, "neutral"), ({"is_day": None}, "neutral"),
    ({"weather_code": 45}, "neutral"), ({"precipitation": None}, "neutral"),
    ({"weather_code": None}, "neutral"), ({"precipitation": 1}, "neutral"),
])
def test_effects(changes, effect):
    assert normalize(payload(**changes))["effect"] == effect


def test_optional_values_and_units():
    data = payload(temperature_2m=float("nan"), wind_direction_10m=-1)
    data["current_units"]["wind_speed_10m"] = "mph"
    result = normalize(data)
    assert result["temperature_c"] is None
    assert result["wind_direction_deg"] is None
    assert result["wind_speed_kmh"] is None
    assert result["data_time"] == "2026-10-12T10:00:00Z"
    assert result["precipitation_interval_seconds"] == 900


@pytest.mark.parametrize("data", [{}, [], {"error": True}, payload(time=None), payload(interval=None), payload(time="bad")])
def test_invalid_payload(data):
    with pytest.raises(ValueError):
        normalize(data)


def test_cache_failure_recovery():
    ticks = [0]
    calls = []
    failed = [False]
    def fetch(city):
        calls.append(city["id"])
        if failed[0] and city["id"] == "dublin":
            raise URLError("offline")
        return payload()
    service = WeatherService(fetch, lambda: ticks[0], lambda: NOW)
    initial = service.get_weather()
    assert len(calls) == 4
    assert service.get_weather() == initial
    assert len(calls) == 4
    failed[0] = True
    ticks[0] = CACHE_SECONDS
    result = service.get_weather()
    assert result["cities"][0]["status"] == "stale"
    assert result["cities"][0]["data_time"] == initial["cities"][0]["data_time"]
    assert result["cities"][1]["status"] == "fresh"
    service.get_weather()
    assert len(calls) == 8
    ticks[0] += RETRY_SECONDS
    failed[0] = False
    assert service.get_weather()["status"] == "ok"
    assert len(calls) == 9


def test_no_data_throttle_and_api(monkeypatch):
    calls = []
    def fail(city):
        calls.append(city["id"])
        raise TimeoutError()
    service = WeatherService(fail, lambda: 0, lambda: NOW)
    monkeypatch.setattr(main, "weather_service", service)
    with TestClient(main.app) as client:
        response = client.get("/api/weather")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["status"] == "degraded"
        assert [c["id"] for c in data["cities"]] == [c["id"] for c in CITIES]
        assert all(c["effect"] == "neutral" and c["data_time"] is None and c["status"] == "unavailable" for c in data["cities"])
        client.get("/api/weather")
        assert len(calls) == 4
        assert client.get("/").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.get("/backend/config.py").status_code == 404


def test_stale_provider_timestamp():
    service = WeatherService(lambda city: payload(time="2026-10-12T08:00"), now=lambda: NOW)
    assert all(c["status"] == "stale" for c in service.get_weather()["cities"])


def test_future_timestamp_is_unavailable():
    service = WeatherService(lambda city: payload(time="2026-10-13T10:00"), now=lambda: NOW)
    assert all(c["status"] == "unavailable" for c in service.get_weather()["cities"])


def test_parallel_requests_share_cache():
    calls = []
    def fetch(city):
        calls.append(city["id"])
        return payload()
    service = WeatherService(fetch, now=lambda: NOW)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.get_weather(), range(4)))
    assert len(calls) == 4
    assert all(r["status"] == "ok" for r in results)


def test_returned_values_cannot_mutate_cache():
    service = WeatherService(lambda city: payload(), now=lambda: NOW)
    result = service.get_weather()
    result["cities"][0]["effect"] = "snow"
    assert service.get_weather()["cities"][0]["effect"] == "sun"

@pytest.mark.parametrize("changes,effect,fragment", [
    ({"weather_code":2,"cloud_cover":4}, "sun", "код погоды 2"),
    ({"weather_code":1,"cloud_cover":36}, "sun", "облачность 36% не выше 60%"),
    ({"rain":0.3,"wind_speed_10m":25.6}, "rain", "приоритет над ветром"),
    ({"snowfall":0.1,"rain":0.3}, "snow", "приоритет над дождём"),
    ({"wind_speed_10m":18}, "wind", "порога 5 м/с"),
    ({}, "sun", "осадки отсутствуют"),
    ({"is_day":0}, "neutral", "ночью"),
    ({"precipitation":None}, "neutral", "недостаточно"),
])
def test_effect_reason(changes, effect, fragment):
    result = normalize(payload(**changes))
    assert result["effect"] == effect
    assert fragment in result["effect_reason"]


def test_reason_survives_cache_failure():
    failed = [False]
    ticks = [0]
    def fetch(city):
        if failed[0]:
            raise TimeoutError()
        return payload(rain=0.3)
    service = WeatherService(fetch, lambda: ticks[0], lambda: NOW)
    initial = service.get_weather()["cities"][0]
    failed[0] = True
    ticks[0] = CACHE_SECONDS
    stale = service.get_weather()["cities"][0]
    assert stale["status"] == "stale"
    assert stale["effect_reason"] == initial["effect_reason"]

@pytest.mark.parametrize("changes,effect", [
    ({"weather_code":2,"cloud_cover":60,"wind_speed_10m":17.99}, "sun"),
    ({"weather_code":2,"cloud_cover":60.01}, "cloudy"),
    ({"wind_speed_10m":18}, "wind"),
    ({"wind_speed_10m":18,"rain":0.1}, "rain"),
    ({"weather_code":2,"cloud_cover":4,"is_day":0}, "neutral"),
    ({"weather_code":45,"cloud_cover":4}, "neutral"),
])
def test_updated_threshold_boundaries(changes, effect):
    assert normalize(payload(**changes))["effect"] == effect

@pytest.mark.parametrize("cloud,day,rain,wind,effect", [
    (39, 1, 0, 1.9, "sun"),
    (60, 1, 0, 1.9, "sun"),
    (60.1, 1, 0, 1.9, "cloudy"),
    (39, 0, 0, 1.9, "neutral"),
    (39, 1, 0.1, 1.9, "rain"),
    (39, 1, 0, 18, "wind"),
])
def test_madrid_cloud_code_does_not_override_cover(cloud, day, rain, wind, effect):
    result = normalize(payload(weather_code=3, cloud_cover=cloud, is_day=day,
                               rain=rain, precipitation=rain, wind_speed_10m=wind))
    assert result["effect"] == effect

@pytest.mark.parametrize("changes,effect", [
    ({"cloud_cover":61,"is_day":0}, "cloudy"),
    ({"cloud_cover":90,"rain":0.1}, "rain"),
    ({"cloud_cover":90,"snowfall":0.1}, "snow"),
    ({"cloud_cover":90,"wind_speed_10m":18}, "wind"),
    ({"cloud_cover":None}, "neutral"),
])
def test_cloudy_priority(changes, effect):
    assert normalize(payload(**changes))["effect"] == effect


@pytest.mark.parametrize('changes,effects', [
    ({'rain': .3, 'wind_speed_10m': 18}, ['rain', 'wind']),
    ({'snowfall': .2, 'wind_speed_10m': 40}, ['snow', 'wind']),
    ({'weather_code': 85, 'wind_speed_10m': 18}, ['snow', 'wind']),
    ({'cloud_cover': 90, 'wind_speed_10m': 18}, ['cloudy', 'wind']),
    ({'cloud_cover': 90, 'is_day': 0, 'wind_speed_10m': 18}, ['cloudy', 'wind']),
    ({'rain': .3, 'wind_speed_10m': 17.99}, ['rain']),
    ({'snowfall': .2, 'wind_speed_10m': None}, ['snow']),
    ({'cloud_cover': 90, 'wind_speed_10m': 17.99}, ['cloudy']),
    ({'cloud_cover': 60, 'wind_speed_10m': 18}, ['wind']),
    ({}, ['sun']),
])
def test_wind_can_combine_with_precipitation_and_clouds(changes, effects):
    result = normalize(payload(**changes))
    assert result['effects'] == effects
    # Existing consumers, including legacy, still receive the original primary effect.
    assert result['effect'] == select_effect(result)
