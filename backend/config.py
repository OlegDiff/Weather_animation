"""Project settings; effect thresholds are visual design choices."""
CITIES = (
    {"id": "dublin", "name": "Dublin", "latitude": 53.3498, "longitude": -6.2603},
    {"id": "helsinki", "name": "Helsinki", "latitude": 60.1699, "longitude": 24.9384},
    {"id": "paris", "name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
    {"id": "madrid", "name": "Madrid", "latitude": 40.4168, "longitude": -3.7038},
)
CACHE_SECONDS = 600
RETRY_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 5
MAX_DATA_AGE_SECONDS = 3600
WIND_THRESHOLD_KMH = 18  # 5 m/s
SUN_MAX_CLOUD_PCT = 60

# The original four-city catalogue remains available at ?map=legacy.
import json
from pathlib import Path
_catalog_dir = Path(__file__).resolve().parent
_layout = json.loads((_catalog_dir / "map-layout.json").read_text(encoding="utf-8"))
_locations = json.loads((_catalog_dir / "map-geocoding.json").read_text(encoding="utf-8"))
EUROPE_CITIES = tuple(
    {"id": c["id"], "name": c["name"], "latitude": _locations[c["id"]]["latitude"],
     "longitude": _locations[c["id"]]["longitude"]}
    for c in _layout
)
