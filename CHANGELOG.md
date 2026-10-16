# Changelog

All notable changes. Dates are build dates; every result is **synthetic demand, uncalibrated**.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow the milestones
of `PROJECT.md` section 12.

## [0.1.0] - 2026-10-16: first runnable release (M9)

### Added
- **One-command demo:** `make demo` (setup, Jeddah network, demo runs, API and viewer on
  http://localhost:5173), `./run_app.sh` (serve `runs/`, `--detach`, `TT_API_PORT` /
  `TT_WEB_PORT`), `make city` (network variant, zones and the 10 % weekday 24 h baseline),
  `make test`, `make stop`, `make screenshots`.
- `python -m sim.demo` and `sim/config/demo.yaml`: the demo runs (Tier B smoke, demo events
  scenario, strategist, evacuation, a demo-scale policy comparison, a one-hour mid-day Tier A city
  smoke), skipped when already done, recorded in `runs/demo-manifest.json`.
- `sim/scenarios/demo_events.yaml` (fictional accident under heavy rain, motorcade, ambulance).
- `sim.runner --smoke --begin` (smoke runs at any time of day).
- `docker compose up --build` runs the same steps in a `demo` container before the `api` and `web`
  services; `.dockerignore`; osmium-tool in the image.
- Docs: `docs/architecture.md` (Mermaid), `docs/demo-script.md` (5-minute walkthrough),
  `CONTRIBUTING.md`, this changelog, README quickstart, release screenshots `docs/img/final-*.png`.

## [0.0.8] - 2026-10-16: integration of tracks A, B and C
- Merged M2-M8 into `main`; `sim.runner --scenario evac_*` dispatches to the evacuation runner;
  `--baseline --routing-threads --gzip`.
- API contract v1.1: reader-side normaliser for scenario/evacuation sub-runs, strategist
  recommendations and SQLite decisions, policy district effects, gzipped edge data, sparse bin cache.
- Merged assumptions register (256 ids); `pillow` as a direct dependency.

## [0.0.7] - 2026-10-16: M8 calibration path (dormant)
- Count and travel-time adapters, commercial-API stubs, `routeSampler.py` wrapper, GEH report.
  No real counts exist; synthetic round trip only.

## [0.0.6] - 2026-10-16: M7 evacuation
- Zone evacuation event with phased release, contraflow network edit, signal plans, clearance
  metrics (T50/T90/T100) and evacuation strategies ranked by the strategist.

## [0.0.5] - 2026-10-16: M6 emergency strategist
- Snapshot fork (`saveState`/`loadState`), candidates (k-shortest routes, preemption, rescue lane,
  closures), parallel what-ifs, ranking with side-effect penalties, plain-language explanations,
  action classification, hash-chained SQLite decision log, approve CLI and viewer panel.

## [0.0.4] - 2026-10-16: M5 focus windows and events
- Four default windows, service-road graft, Tier A to Tier B link with `cutRoutes.py`, Webster
  retiming of guessed signals, vType mix; accident, rain, flood, motorcade and emergency-trip
  events through TraCI with window KPIs.

## [0.0.3] - 2026-10-16: M4 policy lab
- Policy schema and transforms (remote work, staggered hours, day types, bus line, cordon pricing,
  network change, ride-hail share), incremental re-routing runner, matched controls, policy report
  with district effects and corridors, sweep tool.

## [0.0.2] - 2026-10-16: M2 population and baseline, M3 viewer
- Zones, synthetic population, activity chains, day types with prayer times, modes, trips,
  `duaIterate` assignment with a route cache, 24 h meso baseline at 10 %, meso-vs-micro fidelity
  test.
- File-backed FastAPI and the React + deck.gl + MapLibre viewer: edge-bin playback with a time
  slider, difference mode, district choropleth, Tier B trips, overlays, strategist panel, jobs.
- Lane audit from imagery: built, **blocked** on calibration accuracy (60 % held-out precision).

## [0.0.1] - 2026-10-15: M0 skeleton and M1 Jeddah network
- Repo, `uv`, Docker, CI, licence and NOTICE, demo window.
- `sim.network.build_city` from the Geofabrik GCC extract with the Jeddah polygon, reviewed OSM
  fix list, districts and buildings GeoJSON, meso smoke run (0.144 % teleports).
