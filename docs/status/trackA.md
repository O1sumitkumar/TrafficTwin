> **MONITOR NOTE (2026-10-16 07:35, written by the overnight orchestrator, not by Track A):** the 25 % baseline
> was deliberately KILLED by the monitor at 06:27 (not an OOM): the Mac's disk is at 99 % (≈7 GB free) and swap was
> full. Do NOT re-run the 25 % (or 100 %) baseline in this session. Treat the 10 % weekday baseline as the M2 result,
> record the 25 % attempt as "stopped by the monitor for disk/memory pressure; step-0 routing exceeded 45 min under
> contention", finish M2 (metrics, plots, fidelity report, tests, verifier, `M2: done`) and move on to M4. See
> logs/INTERVENTION.md.

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

### Second 10 % attempt (03:16-03:58): step 0 too slow, switched to incremental loading
With the de-peaked demand, m2 network and limited junction control, routing step 0 took ~12 min,
but the step-0 meso simulation (free-flow routes, full-equivalent load) reached only 07:30 after 30
min (real-time factor 1.4 in the peak, 23k teleports). Stopped. Tests on its routes, 05:00-08:00:
`--meso-recheck 10` is 8x faster but 5x the teleports; the rerouting device (period 300 s) was far
slower (05:50 after 9 min). TA-010: duaIterate incremental loading (`--inc-base 3`: steps at 1/3,
2/3 and full demand) so routes adapt before the full load.

### Third 10 % attempt (from 03:58, incremental loading) and the 25 % start
Step 0 (1/3 load): ~16 min, 206 teleports. Step 1 (2/3 load): simulation fast (24 h in ~10 min)
but ~21k teleports, on motorway off-ramps (`ramps.guess` one-lane `AddedOffRampEdge`, Al Harameen
Road ramps) in both peaks. Incident: while freeing disk (6.6 GB free machine-wide) I deleted the
running baseline's run directory and population cache by mistake; both were regenerated
deterministically from the same seed/config (population hash 65fac195, 389,289 vehicles, identical
to the routed set) so the run continued.
25 % estimate recorded before starting (04:50): ~970k vehicle trips; routing ~30 min per step x 3,
simulations 15-40 min each, final run and post-processing: 2.5-3.5 h, run in parallel with the
end of the 10 % run. The 10 % result is the smaller-sample result.

### Overload diagnosis (05:00-05:55) and bounded baselines
Step 1 of the incremental 10 % run gridlocked in the PM peak (18:21 -> 19:11 simulated in 27 min).
Tests on its routes, 16:00-19:00, 10-min caps:
- S: true full demand (`--scale 10`, normal vehicles): 168.6k running at 17:25 and rising.
- T: the 10 % sample with capacity scaling: 111k equivalent running at 17:25 and rising, so the
  scaled sample is, if anything, optimistic; capacity scaling is not the cause.
- T2: T without junction control: same growth. 32-41 % of teleports are inside junction clusters,
  the rest on primary/secondary roads and motorway ramps.
- PM 15:00-21:00 at full equivalent load: 300 s teleport time 366 s wall for 2.7 h simulated;
  `--meso-recheck 10` 115 s / 200k teleports; teleport time 120 s 221 s / 90k teleports.
