"""Build the Pages artifact with real weather using only the Python standard library."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import CITIES, EUROPE_CITIES, MAX_DATA_AGE_SECONDS
from backend.weather_api import WeatherService, fetch_many

ASSETS = (
    "index.html", "style.css", "app.js", "map-cities.js",
    "legacy/index.html", "legacy/style.css", "legacy/app.js",
)
# Helsinki is absent from the approved Europe composition; fetch it only for legacy.
PAGES_CITIES = EUROPE_CITIES + tuple(
    c for c in CITIES if c['name'] not in {city['name'] for city in EUROPE_CITIES}
)


def build_site(output, batch_fetcher=fetch_many):
    """Reject failed/partial refreshes before touching any previously built files."""
    payload = WeatherService(cities=PAGES_CITIES, batch_fetcher=batch_fetcher).get_weather()
    if payload["status"] != "ok" or len(payload["cities"]) != len(PAGES_CITIES):
        raise ValueError("Incomplete or stale weather: keeping the previous site unchanged")
    payload["refresh_interval_seconds"] = 3600
    payload["retry_interval_seconds"] = 60
    # Use a fixed allowlist: no source code, local settings, archives or secrets.
    files = {}
    for name in ASSETS:
        source = ROOT / "frontend" / name
        if source.is_symlink():
            raise ValueError(f"Symlink asset is not allowed: {name}")
        content = source.read_bytes()
        if name.endswith("index.html"):
            url = "../data/weather.json" if name.startswith("legacy/") else "data/weather.json"
            config = (f'id="weather-map" data-weather-url="{url}" '
                      f'data-max-age-seconds="{MAX_DATA_AGE_SECONDS}"')
            content = content.decode("utf-8").replace('id="weather-map"', config).encode("utf-8")
        files[name] = content
    files["data/weather.json"] = (json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    files[".nojekyll"] = b""
    output = Path(output)
    if output.is_symlink():
        raise ValueError("Symlink output is not allowed")
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.relative_to(output).as_posix() not in files):
                raise ValueError(f"Unexpected output entry: {path}")
    for name, content in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if name == "data/weather.json":
            temporary = destination.with_suffix(".tmp")
            temporary.write_bytes(content)
            temporary.replace(destination)
        else:
            destination.write_bytes(content)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    try:
        payload = build_site(args.output)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"Pages build failed: {error}\n")
    print(f"Built {len(payload['cities'])} cities at {payload['generated_at']} in {args.output}")


if __name__ == "__main__":
    main()
