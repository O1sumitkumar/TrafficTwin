# TrafficTwin Jeddah — status
Last updated: 2026-10-15
Environment: macOS (Apple M3 Pro, 11 cores, 18 GB RAM); Python 3.12.13 (uv-managed venv, uv 0.11.13);
Eclipse SUMO 1.28.0 from the PyPI `eclipse-sumo` wheel (works on macOS arm64; brew not needed),
SUMO_HOME = `.venv/lib/python3.12/site-packages/sumo`; osmium-tool 1.19.1 (brew); node 25, Vite 7,
MapLibre GL 5, TypeScript 5.

All results: **synthetic demand, uncalibrated**.

## Milestones
| M | Title | State | Evidence |
|---|---|---|---|
| M0 | Skeleton | done | verifier 2026-10-15: all items PASS after STATUS fix; 26 tests in 8.6 s |
| M1 | Jeddah network | in progress | |

## Measured
- M0: pytest 26 tests, 8.6 s wall (demo window only, offline). Demo window: 939 edges, 401 junctions,
  1 traffic light, 114.36 lane-km. Tier B demo smoke (micro, seed 1, 1 h, 1,800 trips): 0.76 s,
  1 teleport (0.056 %). Same seed twice: identical population_hash and results (verifier, seed 3).

## Decisions
- D-001 SUMO install path: `uv` + `eclipse-sumo` 1.28.0 wheel (macOS arm64 wheel installs and runs;
  sumolib and traci 1.28.0 from PyPI). `sim/common.py` sets SUMO_HOME from the wheel.
- D-002 Python 3.12 pinned (`.python-version`, `requires-python >=3.12,<3.13`).
- D-003 OSM extract: Geofabrik has no Saudi-only file; `asia/gcc-states-latest.osm.pbf` is used
  (243 MB, replication timestamp 2026-10-14T20:21:12Z, downloaded 2026-10-15).
- D-004 Jeddah polygon `data/osm/jeddah.poly`: lon 39.02-39.33, lat 21.30-21.90, tapered in the
  north-east and cut at lon 39.33 in the east so the Makkah highway beyond the city is excluded.
  Sea inside the box carries no roads. Rough; refine when an official boundary is available.
- D-005 Demo window = western Tahlia Street + Al Andalus, bbox lon 39.148-39.166, lat 21.542-21.558
  (3.3 km2), placed after locating Tahlia Street (OSM way 38500585) in the data.
- D-006 The city network was built before the demo window was committed, so the M0 demo window
  was produced directly by the M1 pipeline (`build_window --name demo`), as the brief asks for M1.
- D-007 Windows are cut from the city `.net.xml` (not rebuilt from OSM) so edge ids match Tier A
  exactly (required by cutRoutes in M5). Consequence: windows do not contain service roads.
  Revisit in M5 (option: a window-specific OSM rebuild plus an id-mapping step).
- D-008 netconvert reads gzip OSM XML directly; the city clip is stored as `jeddah.osm.gz`.
- D-009 Tool commands run from the repo root with repo-relative paths so SUMO headers in committed
  outputs do not contain local paths; run hashes (`population_hash`) ignore XML comments.
- D-011 Commit order: the M0 commit already contains the M1 builder code (written in the same
  session); M1 is declared done only in its own commit after its verifier run.
- D-012 `run_claude.sh` (local launcher) is gitignored; `PROMPT.md` is committed as the session brief.
- D-010 Local npm is configured with `omit=dev`; use `npm install --include=dev` in `web/`.

## Open issues
- Disk: about 18 GB free on this Mac; the city net is 341 MB (plus a 341 MB raw copy).

## Handoffs

## M0 Skeleton — 2026-10-15
Built: git repo on `main`; section 8 layout (packages with `__init__.py`, placeholder READMEs for
population, daytypes, policies, vtypes, scenarios, events, strategist, api); `pyproject.toml` +
`uv.lock` (Python 3.12, eclipse-sumo 1.28.0, sumolib/traci, geo and API stack, ruff, pytest);
LICENSE (Apache-2.0), NOTICE (OSM ODbL, SUMO EPL-2.0, GASTAT); `.gitignore`; docker-compose (api
stub with `/health` + Vite web); GitHub Actions CI (ruff check/format, pytest, web typecheck);
docs/STATUS.md, docs/assumptions.md, docs/data-sources.md; demo window in `data/demo/`
(Tahlia / Al Andalus, 3.3 km2, 1,800 random trips) plus its raw OSM for the builder test.
Measured: 26 tests pass in 8.6 s; demo 939 edges / 401 junctions / 1 TLS / 114.36 lane-km; Tier B
demo smoke 0.76 s for 1 h, 0.056 % teleports; determinism confirmed by the verifier.
Decisions: D-001 to D-012 above (SUMO from the wheel, Python 3.12, GCC extract, polygon, demo bbox,
windows cut from the city net).
Could not verify: that the Docker images build and that the eclipse-sumo wheel's shared libraries
load inside python:3.12-slim (not built in this session); CI not yet run on GitHub (no remote).
Next: M1 Jeddah network — city build, fix list with a real fix, window cutter, meso smoke run.
