"""Serve the Weather_animation demo through FastAPI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Weather_animation")

# Register future API routes above this mount; only frontend files are public.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
