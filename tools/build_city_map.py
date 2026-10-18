"""Rebuild browser catalogue from the reviewed layout and stored geocoding."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    layout = json.loads((ROOT / "backend/map-layout.json").read_text(encoding="utf-8"))
    locations = json.loads((ROOT / "backend/map-geocoding.json").read_text(encoding="utf-8"))
    cities = []
    for city in layout:
        point = locations[city["id"]]
        if point["country_code"] != city["country"]:
            raise ValueError("Country mismatch: " + city["id"])
        cities.append({**city, "latitude": point["latitude"], "longitude": point["longitude"], "geonames_id": point["id"]})
    payload = dict(width=1600, height=900, source_width=1672, source_height=941, cities=cities)
    (ROOT / "frontend/map-cities.js").write_text(
        "window.WEATHER_MAP = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
