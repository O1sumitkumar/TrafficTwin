# Track C status: lane audit from imagery

All results: **synthetic demand, uncalibrated**.

## LANE_AUDIT (in progress)
Decisions
- C-001 Pillow is not a project dependency and `pyproject.toml` is outside Track C's ownership:
  crop generation runs with `uv run --with pillow`; the crop test uses `pytest.importorskip`.
  Integration should add `pillow` to `pyproject.toml`.
- C-002 `sim/network/fixes.py` extended additively: optional `confidence`, `method`, `source`
  fields on `Fix` (the model forbids extra keys). `lanes` / `lanes_min` and `direction` already
  existed, so no new per-direction field was needed.
- C-003 One sample per OSM way at the geodesic midpoint; ways shorter than 60 m are skipped
  (junction stubs). Audit order motorway -> trunk -> primary -> secondary, longest first, cap 1,500.
- C-004 Ways covered by reviewed fixes (King Abdulaziz Road, FIX-0001..0003) are excluded from
  calibration and audit: reviewed fixes take precedence.
- C-005 Fix field: `lanes_min` when the imagery count raises the built default (keeps
  netconvert's ramp lanes), `lanes` when it lowers it, no entry when it confirms the default.
- C-006 The rebuilt network applies all fixes to the shared `jeddah.raw.net.xml` (same input
  the M1 build used) and writes `jeddah.lanes.net.xml`; `jeddah.net.xml` is never touched.
