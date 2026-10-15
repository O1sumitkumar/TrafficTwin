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
- B-D-007 Flood sites: `data/jeddah_flood_sites.yaml` has 25 sites (13 underpasses, 5 wadi
  crossings, 7 road segments; 11 high, 6 medium, 8 low confidence) from public press and papers on
  the 2009, 2011, 2015 and 2017 floods; locations checked against OSM. Only FS-001 (King Abdullah
  Rd / Madinah Rd tunnel) is pinned exactly for the reference events. These are publicly reported
  locations, not a critical-site inventory, so the file is committed (PROJECT.md section 11 read
  as covering response plans and non-public sites). Its `radius_m` defaults are assumption
  A-event-flood-radius (registered in docs/assumptions-trackB.md).
- B-D-008 Tahlia bbox east edge moved to lon 39.190 (about 23.9 km2) to contain FS-009, the King Fahd
  Rd / Tahlia St underpass (flooded 2017), so the flood demo closes a high-confidence site.
- B-D-009 Windows (`python -m sim.link window|cut|tls|check`): tahlia 23.8 km2, kaia_corridor 21.9
  (polygon), al_balad 17.0, kau_faisaliyah 19.7 (covers KAU / Al Jamiah only: OSM puts Al
  Faisaliyyah about 9 km from KAU, beyond one 3-25 km2 window; a separate window can be added).
- B-D-010 Tahlia first failed the 9.3 flow check (GEH<5 on 79.3 % of 420 edges, total ratio 0.637)
  because the netconvert-default program at the signalled at-grade level of the Madinah Rd / Tahlia
  interchange (OSM: Madinah Rd on a bridge, Tahlia in a tunnel, links signalled) gives the main right
  turn 6 s of a 90 s cycle, while Tier A meso only adds a red-time penalty. Decision: Tier B windows
  load Webster-retimed programs (`tlsCycleAdaptation.py`, A-link-009) from `<w>.tls.add.xml`; the
  city net is untouched. Result: all four windows pass (tahlia 90.2 % / 0.910, narrow margin;
  kaia_corridor 100 % / 0.992; al_balad 100 % / 0.995; kau_faisaliyah 100 % / 0.997). A reviewed
  program for that cluster (separate right-turn phases) is the real fix; left open.
- B-D-011 Tier A exit-time run (meso, seed 1, run to 14,400 s so every vehicle finishes): 18,001
  vehicles, 35.9 s wall, 26 teleports in the demand hour (0.14 %) but 202 over the whole run
  (1.12 %, mostly hour 2); hot spots `:cluster_2191210167_...`, `:6178528486`, `:9556669830` are
  fix-list candidates for the network owner.
