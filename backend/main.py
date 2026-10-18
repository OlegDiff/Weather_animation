"""Serve the Weather_animation demo and weather API."""
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from backend.weather_api import WeatherService, fetch_many
from backend.config import EUROPE_CITIES

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app = FastAPI(title="Weather_animation")
weather_service = WeatherService(cities=EUROPE_CITIES, batch_fetcher=fetch_many)
legacy_weather_service = WeatherService()


@app.get("/api/weather")
def get_weather(response: Response, map: str = 'europe'):
    """Current model weather; check each city's status before using it."""
    response.headers["Cache-Control"] = "no-store"
    return (legacy_weather_service if map == 'legacy' else weather_service).get_weather()


# API routes must precede the root static mount.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
