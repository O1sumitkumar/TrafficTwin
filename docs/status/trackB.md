# Track B status (windows, events, strategist, evacuation)
All results: **synthetic demand, uncalibrated**.

## M5 Focus windows and events — in progress (2026-10-16)
Decisions (taken without questions, per prompts/_common.md):
- B-D-001 `sim/network/build_window.py` is not a Track B file. The service-road window build lives in
  `sim/link.py` (`python -m sim.link window --name <w>`): it calls `build_window.cut_window` on the
  city net (edge ids identical to Tier A), then grafts the window's service / living-street roads
  from OSM (window type map `sim/network/types/window.typ.xml`) by splitting the city edges they
  attach to. Split parts get deterministic ids (`<city id>` keeps the first part, `<city id>.s<k>`
  the rest) and an edge map `<w>.edgemap.json` (city edge -> window edge sequence) so cut Tier A
  routes are rewritten exactly. Integration may fold this into `build_window` later.
- B-D-002 Tier A routes for the link: the M1 smoke route set (`runs/smoke-A-s1-5b8a19d3-ab76d081`,
  random trips, 0-3600 s) re-simulated in meso with `--vehroute-output.exit-times` so `cutRoutes.py`
  uses Tier A exit times. Track A's population routes replace it later through the same CLI.
- B-D-003 Window artefacts (gitignored): `data/windows/<w>/<w>.net.xml`, `<w>.rou.xml` (cut routes,
  sorted by depart), `<w>.edgemap.json`, `<w>.window.json`. The committed `demo` window keeps
  `data/demo/demo.net.xml` + `demo.trips.xml` (random trips) so tests stay offline.
- B-D-004 `sim/schemas.py` is Track A's; scenario and vType pydantic models live in
  `sim/scenarios/schema.py` and `sim/vtypes/schema.py`; validation CLI `python -m sim.scenarios validate <file>`.
- B-D-005 `data/` is gitignored; `data/jeddah_flood_sites.yaml` (asked for by the brief) is
  force-added (`git add -f`), it is public literature only.
- B-D-006 PROJECT.md section 11: event files ship only with fictional parameters (times, durations,
  motorcade route) on the Tahlia window and are labelled so.
