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
