# Track D status: Jeddah Loop tunnels (siting and optimal policy)

All results: **synthetic demand, uncalibrated.** Tier A (meso), 10 % weekday baseline from M2
(`runs/baseline-weekday-f0.1-s1-e5f1906a-65fac195-f124c5`), seed 1.

## LOOP — in progress (2026-10-16)

Decisions:
- TD-001 Loop policies extend Track A's policy schema with two transforms (`loop_shuttle`,
  `loop_private`, `sim/loop/schema.py`) and run through Track A's `run_policy` unchanged:
  `sim/loop/run.py` swaps in a dispatcher that knows the Loop transforms for the duration of the
  call (same run-time override pattern as Track A's `baseline_launch`) and caps one-shot
  re-routing at 4 threads (machine rule). Track A's `sim.schemas.Transform` union is the transform
  registry: Track A's test validates every `sim/policies/*.yaml` with `Policy`, so the Loop
  transforms are registered with the one allowed appended line in `sim/schemas.py`
  (`import sim.loop.schema`), which adds them to `Policy.transforms` and rebuilds the model. No
  other Track A file is edited.
- TD-002 Tunnel network (`sim/loop/network.py`): per alignment a tunnel node under each station,
  one 1-lane tunnel edge per direction between consecutive stations (crow distance x 1.15), and
  a down ramp (loading, 30 s stop) and up ramp per station to the nearest non-signalised junction
  with trunk/primary/secondary/tertiary edges in the main passenger SCC. Built by netconvert on
  the base network (Track A's structural options) under a new name
  `data/jeddah/jeddah.loop-<key>.net.xml.gz`; base network untouched. Experiment on the demo
  window: netconvert keeps the loaded connections of existing junctions, so surface-to-ramp
  connections must be given explicitly with lanes (private mode only); shuttle mode needs none.
- TD-003 "loop_shuttle" class = SUMO `custom1` (no user-named vClasses in SUMO).
- TD-004 Headway / capacity: SUMO meso has no vType headway; tunnel and ramp edges get an edge
  type (`loop_tunnel`, `loop_ramp`) with meso headways (`<type><meso tauff=...>` additional
  file), x 1/sample like every other headway (A-sim-101). Verified on the demo window: 20
  shuttles with tauff 30 s arrive ~30 s apart (default ~1-4 s). Measured scenario: headway =
  3600 x occupancy / 1,355 = 5.3 s; engineering: 1.5 s.
- TD-005 Shuttle passengers are not simulated as persons: shifted car tours become mode `loop`
  (their vehicles are removed) and shuttles run as an extra route file (loaded: 2 passengers in
  arrival order per station pair, a shuttle leaves with its last passenger; empty repositioning
  0.3 per loaded trip). Rider door-to-door time is estimated after the run (walk + wait + shuttle
  depart delay + simulated shuttle trip) and compared with the same leg's baseline car trip.
- TD-006 Road KPIs exclude shuttles (`loop_report`): city mean delay counts shuttles' 30 s
  loading stop as time loss, which inflates per-trip delay; VHT is shown both ways.
- TD-007 Siting is computed from the baseline in seconds (no SUMO): desire lines, top corridors,
  delay-weighted trip-end hot spots, all site pairs 6-25 km as straight alignments with snapped
  intermediate stations, scored by captured delay; 8 candidates by captured delay per km with an
  overlap rule; anchors KAIA/Al Balad/Tahlia-Andalus/KAU tested: KAIA was not covered by a
  data-driven pick, so C8 (KAIA - KAU) is an anchor test.

Run estimate before the first city run (recorded 13:40): each candidate is one shuttle-mode
policy run at 10 % (no re-routing: removed tours + shuttle routes; no matched control needed):
netconvert of the city net ~1-2 min (first time per alignment), transforms ~2 min, route merge
~2 min, 24 h meso run ~10 min (M2: 9 min), KPIs ~2 min: ~15-20 min per run, 8 candidates ~2-2.7 h
sequential. Private-EV runs add a one-shot re-route and a matched control: ~35-45 min each.
Optimisation: ~6 shuttle and ~3 private runs on the selected set plus 2 noise runs: ~4-5 h.
No single run is expected to exceed 90 min. Disk checked before each run (stop under 3 GB).
