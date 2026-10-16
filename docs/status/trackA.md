# Track A status

## M2 Population and baseline — in progress (2026-10-16)
Decisions so far (details in docs/population.md once written):
- TA-001 Zones = 112 OSM districts; 3,712,917 residents spread by a blend of residential building
  footprint area (0.5), residential-street km (0.35) and landuse=residential area (0.15) because
  OSM footprints cover only part of Jeddah (27,783 buildings). Airport, seaport, naval base and
  industrial area hold no residents. A-pop-001.
- TA-002 OSM has no `route=bus` relations and no GTFS was found: bus availability uses OSM bus-stop
  nodes (49) with the 500 m catchment.
- TA-003 Routing algorithm: A* (benchmark on 20,205 trips, 8 threads, city net: dijkstra 80 s /
  3.1 GB, astar 62 s / 3.4 GB, CH 70 s / 5.0 GB single-threaded). Includes ~15 s net loading.
- TA-004 vTypes travel inside the trips file because duaIterate does not pass `-+` additional
  files to duarouter.
- TA-005 Capacity scaling for samples: vehicle length+minGap x 1/f and meso tau* x 1/f (A-sim-101).
- TA-006 Dependencies added to pyproject (shared file, additive): adhanpy (prayer times),
  matplotlib (plots), psutil (peak memory of runs).

Run estimate before the first city baseline (10 %, weekday, 3 duaIterate steps): about 424k
vehicle trips; routing about 17 min per step (A* benchmark), meso simulation unknown (M1 smoke:
real-time factor ~150 at ~7k running vehicles). Estimate 60-110 min end to end.

Update 02:25: duaIterate step 0 routing took 14.3 min (424,311 trips, A*, 8 threads); the step-0
meso simulation reached 06:45 after 8 min with ~10k teleports concentrated in the 06:00-07:00 hour
(free-flow routes). Revised estimate for the 10 % baseline: 2-2.5 h end to end (3 steps + final run).

### First 10 % attempt stalled (02:00-02:35) and what changed
The first 10 % baseline (M1 network, full meso junction control, sharp school peak) stalled in the
step-0 simulation: from 06:45 to 06:51 of simulated time took 13 min, ~13.8k teleports. It was
stopped. Diagnostics on the step-0 routes, 00:00-09:00, 10-min cap each (`runs/diag/`, logs/diag-*):

| run | capacity scaling | junction control | result |
|---|---|---|---|
| C | none (10 % demand as is) | full | 55 s, 1,969 teleports, 8.4k vehicles stuck at 09:00 |
| E | none | limited | 60 s, 59 teleports |
| F | none | off | 50 s, 13 teleports |
| A / D | length + tau x10 | full / off | killed at 600 s at ~06:48, ~11k teleports (AM gridlock) |
| G | length + tau x10 | limited | killed at 600 s in the 06:00 hour, 10.8k teleports, ~120 before 05:00 |
| H | tau x10 only (storage unscaled) | limited | 66 s, 13.4k teleports, 40.6k running at 09:00 |
| I | tau x10, storage x5.6 (f^0.75) | limited | killed at 600 s at 07:13, 21.5k teleports |

Findings and decisions:
- TA-007 Track A network variant `data/jeddah/jeddah.m2.net.xml` (new name; M1 net untouched):
  M1 build + `sim/population/config/untagged.typ.xml`, argued lanes/speeds for ways WITHOUT
  `lanes`/`maxspeed` tags (motorway 3 lanes 100 km/h, trunk 3/80, primary 3/70, secondary 2/60,
  tertiary 1/50; A-net-201). Built with `python -m sim.network.build_city --config
  sim/population/config/network-m2.yaml --out data/jeddah/jeddah.m2.net.xml --no-side-outputs`
  (100 s): 155,366 edges, 61,774 junctions, 74 TLS, 22,968 lane-km (M1: 20,953). This is the M1
  handoff's "untagged-road overlay" task; integration may move the two files to sim/network/.
- TA-008 Baselines use `--meso-junction-control.limited` (override in
  sim/population/config/baseline.yaml; runner.yaml is shared and unchanged): full junction control
  jams priority junctions at light load (C vs E). Recommend the same for the Tier A smoke.
- TA-009 Demand concentration was the main cause of the AM gridlock: 14.4 % of daily vehicle trips
  left in the 06:00 hour, 74 % of them school drop-offs and empty escort legs. Changes (all
  registered): early-arrival buffer U(0, 25) min (A-act-006); school start as a 50/50 mix of the two
  published Riyadh schedules (A-day-001); government flexible starts 07:30/08:30/09:30 (A-day-004);
  escort occupancy 2 and empty legs only with probability 0.5 (parents continuing to work;
  A-mode-001). Result: top-hour share 9.6 %, 1.05 vehicle trips per resident (3.9 M/day).
- Capacity scaling kept consistent (flow and storage, A-sim-101): storage-light variants (H, I) are
  no better on the old demand, and only consistent scaling keeps queues comparable across samples.
