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
| M1 | Jeddah network | done | smoke-A-s1-5b8a19d3-ab76d081: 0.144 % teleports; docs/network-qa.md; docs/img/m1-viewer.png |

## Measured
- M0: pytest 26 tests, 8.6 s wall (demo window only, offline). Demo window: 939 edges, 401 junctions,
  1 traffic light, 114.36 lane-km. Tier B demo smoke (micro, seed 1, 1 h, 1,800 trips): 0.76 s,
  1 teleport (0.056 %). Same seed twice: identical population_hash and results (verifier, seed 3).
- M1 city network (`data/jeddah/jeddah.net.xml`, OSM 2026-10-14, 3 fixes): 156,126 edges, 62,513
  junctions, 72 traffic lights, 171,590 lanes, 20,952.88 lane-km, 18,010.64 edge-km; 353 MB net
  XML; build 56 s (netconvert + fixes + side outputs). Main strongly connected component 99.10 % of
  passenger edges. Districts: 112 polygons (OSM admin_level 10). Buildings: 27,783 footprints, 9.7 MB.
- M1 Tier A smoke (meso, seed 1, 0-3600 s, 18,001 random trips, period 0.2 s): inserted 17,994,
  completed 10,825, running at end 7,169; SUMO wall 24.1 s (real-time factor 149; SUMO's own
  performance figure 306); demand generation (randomTrips + duarouter, 5 routing threads) 500 s;
  teleports 26 (all jam) = 0.144 %; mean route length 24.8 km. Peak RSS of the meso run 2.87 GB
  (measured on the pre-extension network, same demand size).

## Decisions
- D-001 SUMO install path: `uv` + `eclipse-sumo` 1.28.0 wheel (macOS arm64 wheel installs and runs;
  sumolib and traci 1.28.0 from PyPI). `sim/common.py` sets SUMO_HOME from the wheel.
- D-002 Python 3.12 pinned (`.python-version`, `requires-python >=3.12,<3.13`).
- D-003 OSM extract: Geofabrik has no Saudi-only file; `asia/gcc-states-latest.osm.pbf` is used
  (243 MB, replication timestamp 2026-10-14T20:21:12Z, downloaded 2026-10-15).
- D-004 Jeddah polygon `data/osm/jeddah.poly`: lon 39.02-39.33, lat 21.26-21.90 (south edge moved from 21.30, D-014), tapered in the
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
- D-013 Fix list: King Abdulaziz Road carriageways (ways 85191646, 43061113, 1071541010) have no
  `lanes` tag and defaulted to 2 lanes while tagged segments carry 4; fixed with a new
  `lanes_min: 4` fix type (raises only, keeps guessed ramp lanes). FIX-0001..0003 -> 68 edges.
- D-014 Polygon extended south from lat 21.30 to 21.26 after QA showed a 161 km southern district
  was unreachable (its only access crossing lay outside the clip): teleports 0.228 % -> 0.144 %,
  main SCC 98.61 % -> 99.10 %.
- D-015 Traffic lights stay OSM-only (`--tls.guess-signals --tls.discard-simple --tls.join`, 72
  programs from 338 OSM signal nodes). `--tls.guess` tested: 222 programs at the default threshold,
  30,275 at threshold 40, because untagged roads default to 100 km/h. Revisit after the
  untagged-lanes/speeds overlay (docs/network-qa.md).
- D-016 Buildings GeoJSON is 9.7 MB (< 50 MB) but stays gitignored with the rest of data/jeddah
  (CLAUDE.md: only data/demo, data/osm/fixes and data/census are committed); rebuilt by build_city.
- D-017 Strong connectivity is measured with `python -m sim.network.netinfo scc` (passenger lane
  connections, iterative Tarjan). Cut windows are far from strongly connected (demo: 49.7 %), because
  boundary edges are entry-only or exit-only; M5's cutRoutes link supplies through traffic.
- D-018 Lane-level outputs (`--lanechange-output`, `--queue-output`, `--lanedata-output`) added to
  the Tier A micro-only guard; `time-to-teleport` registered as A-sim-002 and the inherited typemap
  defaults for untagged roads as A-network-003.
- D-012 `run_claude.sh` (local launcher) is gitignored; `PROMPT.md` is committed as the session brief.
- D-010 Local npm is configured with `omit=dev`; use `npm install --include=dev` in `web/`.

