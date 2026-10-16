# Track C status: lane audit from imagery

All results: **synthetic demand, uncalibrated**.

## LANE_AUDIT — 2026-10-16
Decisions
- C-001 Pillow is not a project dependency and `pyproject.toml` is outside Track C's ownership:
  crop generation runs with `uv run --with pillow`; the crop test uses `pytest.importorskip`.
  Integration should add `pillow` to `pyproject.toml`.
- C-002 `sim/network/fixes.py` extended additively: optional `confidence`, `method`, `source`
  fields on `Fix` (the model forbids extra keys). `lanes` / `lanes_min` and `direction` already
  existed, so no new per-direction field was needed.
- C-003 One sample per OSM way (see C-007 for the point); ways shorter than 60 m are skipped
  (junction stubs). Audit order motorway -> trunk -> primary -> secondary, longest first, cap 1,500.
- C-004 Ways covered by reviewed fixes (King Abdulaziz Road, FIX-0001..0003) are excluded from
  calibration and audit: reviewed fixes take precedence.
- C-005 Fix field: `lanes_min` when the imagery count raises the built default (keeps
  netconvert's ramp lanes), `lanes` when it lowers it, no entry when it confirms the default.
- C-006 The rebuilt network applies all fixes to the shared `jeddah.raw.net.xml` (same input
  the M1 build used) and writes `jeddah.lanes.net.xml`; `jeddah.net.xml` is never touched.
- C-007 Sample point = midpoint of the way's longest straight segment (first run used the
  geodesic midpoint of the whole way; a quarter of those samples landed on junctions, tunnel
  portals or curves). Same 40 calibration ways in both runs.
- C-008 Threshold rule: lowest confidence with precision >= 80 % on >= 15 kept crops that stays
  >= 80 % at every higher threshold keeping >= 15 crops (no lucky dips).
- C-009 The brief's 40 calibration ways choose the threshold; a disjoint 60-way holdout (seed 2)
  must also reach 80 % at that threshold before any audit fix is written. Without it the 40-way
  result is selected and scored on the same data.
- C-010 Analyst results are extracted from the subagent transcripts by a script into
  `data/imagery/<set>/results/*.jsonl`; every reading is kept in `imagery-eval.json`.

Built: `sim/network/lane_audit.py` (CLI: inventory, sample-calibration, crops, evaluate,
select-audit, write-fixes, rebuild); `tests/test_lane_audit.py` (offline: tile maths, sampling,
selection, threshold rule, holdout scoring, fix entries applied to the demo net, synthetic-tile
crop); `fixes.py` provenance fields; `data/osm/fixes/imagery-eval.json`; `docs/lane-audit.md` with
12 example crops in `docs/img/lane-audit/`; Esri attribution in `NOTICE`; A-network-004..007.

Measured: inventory 2,470 untagged major ways (92 motorway, 163 trunk, 744 primary, 1,471
secondary) = 2,254 of 2,972 major km (76 %). 3,274 Esri tiles fetched (about 3/s). Calibration
v2 (40 tagged): 70.0 % exact, 95.0 % within one lane; threshold 0.5 -> 83.3 % on 18 crops.
Holdout (60 tagged, disjoint): 58.3 % exact, 88.3 % within one; at 0.5 -> **60.0 % on 20 crops**
(trunk 1/8). Pooled 100: 63 % exact, no threshold reaches 80 % with >= 15 crops. Confidence barely
separates: crops rated <= 0.3 were 64 % correct. Before-smoke on `jeddah.net.xml` reproduced M1:
26 teleports = 0.144 %, SUMO 22.4 s, demand generation 542 s.