TA-011 Finding: at the expected demand (3.9 M vehicle trips/day; consistent with the 2014 "6 M
trips/day" anchor and the brief's 4.5-5.5 M sizing) the M1/m2 network overloads in both peaks in
meso with 3 assignment steps. Network capacity (untagged lanes, junction clusters, ramps) is the
binding issue: handed to the network/lane-audit work as the top open issue. Decision: city
baselines use a 120 s teleport time (A-sim-103) so a 24 h run is bounded, and every report shows
the teleport share as the quality flag. Results are gridlock-affected and must be read as such.
25 % started again at 05:57 in parallel (estimate 2.5-3.5 h).
- 06:25 the parallel 25 % run died silently during step-0 routing (empty log; machine load average ~99 from Track B multiprocessing; likely killed under memory pressure). 25 % to re-run alone after the 10 % run.

### Result: 10 % weekday baseline completed (05:40-07:49)
Run `runs/baseline-weekday-f0.1-s1-e5f1906a-65fac195-f124c5` from the one command
`uv run python -m sim.runner --baseline --daytype weekday --sample 0.10 --seed 1` (m2 network, meso,
limited junction control, capacity x10, 3 incremental duaIterate steps, 120 s teleport time).
- Runtime: assignment 118 min (routing 24 / 29 / 47 min under heavy machine contention from other
  tracks; sims 2 / 5 / 11 min), final 24 h meso run 9 min (real-time factor 175), post-processing
  1.3 min; 129 min total. Peak RSS 3.7 GB (duarouter), 3.1 GB (sumo).
- Demand: 371,450 persons, 1,006,762 person trips (2.69/person), 389,289 vehicle trips (3.89 M
  city-equivalent, 1.05 per resident), top-hour share 9.6 % (06:00).
- KPIs (city-equivalent): 3.85 M trips completed (99.2 %), VKT 56.1 M, VHT 2.74 M (2.01 M delay),
  mean trip 14.6 km / 42.7 min, mean delay 31.3 min, mean speed 20.5 km/h, CO2 26,185 t, NOx 16,217 kg.
- Quality flag: 196,721 jam teleports (0.51 per loaded vehicle). Where (from sumo.log): motorway
  ramps (`Added*RampEdge`) 33k (17 %), inside junction clusters 42k (21 %), other edges 122k (62 %).
  When: ~125k (64 %) between 18:00 and 24:00, ~34k in 06:00-09:00; evening speeds 13-15 km/h. The baseline is
  gridlock-affected (TA-011: network capacity), labelled synthetic demand, uncalibrated. The top open
  issue for integration is network capacity (untagged lanes, ramps, junction clusters), not demand.
- Outputs: meta.json, metrics.json, report.md (with the fidelity caveats), tripinfo/edgedata/
  emissions/metrics_hourly/metrics_district Parquet, plots/ (departures, trip length, trips per
  person). Raw XML is deleted after conversion (disk).

### 25 % sample: runtime measured as a lower bound, not completed
One attempt, started 05:40 alongside the 10 % run (log `logs/baseline-weekday-f0.25-s1.log`, empty).
It was stopped by the overnight monitor at 06:27 for disk and memory pressure (data volume 99 % full,
swap 8.3/9.2 GB, load ~46; logs/INTERVENTION.md), still in step-0 routing after 45 min (10 %: 24 min
for the same step). Correction: the 06:25 note above ("died silently", "started again at 05:57")
was written before the monitor's account and is superseded by it. Per the monitor it is not re-run
in this session; the machine needs ~15 GB free first.
Estimate for an uncontended 25 % run with 8 routing threads: 3-4 h (routing scales ~linearly with
trips, ~970k); with the deterministic 1-thread default (TA-013) about 4x the routing time, 8-12 h.

### Sampling decision (default `--sample`)
TA-012 Default for Tier A baselines and policy runs: `--sample 0.10` with consistent capacity
scaling (`--scale` equivalent: length+minGap and meso tau x10, A-sim-101). Reason: 10 % is the only
city sample that fits the 18 GB machine alongside other work; 25 % needs ~2x the routing time and
memory. Updated after TA-013: the deterministic default (1 routing thread) makes a fresh 10 % run
~5 h (routing ~4x slower); the 8-thread setting (~2 h) is allowed for exploratory runs and is flagged
`routes_deterministic: false`. Reported results and policy comparisons use 1 thread or a cached
route set. Use 0.25 for final comparisons once disk/memory allow; 1.0 is not planned on this machine.

### Determinism of the assignment (verifier finding, fixed)
TA-013 The verifier found that two from-scratch demo assignments gave different routes: the seed did
not reach duaIterate, and multi-threaded duarouter is not repeatable. Fix: the run seed now goes to
every duarouter and sumo step (`duarouter--seed`, `sumo--seed`), and `routing_threads` defaults to 1.
With the seed alone, 8 threads still differed on the demo; with 1 thread the routes and tripinfo are
identical (new test `test_baseline_assignment_reproducible_from_seed`, empty caches, 2 steps).
Cost measured on the city net (21k trips, A*, free flow): 1 thread 427 s / 3.1 GB, 8 threads 106 s
/ 3.6 GB, so 1 thread routes ~4x slower. The 10 % baseline above was routed with 8 threads before
this fix: its routes (routes_hash in meta.json) are reproducible from the route cache
`data/population/routes/9724fafeab351805` only, not from the seed; the final simulation on them is
seeded and repeatable. It is not re-run now (disk, and ~5 h at 1 thread). A run that sets
`routing_threads: 8` records `routes_deterministic: false` in meta.json.

### M2 handoff (2026-10-16 08:30)
ruff clean; pytest 45 passed (demo window); verifier PASS after one fix round (assignment
determinism, sanity table, status corrections). Carried forward: re-run the 10 % baseline with 1
routing thread when ~15 GB are free (closes TA-013 for the reported run); 25 % run and the 10 % vs
25 % capacity-scaling check (A-sim-101); network capacity (TA-011) is the top issue for the
lane-audit/network work; README M2 command at integration (`uv run python -m sim.runner --baseline
--daytype weekday --sample 0.10 --seed 1`).
M2: done

## M4 Policy lab — in progress (2026-10-16)
Run estimate before starting the two new city baselines (recorded 08:35): the Friday and Ramadan-weekday
10 % baselines (`python -m sim.runner --baseline --daytype friday|ramadan_weekday --sample 0.10
--seed 1`) need their own duaIterate assignment (the whole population is re-timed). With the
deterministic 1-thread default (TA-013) routing is ~4x slower than the 8-thread M2 run: estimate
2.5-4 h each, run in parallel (2 routing cores, ~3-4 GB RAM each). The 10 % sample is the smallest
city sample; the weekday 10 % baseline from M2 is the result already available.

Decisions (M4):
- TA-014 Incremental routing for policy runs (A-pol-090): unchanged vehicles keep their baseline
  route; new / re-timed / re-moded / affected vehicles get a one-shot duarouter route on the
  starting baseline's congested travel times (edgedata, 900 s). A fresh 3-step assignment per
  policy would cost 2-5 h each; the incremental run costs ~12 min. A no-change policy reproduces
  the baseline tripinfo bit for bit (test). One-shot routing on fixed weights is repeatable with
  any thread count (test), so policy runs use 8 routing threads.
- Policy models live in `sim/schemas.py` (Track A's file since M2; additive) and
  `python -m sim.validate` is a new module; `sim/runner.py` gets an additive `--policy` option.
  `--daytype` is the comparison baseline; a policy with a `daytype` transform starts from that
  day type's baseline (Friday, Ramadan) and a daytype-only policy reuses its outputs.
- TA-015 The Ramadan baseline died when the disk filled (09:00, 1 GB free) and was restarted with
  8 routing threads (launcher monkeypatches `routing_threads`; baseline.yaml unchanged), so its
  routes, like the M2 weekday routes, are reproducible from the route cache only
  (`routes_deterministic: false`). The Friday baseline continues with 1 thread.
- TA-016 Policy runs write gzipped SUMO outputs (the uncompressed 10 % edgedata is 2.2 GB and
  filled the disk once); `sim/metrics.py` reads `.xml.gz`; sumo/build logs are gzipped.
- TA-017 `staggered_hours` groups institutions by the district of the school / workplace: the
  synthetic population has no school ids (the first attempt grouped by school edge: 35,715
  "schools", effectively per pupil).
- Network variants of `network_change` go to `data/jeddah/jeddah.m2.<policy>-<hash>.net.xml.gz`
  (new names; the base network is untouched); netconvert with the window cutter's structural
  options reproduces the base network body byte for byte on an empty patch.