## Open issues
- Untagged major roads: 83 % of secondary, 73 % of primary, 65 % of trunk km lack `lanes`; most
  untagged roads default to 1-2 lanes at 100 km/h. Largest realism gap; M2 type overlay planned.
- Traffic-light coverage far below reality (72 programs; 2,264 major 3+-approach junctions without
  a signal). Not verified against any official inventory.
- Demand generation dominates smoke runtime (500 s for 18k random trips). M2 must cache routes
  (network hash, population hash, day type, seed) and use duaIterate with routing threads.
- Disk: about 18 GB free on this Mac; the city net is 353 MB (plus a raw copy of the same size).

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

## M1 Jeddah network — 2026-10-15
Built: `sim.network.build_city` (Geofabrik GCC extract -> osmium clip to `data/osm/jeddah.poly` ->
gzip OSM XML -> netconvert with `sim/network/config/city.yaml` + Tier A type overlay -> fix list ->
districts, buildings and viewer GeoJSON + `jeddah.build.json` provenance); `sim.network.fixes`
(pydantic-validated YAML fix list: lanes, lanes_min, speed, oneway, remove; resolved via OSM
`origId`; strict mode fails on stale fixes) with three real fixes on King Abdulaziz Road;
`sim.network.build_window` (cuts windows from the city net so edge ids match Tier A; regenerated the
committed demo); `sim.network.netinfo` (streaming stats, SCC, edge GeoJSON); `sim.runner --smoke`
(random trips, meso Tier A / micro Tier B, run metadata, Tier A micro-only guard); Vite + MapLibre
viewer stub (`web/`, screenshot `docs/img/m1-viewer.png`); docs/network-qa.md, docs/data-sources.md.
Measured: city net 156,126 edges, 62,513 junctions, 72 traffic lights, 20,952.88 lane-km, build
56 s; main SCC 99.10 % of passenger edges; 112 districts, 27,783 buildings (9.7 MB). Tier A smoke
(seed 1, 1 h, 18,001 random trips): SUMO 24.1 s (real-time factor 149), demand generation 500 s,
26 teleports = 0.144 % (limit 0.5 %), peak memory about 2.9 GB (measured on the pre-extension network, same demand size). Tests: 27 pass in about 10 s.
Decisions: D-013 (lanes_min fixes), D-014 (polygon south to 21.26), D-015 (OSM-only signals),
D-016 (buildings stay gitignored), D-017 (SCC tool; windows not strongly connected), D-018.
Population sampling implications for M2 (18 GB RAM): a 1 h meso run of 18k vehicles (about 7k
simultaneously on the network) peaked at about 2.9 GB, and meso speed was about 150x real time. A
full-population weekday is 4.5-5.5 M vehicle trips (PROJECT.md section 2), so peak simultaneous
vehicles will be in the hundreds of thousands at the 07:00 peak. Meso memory grows roughly with
loaded routes plus running vehicles, so measure before choosing: plan a 10 % sample first, then 25 %,
and only then 100 %. Load routes incrementally (sorted route files, `--route-steps`), keep FCD off,
and stream edgeData. The binding cost is routing, not simulation: random-trip routing took 500 s
for 18k trips, so 5 M trips with several duaIterate iterations is hours to days. M2 should therefore
(1) route a 25 % sample with `--scale 4`-style capacity scaling as the default, (2) cache routes by
(network hash, population hash, day type, seed), (3) use duarouter routing threads and fewer
iterations on Tier A, and (4) snap zones to edges in the main SCC only.
Could not verify: real Jeddah lane counts on untagged roads (no imagery check) and the real signal
count; official district boundaries or district-level population (none found); the northern
enclave's exit restriction; Docker image builds; CI on GitHub (no remote configured).
Next: M2 Population and baseline. First three tasks:
1. Zones: districts as TAZs snapped to main-SCC edges, with census control total 3,712,917 (place
   Jiddah, GASTAT 2022) spread by residential building footprint area; registered as assumptions.
2. Untagged-road overlay: argued lanes/speeds per road class (A-network-003) and the next fixes
   (Al Harameen Road way 346621217), then re-run the smoke to confirm teleports stay < 0.5 %.
3. Synthetic population + weekday activity chains for a 10 % sample, routed with duaIterate, with
   runtime and memory measured at 10 % and 25 % to make the sampling decision.
