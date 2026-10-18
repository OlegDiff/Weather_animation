# AGENTS.md — Weather_animation

Instructions for AI coding agents working in this repository. Read `README.md` and inspect the existing files before proposing or making changes. If the README describes a planned file that does not yet exist, do not assume it is implemented.

## Current scope (user-approved, 2026-10-18)

The main map follows Europe Typographic City Map.png: 175 readable cities, 1600x900 (16:9), demo with snow and live weather. Preserve the four-city implementation at frontend/legacy/. See docs/europe-map.md for catalogue provenance and unresolved labels. The legacy preservation rules below apply to that snapshot; the main map uses the approved expanded layout and scaled effects.

## Project goal

Weather_animation is a learning project: animate the **letters of city names** according to weather conditions in Dublin, Helsinki, Paris, and Madrid. A working prototype with four effects (`rain`, `snow`, `wind`, `sun`) and a looping synthetic weather scenario already exists outside or inside the repository. **Preserving that prototype is the top priority** during migration and integration.

## Technology and boundaries

- Frontend: plain HTML, CSS, JavaScript. Retain the existing animation/rendering approach (including Canvas if used).
- Backend: Python + FastAPI.
- Weather provider: initially Open-Meteo; communicate over HTTP and JSON.
- Version control: Git + GitHub.
- Tests: pytest for backend logic; use a lightweight, appropriate strategy for frontend checks.
- Start with one repository and one backend process, which may also serve frontend static files.
- Do **not** introduce React, TypeScript, Node build tools, Docker, databases, Airflow, n8n, Redis, or other infrastructure without explaining a concrete need and obtaining approval.

## Planned structure (not a statement of what exists)

```text
Weather_animation/
  backend/
    main.py             # FastAPI routes and static serving
    weather_api.py      # external weather requests
    weather_logic.py    # normalize weather and select effect
    config.py           # cities, coordinates, refresh settings
  frontend/
    index.html
    style.css
    app.js              # fetch API data, update city states
    weather-effects.js  # existing effect algorithms
  tests/
  requirements.txt
  README.md
  AGENTS.md
  .gitignore
  .env.example          # only if environment settings are needed
```

Do not create unused placeholders merely to match this tree. Adopt the structure incrementally, preserving a runnable state.

## Rules for making changes

1. **Inspect before editing.** Identify the actual entry point, dependencies, renderer, city layout, and current working behavior.
2. **Plan briefly.** Before substantial changes, explain what files will change, why, and how success will be checked. Work in small, reviewable steps.
3. **Protect existing animation behavior.** Do not redesign the layout or change city positions, colors, timing, or the four effects unless requested. Do not replace a working animation with a simplified mock.
4. **Keep responsibilities separate.** Python fetches and normalizes weather; frontend renders effects. The browser should call our backend, not require an external weather API key.
5. **Preserve the synthetic demo.** Add a configurable demo/live mode so the effects can be tested without network access. Do not invent live weather values or label synthetic data as real.
6. **Make provider-specific details local.** Keep external response mapping in `weather_api.py` / `weather_logic.py`, with a stable internal API contract for the frontend. Handle missing values, timeouts, and upstream failures.
7. **Avoid excessive requests.** Refresh upstream data on a reasonable interval (initially around 10–15 minutes), use a simple in-memory cache when needed, and expose the observation/update timestamp. Do not call weather services on every animation frame.
8. **Use clear code.** Prefer small functions, meaningful names, comments for non-obvious choices, and limited dependencies. Avoid premature abstractions.
9. **Secure configuration.** Never commit secrets, tokens, `.env` values, virtual environments, caches, or generated bulky artifacts. Maintain `.gitignore`; use `.env.example` only for safe examples.
10. **Explain as you work.** This is a learning project. Describe new commands, files, key concepts, and trade-offs concisely in Russian; preserve established English code identifiers.
11. **Limit scope.** Change only what the task requires; call out unrelated issues instead of fixing them silently.
12. **Git safety.** Never run destructive Git commands, create commits, push to GitHub, merge, or rewrite history without explicit user permission. Show intended changes first.

## Weather-to-effect contract

- Internal effect names: `rain`, `snow`, `wind`, `sun`, `cloudy`, `neutral`.
- A single primary effect is selected per city at first; `neutral` means no active animation, not an active weather animation. The user-approved cloudy effect uses grey letters with moving dark grey clouds above 60% cloud cover; snow, rain and wind take precedence. Preserve the original four-effect demo sequence.
- Prefer snow over rain when snow is actually occurring; do not classify overcast conditions as sunny simply because there is no rain or wind.
- Support intensity/direction parameters where available (e.g., precipitation, wind speed/direction, cloud cover), but keep the frontend resilient to missing optional fields.
- Document and test the precise weather classification thresholds when implemented; do not silently invent scientifically justified thresholds.
- Keep `city`, `effect`, weather metrics, units, and data timestamp unambiguous in JSON. Agree on the final schema when implementing the endpoint.

## Validation and completion

After changes, where applicable:

- Run the application locally and verify that the browser renders all four city labels at the intended positions.
- Verify that demo mode still plays the original looping synthetic sequence.
- Exercise all four effects and confirm they act on letters, not merely background icons.
- Test backend mapping and edge cases: missing weather data, API failure, stale cache, and precedence of simultaneous weather conditions.
- Run relevant tests and report the exact commands and outcomes. If execution is unavailable, state what was not verified; never claim tests passed without running them.
- Update `README.md` whenever installation, execution, architecture, API behavior, or project status changes.

## Preferred response format for coding tasks

1. Short summary of the approach (for nontrivial changes).
2. Implemented changes with file names.
3. How to run and verify locally (copyable commands).
4. Tests performed and remaining limitations.

**First implementation milestone:** import the existing animation into this repository, preserve the synthetic four-city loop, establish a reproducible local run, and only then connect live weather.
