# TrafficTwin Jeddah

Open-source traffic digital twin of Jeddah: a city-wide mesoscopic model (Tier A) for policy
questions and microscopic focus windows (Tier B) for events and emergency decision support, built
on Eclipse SUMO and OpenStreetMap. See `PROJECT.md` for the brief and `docs/STATUS.md` for what is
built and measured.

> All results use **synthetic demand, uncalibrated**. Simulation and decision support only.

## Setup (macOS arm64 or Linux)

```bash
uv python install 3.12
uv sync                         # Python 3.12 venv; SUMO 1.28 comes from the eclipse-sumo wheel
brew install osmium-tool        # Linux: apt install osmium-tool
```
SUMO binaries and tools are found through the `eclipse-sumo` wheel; `SUMO_HOME` is set
automatically by `sim/common.py` (or honoured if already set).

## Tests (demo window only, offline, about 3 min)

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

## Build the Jeddah city network (M1)

```bash
# downloads the Geofabrik GCC extract (243 MB) on first run, clips it to data/osm/jeddah.poly,
# runs netconvert, applies data/osm/fixes/*.yaml and writes the GeoJSON side outputs (~1 min)
uv run python -m sim.network.build_city

# re-cut the committed demo window from the city network (same pipeline as Tier A)
uv run python -m sim.network.build_window --name demo --osm-extract
```
Outputs (gitignored): `data/jeddah/jeddah.net.xml`, `data/jeddah/districts.geojson`,
`data/jeddah/buildings.geojson`, `data/jeddah/jeddah.build.json` (provenance and network size),
`web/public/data/*.geojson` (viewer).

Inspect the fix list against a built network:
```bash
uv run python -m sim.network.fixes check --net data/jeddah/jeddah.net.xml
```

## Smoke runs

```bash
# Tier A: whole city, mesoscopic, one hour of random trips (run it in the background; ~9 min,
# most of it routing): prints edges, junctions, traffic lights, lane-km, vehicles, runtime,
# real-time factor and teleport share (must be < 0.5 %)
mkdir -p logs && nohup uv run python -m sim.runner --smoke --tier A --seed 1 > logs/smoke-A.log 2>&1 &
tail -f logs/smoke-A.log

# Tier B: demo window, microscopic (seconds)
uv run python -m sim.runner --smoke --tier B --seed 1
```
Each run writes `runs/<run_id>/` with `meta.json` (seed, config hash, network hash, population
hash, SUMO version, results), `stats.xml`, `tripinfo.xml`, `edgedata.xml` and `sumo.log`.

## Population and 24 h city baseline (M2)

```bash
# synthetic population (10 % sample), weekday activity chains, duaIterate assignment (cached by
# network/population/day type/seed), final 24 h meso run, KPIs and plots (~2 h uncached, ~15 min cached)
nohup uv run python -m sim.runner --baseline --daytype weekday --sample 0.10 --seed 1 --gzip > logs/baseline.log 2>&1 &
uv run python -m sim.fidelity --window demo --seed 1   # meso vs micro on a window (PROJECT.md 9.4)
```
`--routing-threads 8` speeds up assignment but makes routes reproducible from the cache only
(TA-013/TA-015). Method and measured numbers: `docs/population.md`, `docs/fidelity.md`.

## Policy lab (M4)

```bash
uv run python -m sim.runner --policy remote_work_30 --daytype weekday --sample 0.10 --seed 1
uv run python -m sim.policies.sweep --policy remote_work --param share=0.1:0.5:0.1 --sample 0.10
uv run python -m sim.validate sim/policies/*.yaml
```
Each policy run writes `runs/<policy>/policy_report.{json,md}` against the matching baseline.
Results, matched controls and noise checks: `docs/policies.md`.

## Viewer and API (M3)

```bash
uv run uvicorn api.main:app --port 8000                              # file-backed API over runs/
cd web && npm install --include=dev && npm run dev                   # http://localhost:5173
```
`docker compose up --build` starts both (API on 8000, viewer on 5173). Data contract:
`docs/contracts/run-outputs.md`; viewer guide: `docs/viewer.md`.

## Layout

`sim/` simulation (network, population, day types, policies, events, runner), `strategist/`
decision logic, `api/` + `web/` presentation, `docs/` status, assumptions and data sources,
`tests/` demo-window tests.

## Licence

Code: Apache-2.0 (`LICENSE`). Data derived from OpenStreetMap is (c) OpenStreetMap contributors,
ODbL; SUMO is EPL-2.0 (dependency, not vendored); GASTAT open data with attribution. See `NOTICE`.

## Focus windows and events (M5)

```bash
# Tahlia window with service roads, Tier A exit times, cut routes + Webster signals, flow check
uv run python -m sim.link window --name tahlia
uv run python -m sim.link tier-a --routes runs/source-smoke-A/routes.rou.xml --seed 1
uv run python -m sim.link cut --window tahlia --tier-a runs/tierA-exit-<hash>/
uv run python -m sim.link check --window tahlia --tier-a runs/tierA-exit-<hash>/ --seed 1
# a scenario against the window baseline (same seed): runs/<id>/scenario_report.{json,md}
uv run python -m sim.runner --scenario accident_tahlia --window tahlia --seed 1
```
Create the source route set first: `uv run python -m sim.runner --smoke --tier A --seed 1`, then
`mkdir -p runs/source-smoke-A && cp runs/smoke-A-s1-*/routes.rou.xml runs/source-smoke-A/`. Demo
scenarios: `sim/scenarios/{accident,rain,flood,motorcade,emergency}_tahlia.yaml` (fictional).
Results and caveats: `docs/events.md`.

## Emergency strategist (M6)

```bash
uv run python -m strategist.run --scenario emergency_tahlia_0830 --window tahlia --seed 1
uv run python -m strategist.approve <recommendation_id> [--option 1] [--actor name] [--reject]
uv run python -m strategist.log verify      # hash-chained, append-only decision log
```
Pipeline, actions and measured runs: `docs/strategist.md`.

## Evacuation (M7)

```bash
uv run python -m sim.runner --scenario evac_demo --seed 1             # demo window, ~15 s
uv run python -m sim.runner --scenario evac_corniche_hamra --seed 1   # Al Hamra (tahlia window)
uv run python -m strategist.evacuation run --scenario evac_corniche_hamra --seed 1
```
`sim.runner --scenario evac_*` dispatches to `sim.events.evacuation run`. Method and results:
`docs/evacuation.md`.

## Calibration (M8, dormant until counts exist)

```bash
uv run python -m sim.adapters.synthetic --net data/demo/demo.net.xml --out runs/synthetic-demo --seed 1
uv run python -m sim.calibrate --counts runs/synthetic-demo/counts.csv --net data/demo/demo.net.xml \
  --routes runs/synthetic-demo/candidates.rou.xml --sample 1.0 \
  --travel-times runs/synthetic-demo/traveltimes.csv --counts-source synthetic --before
```
Synthetic counts only exercise the pipeline. See `docs/calibration.md`.

## Lane audit from imagery (blocked)

`sim/network/lane_audit.py` is built but its calibration precision is below the gate, so no
imagery-derived lanes are applied and `data/jeddah/jeddah.net.xml` stays the default network.
See `docs/lane-audit.md`.
