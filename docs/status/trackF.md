# Track F: NETWORK_V2 (fix the Tier A capacity gap)

Branch `trackF`, worktree `.worktrees/trackF`, cut from `main` at 007d366. Everything below is
**synthetic demand, uncalibrated**. Details and tables: `docs/network-v2.md`.

## NETWORK_V2 — in progress (2026-10-17)

### Diagnosis of the m2 baseline (before any change)
`python -m sim.network.teleports hotspots runs/baseline-weekday-f0.1-s1-e5f1906a-65fac195-65b0f3/sumo.log
--net data/jeddah/jeddah.m2.net.xml` (195,277 teleport lines parsed of 196,721 counted by SUMO):
teleports are diffuse (7,517 locations; top 15 = 3.6 %), 21 % on junction internal edges, 17 % on
the 95-m edges netconvert adds when it guesses ramps, 67 % of edge teleports on edges < 100 m,
and they pile up in the evening (hours 18-23 hold 64 %). Sampled vehicles are 71 m long (46 m +
25 m gap: 10 % capacity scaling, A-sim-101), and 55 % of the city's edges are shorter than 75 m,
so short-edge storage is part of the mechanism; lane counts are the other part.

### Decisions
- **TF-001 Evidence-based lane/speed defaults as an OSM pre-pass, not a typemap.** A typemap cannot
  tell a oneway carriageway from a two-way road of the same class; the pre-pass
  (`sim/network/lane_defaults.py tag`) adds `lanes`/`maxspeed` per class x oneway to untagged ways
  only, marked `traffictwin:defaults=A-net-301;A-net-302`. Defaults = km-weighted median of the
  tagged ways of the same class x oneway on the same clip (evidence file
  `sim/network/types/jeddah-lanes.json`), used when >= 5 km are tagged.
- **TF-002 Two-way roads are not widened.** Two-way secondary/tertiary/primary have 1.4 / 2.1 /
  2.0 km tagged; borrowing the dual-carriageway median (3 lanes per direction) would turn
  undivided roads into 6-lane roads. Their lanes stay on the SUMO typemap; maxspeed falls back to
  the class median.
- **TF-003 Held-out cross-check: no class disagrees strongly; the tagged median is kept.**
  130 lane-audit ways (both holdouts + calibration sets, read from Track C's results, no imagery
  calls): the default equals the way's own tag for motorway 62 %, trunk 89 %, primary 39 %,
  secondary 60 % (SUMO typemap 0 / 5 / 17 / 4 %, m2 overlay 36 / 89 / 39 / 28 %); within one lane
  74-98 %. Imagery reads agree 45-68 % (the imagery itself failed its 80 % gate). Motorway is the
  weakest (imagery tends to read 3 where the median says 4); the brief says to prefer the tagged
  median, so 4 stays.
- **TF-004 A peak probe instead of the 1-hour random-trip smoke for comparing variants.** The
  official smoke teleports 0.14 % on v1 and cannot tell variants apart. `python -m
  sim.network.probe` takes the m2 baseline's own vehicle trips 05:00-09:00 (91,392 sampled
  vehicles, capacity-scaled vTypes), routes them once at free flow and runs meso with the baseline
  Tier A options; ~6 min per variant. Free-flow routes load harder than the 3-step assignment, so
  the probe is relative (m2: probe 57.3 % vs baseline 50.5 %).
- **TF-005 Ramp splitting kept (`--ramps.guess` as in v1).** `--ramps.no-split` removes the short
  ramp edges but also the extra lane they carry: probe 48.0 % vs 40.0 % with splitting.
- **TF-006 `--no-internal-links` rejected.** Removes the junction-internal teleports but moves them
  upstream: 51.4 % (with no-split) vs 48.0 % without.
- **TF-007 `--junctions.join-dist 30` rejected** (with no-split): 48.6 % vs 48.0 % at 20 m.
- **TF-008 v2 is the default for Tier A baselines.** `sim/population/config/baseline.yaml` and
  `zones.yaml` point at `data/jeddah/jeddah.v2.net.xml`; `build_city` defaults to profile v2;
  `--network-profile v1|m2` rebuild the old networks (both reproduce their hashes, 5b8a19d3 and
  e5f1906a, written to /tmp).