Not done because of the block: audit reading (115 of 1,500 crops on disk, 100 in the stopped
run's manifest, none read),
`imagery-lanes.yaml`, `jeddah.lanes.net.xml`, after-smoke. `jeddah.net.xml` untouched.

Could not verify: whether the disagreements are tag errors or reading errors (a few look like tag
errors, e.g. way 208082834; Prince Majid Road reads 4 vs tag 3); the capture date of the Esri tiles.

Next (see docs/lane-audit.md): human adjudication of the 37 disagreements, starting with Prince
Majid Road (19 of 25 trunk samples, 5 of the 8 confident holdout errors; holdout without it is
still 78.6 %); or a motorway-only audit
after a fresh motorway holdout (motorways 21/25 = 84 % so far, found after the fact); or two
independent reads per crop, validated on a fresh holdout. Integration: add `pillow` to pyproject.

LANE_AUDIT: blocked - accuracy

## M3 Viewer and API — 2026-10-16
Decisions
- C-011 Data contract first: `docs/contracts/run-outputs.md` (v1) defines `runs/<id>/` (meta, metrics,
  edgedata.parquet in 5-minute bins, fcd.parquet for Tier B, policy_report, scenario_report,
  recommendations, hash-chained decisions.jsonl) and the API. Missing optional files return 404
  "not available"; `python -m api.ingest` derives the Parquet files from SUMO XML.
- C-012 Tier A edge bins are dense Float32 arrays per bin and metric, aligned to a binary edge
  index per network hash (`edges.bin`, `TTE1` layout). Never per-vehicle data for Tier A. Difference
  mode is computed in the browser; both runs must share `network_hash`.
- C-013 `sim/runner.py` additive change: `fcd` kwarg / `--fcd` option (Tier B trajectories,
  `--fcd-output.geo`). FCD is not part of the config hash; the existing Tier A guard still rejects it.
- C-014 Derived caches live under `runs/_viewer-cache/` (runs/ is writable in docker-compose, data/
  is mounted read-only); runs listing skips `_` and `.` directories. Safe to delete.
- C-015 District choropleth: the policy report's district metrics when present, otherwise the
  computed % change in sampled-seconds-weighted mean speed per district (edge midpoint in polygon).
- C-016 Example reports (`python -m api.examples <tier B run>`) are fictional, demo-window only and
  marked `example`/`fictional` (PROJECT.md section 11); they exist to demonstrate the views until
  Tracks A/B write real reports.
- C-017 Basemap OpenFreeMap vector style (no key) with a plain fallback. React compiled with Vite's
  built-in esbuild (`@vitejs/plugin-react` current needs Vite 8). Vite proxy target: `VITE_API_TARGET`,
  else `http://api:8000` inside Docker (`/.dockerenv`), else localhost.
- C-018 Data for M3 is smoke output: city Tier A seed 1 at period 0.2 s (smoke-A-s1-5b8a19d3-ab76d081,
  26 teleports) and at period 0.25 s (smoke-A-s1-5b8a19d3-6ba142f4, 0 teleports; the
  comparison run for difference mode), demo Tier B seeds 1 and 2 with FCD.

Built: `api/` (FastAPI, file-backed: runs, metrics, bins, edges, district effects, trajectories,
reports, recommendations + decision POST with SHA-256 chain, jobs with SSE progress, ingest,
examples), `tests/test_api.py` (15 tests, about 8 s, tmp run dirs), `web/` (React 19 + TS strict +
Vite 7 + deck.gl 9.4 + MapLibre 5: run picker, Tier A binary PathLayer by 5-minute bin, metrics
speed_rel/speed/delay/density/flow, baseline-vs-scenario and difference mode, district choropleth,
extruded buildings, Tier B TripsLayer by speed or vType, event and closure overlays, 0-24 h slider
with play/pause/speed, strategist panel with approve/reject and decision log, policy/scenario tables,
start-run form with SSE, fps/heap HUD, deep-link URL params), `web/scripts/screenshot.mjs` +
`perf.mjs`, `docs/viewer.md`, six screenshots `docs/img/m3-*.png`.

Measured: ingest of all runs 12.5 s, peak 469 MB; city edgedata (116 MB XML, 324,033 rows) to
Parquet 2.9 s at 231 MB peak (242 MB at 3x the input, so memory is flat); city edge index from the
353 MB net 3.7 s, 156,126 edges, 434,982 points, edges.bin 4.10 MB (2.07 MB gzip). One city bin
624,504 B (38-44 KB gzip at smoke demand) = 7.5 MB raw per simulated hour per metric. Tier B
trajectories 1 h, 1,800 vehicles: 9.5 MB (2.3 MB gzip). Viewer, headless Chrome with the Metal GPU
(ANGLE Metal Renderer: Apple M3 Pro): full city at 300x 59.9 fps median (vsync cap), p5 59.5-59.9,
uncapped 172 fps median with an orbiting camera; Tier B 59.9 fps; JS heap 131-154 MB; Chrome RSS
0.86-1.39 GB across two measurement sessions; recolour of 156k edges per bin about 3 ms. Gates:
ruff clean, pytest 63 passed / 2 skipped (Pillow, lane audit), `npm run typecheck` and `build` pass.
Verifier: all engineering criteria PASS; the status block (this) and the memory range were its two
fixes.

Could not verify: `docker compose up`. The API image builds (`logs/m3-docker-build.log`), but
Docker Desktop hung on the first bind mount from `~/Documents` (looks like a macOS privacy prompt
nobody could answer), then its daemon stopped responding; it needs someone at the Mac. The
compose file, Dockerfile and vite proxy were reviewed statically by the verifier. The Docker
credential helper (`credsStore: desktop`) also blocked image pulls in this non-interactive session; a
clean DOCKER_CONFIG worked. Approve and start-run were exercised by the tests and curl, not clicked in
the browser. Real policy/scenario/strategist reports do not exist yet (the views use fictional
examples). Only one vType exists in the smoke runs, so "colour by type" shows one colour.

Integration notes: update the root README viewer section (lines 60-68 still say "M1 stub" / "API
stub") with `uv run uvicorn api.main:app --port 8000` + `cd web && npm install --include=dev && npm
run dev`, and drop the "stub" comments in docker-compose.yml and Dockerfile.api; run
`docker compose up --build` once Docker Desktop is healthy. Consider `VITE_API_TARGET=http://api:8000`
in compose and a `runs/`-based job log dir. Tracks A and B: write `edgedata.parquet` (or keep XML and
let ingest convert), `meta.baseline_run_id`, and the report files per the contract.

Next: once Tracks A/B produce a 24 h baseline and a policy run, replay them in the viewer and re-run
`npm run perf` on 288 bins; chunk Tier B trajectory loading for long windows.

M3: done
