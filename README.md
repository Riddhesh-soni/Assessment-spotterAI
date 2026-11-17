# Weather-Aware Truck Routing

A full-stack web app that helps a truck driver choose the **safest route** based on
**weather, load weight, and travel time**. It generates alternative routes, samples
weather at timed checkpoints along each one, classifies risk using the assessment's
threshold + load rules, recommends the safest route, and visualizes everything on an
interactive map with a 0–48 hour weather heatmap.

Built with **React + TypeScript** (frontend) and **Django + Django REST Framework**
(backend).

---

## Table of contents

- [Project status](#project-status)
- [Feature checklist](#feature-checklist)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [How risk is calculated](#how-risk-is-calculated)
- [How a plan is built (request lifecycle)](#how-a-plan-is-built-request-lifecycle)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API contract](#api-contract)
- [Testing](#testing)
- [Deployment](#deployment)
- [Design decisions & assumptions](#design-decisions--assumptions)
- [Known limitations & roadmap](#known-limitations--roadmap)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)

---

## Project status

| Area | Status |
|------|--------|
| Backend (API, risk engine, providers, planner) | ✅ Complete, 55 tests passing |
| Frontend (form, map, routes, heatmap, slider) | ✅ Complete, type-checks & builds |
| Geocoding (Nominatim) | ✅ Verified against live API |
| Weather (Open-Meteo) | ✅ Verified against live API (units normalized) |
| Routing (OpenRouteService) | ✅ Verified against live API (Denver→SLC returns 3 distinct routes) |
| End-to-end live run | ✅ Verified — routes, checkpoints, ETAs, risk, recommendation, heatmap |
| GitHub repo / Hosting / Loom | ⬜ Deliverables still to do |

> **You must supply a free OpenRouteService API key** — routing is the only keyed
> provider. See [Configuration](#configuration). Everything else works without keys.

---

## Feature checklist

Mapped directly to the assessment requirements:

**User inputs**
- [x] Origin & destination
- [x] Departure date/time
- [x] Load weight

**The app**
- [x] Generates up to 3 route options via a routing API (`driving-hgv` profile)
- [x] Samples weather every **10 / 25 / 50 miles** (user-selectable)
- [x] Uses the truck's **estimated arrival time** at each checkpoint
- [x] Calculates weather risk using the threshold + load rules
- [x] Recommends the best route (fewest severe → high → lowest avg risk → fastest)
- [x] Shows all routes, checkpoints, risk levels, ETAs, and summaries on a map
- [x] Shows a weather heatmap along the corridor with a **0–48h forecast slider**

**Risk rules**
- [x] Wind / Rain / Snow thresholds (Low → No-Travel)
- [x] Load rules (≥55 mph; 45–54 + >30k lb; 35–44 + >40k lb)
- [x] Route recommendation priority ordering

---

## Architecture

The guiding principle is **separation of concerns** so the business logic is
isolated and testable, and the external vendors are swappable.

```
                      ┌──────────────────────────────────────────┐
  React (Vite + TS)   │  features/  trip-form · map · routes ·    │
                      │             heatmap                       │
                      │  api/ · hooks/ · lib/ · types/            │
                      └───────────────────┬──────────────────────┘
                                          │  POST /api/plan/
                      ┌───────────────────▼──────────────────────┐
  Django + DRF        │  routing.api      (HTTP boundary)         │  ← views, serializers
                      │  routing.services (planner + geometry)    │  ← orchestration
                      ├───────────────────────────────────────────┤
                      │  risk             (pure domain logic)     │  ← no IO, 100% unit-tested
                      ├───────────────────────────────────────────┤
                      │  providers        (geocoding / routing /  │  ← swappable vendor clients
                      │                    weather) behind        │     behind Protocol interfaces
                      │                    interfaces             │
                      └───────────────────────────────────────────┘
```

**Why this shape?**

- **`risk/` is pure** — no Django, no network, just data in and classification out.
  That makes the 40%-of-grade logic trivially and exhaustively testable (boundary
  values, load-rule interactions, route ranking).
- **`providers/` hide the vendors** behind `Protocol` interfaces. The planner depends
  on `GeocodingProvider` / `RoutingProvider` / `WeatherProvider`, never on
  OpenRouteService or Open-Meteo directly. Swapping a vendor is a one-line change in
  `providers/__init__.py`.
- **`services/planner.py` orchestrates** and is testable end-to-end with fake
  providers (no network) — see `apps/routing/tests/test_planner.py`.
- **Settings are split** (`base` / `dev` / `prod`); all secrets and tuning come from
  the environment.

---

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Django 5 + Django REST Framework | Batteries-included, clean validation/serialization |
| Routing | OpenRouteService (`driving-hgv`) | Truck profile; native alternatives for short trips + synthesized detours for long ones |
| Geocoding | Nominatim (OpenStreetMap) | Free, no key |
| Weather | Open-Meteo | Free, no key, hourly wind/rain/snow, multi-location batching |
| Frontend | React 18 + TypeScript + Vite | Fast, typed, maintainable |
| Map | Leaflet + react-leaflet | Lightweight, no token, canvas rendering for smoothness |
| Server state | TanStack Query | Clean async/mutation handling |
| Testing | pytest + pytest-django | Fast, offline, parametrized boundary tests |

---

## How risk is calculated

Each checkpoint is classified on **wind, rain, and snow**, and the checkpoint's level
is the **worst** of the three. Wind is additionally escalated by **load weight**.
See [`backend/apps/risk/rules.py`](backend/apps/risk/rules.py) and
[`engine.py`](backend/apps/risk/engine.py).

### Thresholds (from the spec)

| Condition | Low | Moderate | High | Severe | No Travel |
|-----------|-----|----------|------|--------|-----------|
| Wind (mph) | <25 | 25–34 | 35–44 | 45–54 | **≥55** |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | **>1.00** |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | **>3.0** |

**Boundary handling** (the spec is deliberately not uniform, so we honor it exactly):
every band's lower bound is inclusive (e.g. wind `25.0` → Moderate). The No-Travel
boundary is **inclusive for wind** (`≥55`) but **exclusive for rain/snow** (`>1.00`,
`>3.0`) — so rain of exactly `1.00 in/hr` stays Severe. These exact cases are covered
by tests.

### Load rules (escalate wind risk)

- `≥55 mph` → **No Travel** for any load
- `45–54 mph` + `>30,000 lb` → **No Travel**
- `35–44 mph` + `>40,000 lb` → **Severe**

Load rules only ever *raise* risk, never lower it.

### Route recommendation

Routes are ranked by (ascending = better):

1. Fewest **No-Travel** miles *(extension — an impassable route can't win)*
2. Fewest **Severe** miles
3. Fewest **High** miles
4. Lowest **average risk** (distance-weighted)
5. Shortest **travel time**

"Miles at a level" are **distance-weighted**: each checkpoint owns a trapezoidal
segment of road, so severe/high mileage reflects real road length, not raw checkpoint
counts.

---

## How a plan is built (request lifecycle)

`POST /api/plan/` →

1. **Validate** the request (DRF serializer).
2. **Geocode** origin + destination (Nominatim).
3. **Route**: fetch N route options (OpenRouteService, truck profile). ORS's native
   alternative-routes algorithm is capped at ~100 km, so for longer trips the app
   synthesizes distinct routes by re-routing through laterally-offset waypoints.
4. **Sample** checkpoints every 10/25/50 mi along each route (haversine + interpolation).
5. **ETA**: estimate arrival time at each checkpoint (uniform-speed model from the
   provider's total distance + duration).
6. **Weather**: batch-fetch hourly forecasts for every checkpoint in ~2 calls
   (Open-Meteo multi-location), then pick each checkpoint's arrival-hour sample.
7. **Classify** risk per checkpoint and **summarize + rank** the routes.
8. **Heatmap**: classify a corridor grid at every hour of the 0–48h horizon.
9. **Serialize** and return routes, checkpoints, summaries, recommendation, heatmap.

---

## Quick start

### Prerequisites
- Python 3.12+
- Node 18+
- A free OpenRouteService API key → https://openrouteservice.org/dev/#/signup

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# edit .env and paste your ORS_API_KEY

python manage.py migrate
python manage.py runserver        # http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`, so no CORS or env setup
is needed locally. Open http://localhost:5173 and plan a trip.

---

## Configuration

All backend config is environment-driven (see `backend/.env.example`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `ORS_API_KEY` | ✅ | OpenRouteService routing key |
| `SECRET_KEY` | prod | Django secret key |
| `DEBUG` | – | `True` locally, `False` in prod |
| `ALLOWED_HOSTS` | prod | Comma-separated hosts |
| `CORS_ALLOWED_ORIGINS` | ✅ (prod) | Frontend origin(s) |
| `GEOCODER_USER_AGENT` | – | Descriptive UA for Nominatim |
| `DEFAULT_SAMPLING_MILES` | – | Default checkpoint spacing (10/25/50) |
| `PROVIDER_HTTP_TIMEOUT` | – | Upstream HTTP timeout (seconds) |

Frontend (`frontend/.env.example`):

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Backend URL in production. Leave empty locally (uses the dev proxy). |

---

## API contract

### `POST /api/plan/`

**Request**
```json
{
  "origin": "Denver, CO",
  "destination": "Salt Lake City, UT",
  "departure": "2026-11-18T08:00:00Z",
  "load_lb": 42000,
  "interval_miles": 25,
  "alternatives": 3
}
```

| Field | Type | Notes |
|-------|------|-------|
| `origin`, `destination` | string | Free-text place/address |
| `departure` | ISO 8601 datetime | Trip start |
| `load_lb` | number ≥ 0 | Cargo weight |
| `interval_miles` | 10 \| 25 \| 50 | Optional, default 25 |
| `alternatives` | int 1–5 | Optional, default 3 |

**Response** (abridged)
```json
{
  "query": { "origin": {...}, "destination": {...}, "departure": "...", "load_lb": 42000 },
  "recommended_index": 0,
  "routes": [
    {
      "label": "Route A",
      "is_recommended": true,
      "geometry": [[39.7, -104.9], ...],
      "distance_miles": 525.1,
      "duration_seconds": 29160,
      "eta_arrival": "...",
      "summary": {
        "total_miles": 525.1,
        "average_risk": 0.42,
        "has_no_travel": false,
        "miles_by_level": { "low": 400, "moderate": 100, "high": 25, "severe": 0, "no_travel": 0 }
      },
      "checkpoints": [
        {
          "lat": 39.7, "lng": -104.9, "distance_miles": 0, "eta": "...",
          "weather": { "wind_mph": 12, "rain_in_per_hr": 0, "snow_in_per_hr": 0, "temperature_f": 41 },
          "risk": { "level": 0, "label": "Low", "drivers": ["wind"], "by_condition": {...} }
        }
      ]
    }
  ],
  "heatmap": {
    "times": ["..."],
    "bbox": { "min_lat": 38.9, "min_lng": -112.1, "max_lat": 40.8, "max_lng": -104.0 },
    "cells": [ { "lat": 38.9, "lng": -111.2, "risk_by_hour": [0,0,1,2,...] } ]
  },
  "risk_legend": [ { "level": 0, "label": "Low" }, ... ]
}
```

**Error shape**
```json
{ "error": { "code": "provider_misconfigured", "detail": "ORS_API_KEY is not set..." } }
```
Validation errors use DRF's field-error format. Status codes: `400` validation,
`422` geocoding failure, `502` upstream error, `503` misconfigured provider.

### `GET /api/health/`
Returns `{ "status": "ok" }`.

---

## Testing

```bash
cd backend
source .venv/bin/activate
pytest                 # 55 tests: risk engine, geometry, end-to-end planner (fake providers)
```

What's covered:
- **Risk thresholds** — every boundary value for wind/rain/snow.
- **Load rules** — all three escalation rules + "never lowers risk".
- **Checkpoint classification** — worst-condition selection, load drivers.
- **Route scoring & ranking** — distance-weighted miles, full priority ordering, No-Travel deprioritization.
- **Geometry** — haversine, cumulative distance, interpolation, sampling partitions the route, polyline simplification.
- **Planner** — a full plan with mocked providers (no network): routes, checkpoints, ETAs, recommendation, heatmap horizon.

```bash
cd frontend
npm run build          # type-checks (tsc) + production build
```

---

## Deployment

Both services deploy from the included **`render.yaml`** blueprint (Render.com), or any
PaaS:

- **Backend**: `backend/build.sh` installs deps, collects static (WhiteNoise), and
  migrates; `Procfile` runs gunicorn. Set `ORS_API_KEY`, `ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS`, `SECRET_KEY`.
- **Frontend**: `npm run build` → static `dist/`. Deploy to Render static, Vercel, or
  Netlify. Set `VITE_API_BASE_URL` to the backend URL.

**One-time deploy order:** deploy backend → note its URL → set the frontend's
`VITE_API_BASE_URL` and the backend's `CORS_ALLOWED_ORIGINS` to each other → redeploy.

---

## Design decisions & assumptions

- **ETA model.** Checkpoint ETAs assume uniform speed over the route
  (`provider duration × distance-fraction`). The routing API gives total distance +
  duration; we scale by distance traveled. Simple, defensible, and uses the provider's
  own time estimate.
- **Weather batching.** All checkpoints across all routes are fetched in chunked
  multi-location Open-Meteo calls (≈2 weather calls per plan instead of hundreds),
  keeping it fast and within rate limits.
- **Unit safety.** The weather client reads the API's reported units and normalizes
  wind→mph, rain/snow→in/hr itself (Open-Meteo reports mph as `"mp/h"`, for instance),
  so the thresholds stay correct regardless of upstream defaults.
- **No-Travel routes are deprioritized** below all passable routes (a strict,
  documented extension of the spec's ranking).
- **Stateless.** No persistence is required by the spec; the app computes plans on
  demand. SQLite is configured only to satisfy Django/DRF defaults.
- **Map performance.** Route polylines are down-sampled to ≤400 points and the map
  renders on canvas for smooth pan/zoom with many markers + heatmap cells.

---

## Known limitations & roadmap

- **Route options.** ORS's native alternative-routes algorithm is limited to ~100 km
  on the public API, so for longer trips the app synthesizes alternatives via
  offset waypoints. The number of *genuinely distinct* routes depends on the road
  network — some corridors only support 2 sensible truck routes — so you may see
  2–3 routes. The UI handles 1–N gracefully, and near-duplicates are filtered out.
- **Heatmap is a bounding-box grid**, not a tight route-hugging corridor buffer. It
  covers a rectangular area (with margin) around all routes — a performant, reasonable
  interpretation of "along the trip corridor." A true buffered corridor is a possible
  refinement.
- **Forecast horizon.** Open-Meteo provides near-term forecasts; departures far in the
  future will have less reliable weather. The 0–48h heatmap is anchored at departure.
- **Latency.** A plan makes several upstream calls (geocode ×2, routing ×N, weather
  ×~2), so a long trip takes a few seconds. Response caching is a natural future
  optimization (intentionally out of scope — correctness over features).

Possible enhancements (explicitly out of scope — the spec says prioritize correctness
over extra features): response caching, request rate-limiting, per-segment ORS
durations for non-uniform ETAs, true corridor buffering, and persisted trip history.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `503 provider_misconfigured: ORS_API_KEY is not set` | Add your ORS key to `backend/.env` and restart the server. |
| `422 geocoding_failed` | Origin/destination couldn't be resolved — try a more specific place name. |
| `502 upstream_error` | An external API failed/timed out — retry; check connectivity. |
| Frontend can't reach the API | Ensure the Django server is running on :8000 (dev proxy) or set `VITE_API_BASE_URL` in prod. |
| CORS error in prod | Add the frontend origin to `CORS_ALLOWED_ORIGINS` on the backend. |
| Map tiles not loading | Network/adblock blocking OpenStreetMap tiles. |

---

## Project layout

```
.
├── README.md                 # this file
├── render.yaml               # one-blueprint deploy for both services
├── .gitignore
├── backend/
│   ├── config/               # settings (base/dev/prod), urls, wsgi/asgi
│   ├── apps/
│   │   ├── providers/        # vendor clients behind Protocol interfaces + factory
│   │   │   ├── base.py       #   interfaces, data contracts, HTTP helper
│   │   │   ├── geocoding.py  #   Nominatim
│   │   │   ├── routing.py    #   OpenRouteService
│   │   │   └── weather.py    #   Open-Meteo (batched, unit-normalized)
│   │   ├── risk/             # PURE domain logic (no IO)
│   │   │   ├── models.py     #   RiskLevel, dataclasses
│   │   │   ├── rules.py      #   thresholds + load rules
│   │   │   ├── engine.py     #   classify / summarize / rank
│   │   │   └── tests/        #   boundary + scoring tests
│   │   └── routing/
│   │       ├── api/          # DRF views, serializers, exception handler, urls
│   │       ├── services/     # geometry (sampling) + planner (orchestration)
│   │       └── tests/        # geometry + end-to-end planner tests
│   ├── requirements*.txt, Procfile, build.sh, .env.example, pytest.ini
├── frontend/
│   ├── src/
│   │   ├── api/              # typed fetch client + plan endpoint
│   │   ├── types/            # TS contract mirroring the API
│   │   ├── hooks/            # usePlanTrip (TanStack Query)
│   │   ├── lib/              # risk colors/labels/formatters
│   │   ├── features/         # trip-form · map · routes · heatmap
│   │   └── components/       # shared (risk legend)
│   ├── index.html, vite.config.ts, tsconfig*.json, .env.example
└── fs-assessment-spotter.pdf # original assessment brief
```

---

Built for the Spotter Full Stack Developer assessment.