- **TF-009 Incident: shared clip mtimes touched.** The first v2 build re-ran `osmium extract/cat`
  onto `data/osm/jeddah.osm.pbf` and `jeddah.osm.gz` (symlinks into main) because the worktree's
  `jeddah.poly` was newer than the clip. Content is byte-identical (hashes cafede24 / b491ff1d
  before and after); only mtimes changed. It also appended to the shared
  `data/jeddah/build_city-jeddah.log`; `build_city` now names custom-output logs after the full
  output stem so variants never share a log.

- **TF-010 Zones and population rebuilt on v2.** Zone edges are network edge ids, so v2 has its own
  zones (hash d949c812) and population (346893f2); v1/m2 zones are untouched in the main checkout.
- **TF-011 `--tls.guess` rejected** (probe 40.2 % vs 40.0 %, 283 TLS vs 73): no gain, and 210
  guessed signals cannot be checked against an inventory.
- **TF-012 v2 = v2a settings.** None of the junction/ramp/TLS variants beat measured lanes + speeds
  with the v1 netconvert options; `city-v2.yaml` keeps those options.
- **TF-013 No second city run.** First run 28.3 % > 10 %, so the hotspots were checked for fix-list
  entries: the diverges are consistent with the tags of the same roads, and the central cluster's
  same-road tagged segments agree with the defaults (King Abdullah Rd trunk 6.0 km tagged, median 3;
  Bani Malik St 7.8 km, 3; Prince Majid Rd 42.4 km, 3). No entry is sourced, the top 10 hold 3.7 %,
  and a teleport-time-300 probe shows real gridlock (40.6 %, 12,500 vehicles stuck vs 3,616), so a
  rerun would cost 2 h for at most a few points. Unsourced fixes are not added.
- **TF-014 Same-road lane propagation not adopted** (documented as a v3 candidate,
  docs/network-v2.md §5): 386 untagged km covered, 168 km changed in both directions, not at the
  hotspots, and it lowers two motorways from 4 to 3 lanes.
- **TF-015 Demo window and Tier B windows stay cut from v1.** Tier B is microscopic and its windows
  were cut and linked on v1/M1 routes (B-D-002); re-cutting from v2 is listed for the coordinator.
  The quick demo steps were rerun: same run ids and KPIs as M9 (tier-b smoke-B-s1-25c06763-9cfa755f
  0 teleports; events demo_events-demo-s1-342c09a8; strategist; evac_demo-demo-s1-ed042153; policy
  VKT -1.6 %, VHT -1.4 %); only the demo-policy baseline's config hash moved (1ea5e5 -> 0541a8)
  because `baseline.yaml`'s `net:` path is part of the hashed config.

### Probe results (AM 05-09, same 91,392 vehicles; teleports per vehicle)
| network | settings | hash | teleports | mean speed | time loss |
|---|---|---|---|---|---|
| m2 (control) | Track A overlay A-net-201 | e5f1906a | 57.3 % | 34.3 km/h | 1,608 s |
| v2a | measured lanes + maxspeed (pre-pass) | ae764558 | 40.0 % | 43.3 km/h | 1,204 s |
| v2b | v2a + `--ramps.no-split` | bf84c83a | 48.0 % | 41.8 km/h | 1,226 s |
| v2c | v2b + `--junctions.join-dist 30` | ebc9d3a3 | 48.6 % | 41.9 km/h | 1,248 s |
| v2d | v2b + `--no-internal-links` | 290ec69b | 51.4 % | 43.5 km/h | 1,082 s |
| v2h | v2a + `--junctions.join-dist 30` | 80b9c370 | 40.3 % | 43.7 km/h | 1,188 s |
| v2i | v2a + `--no-internal-links` | 08dbc7a4 | 41.5 % | 45.0 km/h | 1,061 s |
| v2k | v2a + `--tls.guess` | c2c84582 | 40.2 % | 43.0 km/h | 1,210 s |
| v2 diag. | v2a, `--time-to-teleport 300` | ae764558 | 40.6 % | 38.5 km/h | 1,716 s |
(v2j, join 30 + no internal links, was stopped unfinished to free the machine for the city run.)

### City run estimate (recorded before starting)
10 % weekday baseline on v2 with `python -m sim.policies.baseline_launch weekday --routing-threads 6
--gzip`: new zones (v2 edges) mean a fresh population, trips and a 3-step assignment. Track A's 8-
thread run took 118 min of assignment under contention; with 6 threads and today's load (~25-30
from other tracks) estimate **2.5-3 h**. The smaller-sample result available beforehand is the
peak probe above (10 % sample, AM window).
