import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from io import BytesIO

from backend.config import EUROPE_CITIES, CITIES
from backend.weather_api import WeatherService, fetch_many
from backend import main
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_map_catalog_is_complete_and_matches_frontend():
    layout = json.loads((ROOT / "backend/map-layout.json").read_text(encoding="utf-8"))
    script = (ROOT / "frontend/map-cities.js").read_text(encoding="utf-8")
    frontend = json.loads(script.removeprefix("window.WEATHER_MAP = ").strip().removesuffix(";"))
    assert len(EUROPE_CITIES) == len(layout) == 175
    assert len({c["id"] for c in layout}) == len(layout)
    assert {c["id"] for c in EUROPE_CITIES} == {c["id"] for c in frontend["cities"]}
    for city in frontend["cities"]:
        assert 0 <= city["x"] < city["x"]+city["w"] <= 1672
        assert 0 <= city["y"] < city["y"]+city["h"] <= 941
        backend = next(c for c in EUROPE_CITIES if c["id"] == city["id"])
        assert backend["latitude"] == city["latitude"]
        assert backend["longitude"] == city["longitude"]
    assert frontend["width"]/frontend["height"] == 16/9


def test_ambiguous_places_are_correct_cities():
    by_id = {c["id"]:c for c in EUROPE_CITIES}
    assert 52 < by_id["gomel-by"]["latitude"] < 53
    assert -6 < by_id["salamanca-es"]["longitude"] < -5
    assert "helsinki" not in by_id
    assert by_id["paris-fr"]["name"] == "Paris"


def test_batch_transport_maps_responses_and_limits_requests():
    calls=[]
    from urllib.parse import urlparse, parse_qs
    def fake_open(url, timeout):
        query=parse_qs(urlparse(url).query)
        lat=[float(v) for v in query["latitude"][0].split(",")]
        lon=[float(v) for v in query["longitude"][0].split(",")]
        calls.append(len(lat))
        return BytesIO(json.dumps([{"latitude":a,"longitude":b} for a,b in zip(lat,lon)]).encode())
    with patch("backend.weather_api.urlopen", fake_open):
        result=fetch_many(list(EUROPE_CITIES))
    assert len(calls)==5
    assert max(calls)<=40
    assert len(result)==175
    assert not any(isinstance(v,Exception) for v in result.values())


def test_partial_batch_failure_keeps_other_results():
    from urllib.parse import urlparse, parse_qs
    def fake_open(url,timeout):
        query=parse_qs(urlparse(url).query)
        lat=[float(v) for v in query["latitude"][0].split(",")]
        lon=[float(v) for v in query["longitude"][0].split(",")]
        if lat[0]==EUROPE_CITIES[0]["latitude"]:
            raise TimeoutError()
        return BytesIO(json.dumps([{"latitude":a,"longitude":b} for a,b in zip(lat,lon)]).encode())
    with patch("backend.weather_api.urlopen", fake_open):
        result=fetch_many(list(EUROPE_CITIES))
    assert sum(isinstance(v,Exception) for v in result.values())==40
    assert len(result)==175


def test_europe_endpoint_no_synthetic_fallback(monkeypatch):
    calls=[]
    def offline(cities):
        calls.append(len(cities))
        return {c["id"]:TimeoutError() for c in cities}
    service=WeatherService(cities=EUROPE_CITIES,batch_fetcher=offline)
    monkeypatch.setattr(main,"weather_service",service)
    with TestClient(main.app) as client:
        data=client.get("/api/weather?map=europe").json()
        assert len(data["cities"])==175
        assert all(c["effect"]=="neutral" and c["status"]=="unavailable" for c in data["cities"])
        client.get("/api/weather?map=europe")
        assert calls==[175]
        assert client.get("/?mode=demo").status_code==200
        assert client.get("/legacy/").status_code==200
        assert client.get("/map-cities.js").status_code==200
