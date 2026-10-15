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
