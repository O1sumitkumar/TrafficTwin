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

Measured (13:20): one shuttle candidate run = 10.6 min wall (transforms 35 s incl. netconvert,
merge 20 s, 24 h meso 8.5 min at 2.9 GB peak RSS, KPIs/report 71 s); ~90 MB disk per run after
pruning (run dir 47 MB + 42 MB variant network, now deleted after each run).
- TD-008 Single-seed noise is of the same order as a corridor's effect: C3 removed 3,532 sampled
  car trips yet came out at -0.4 % VHT, and Track A measured +1.3 % VHT from a sim-seed change
  alone. So every candidate is also re-simulated with sim seed 2 and compared with the seed-2
  baseline replicate (Track A's replicate machinery, `runs/loop_noise_baseline_s2`); candidates
  are ranked on the two-seed mean and the greedy step skips any whose saving changes sign between
  seeds. Estimate (recorded 13:30): replicate + 8 candidate runs ~1.7 h; then the optimiser:
  13 sweep runs (3 private-EV with matched controls, ~25-30 min each), a network placebo and a
  seed-2 replicate of the recommended configuration, ~3.5-4 h. No single run above 90 min.
- TD-009 Added a time-competitive shift sensitivity (A-loop-017): only tours whose every leg is
  faster by Loop (walk + wait + loading + ramps + ride) than by car in the baseline. C1 showed
  69 % of shifted legs slower than by car under the measured 12.5 min wait, so the fixed-alpha
  result is optimistic; the competitive runs are where speed and wait (vendor vs measured) bite.
- TD-010 Preliminary verifier (13:30): 4 of 8 checks failed; fixed:
  (a) Objective. City VHT saved counts the removed cars' own hours as savings. The decision
  metric is now **congestion relief** = hours (travel + departure delay) saved by the vehicles
  that are on the road in both runs (same vehicle id, shuttles excluded), per USD M of capex.
  Riders' extra door-to-door time is reported as net person-hours (relief minus riders' extra
  time vs their baseline car trip). City VHT saved stays in the tables. Finished runs are
  recomputed from their outputs (`python -m sim.loop.evaluate --rebuild`, no re-simulation).
  (b) Shuttle dispatch had no time window (pooling waits up to hours at 10 %): a shuttle now
  leaves when full or 180 s after its first passenger (A-loop-019). Road KPIs of the seed-1
  candidate runs C1-C8 are unaffected (only shuttle departure times change); the seed-2 and
  sweep runs use the window.
  (c) Greedy: both seeds must agree on the sign and the mean must exceed the two-seed noise
  (replicate noise / sqrt 2); empty selection handled. Quality gate also checks tunnel-segment
  exceedance (headway is per segment and direction; the 1,355 pph figure is applied per station
  pair for the flag, as the brief says, and per tunnel direction as the headway).
  (d) Demo CLI: `python -m sim.loop.run loop_demo --demo` builds demo-window zones (Track A's
  fidelity setup) and caches under `runs/loop-demo/` and runs in ~10 s.
  (e) Register: lanes, overlap and selection heuristics, budget (A-loop-018), dispatch window
  (A-loop-019) moved to YAML and registered; the sweep reads the YAML sweep lists.
  Known limitation kept: `python -m sim.policies.run loop_demo` validates (schema registration)
  but fails at apply; Loop policies run through `python -m sim.loop.run`.
- TD-011 Seed-2 replicates (14:10-15:40): C1 71.0k / 71.5k and C2 47.4k / 53.2k VHT/day relief
  agree; C3 (-19.8k / +89.5k), C5 and C6 change sign and are excluded. The seed-2 baseline is
  itself more congested (+36k VHT) and relief is larger from a more congested start, so seed 2
  runs systematically higher (gridlock non-linearity). Replicate noise of one comparison:
  34k VHT/day relief (1.25 %). Greedy (with the knapsack correction) selects C1 alone
  (17.86 km): C2 is best per km but nothing else fits beside it, and C1 alone relieves more.
- TD-012 Shuttle speed runs on C1 gave 42.7k / 53.5k / 95.6k relief at 50 / 90 / 160 km/h.
  Shuttles never use surface roads, so tunnel speed has no causal path to road relief in this
  model: the spread is simulation noise (a direct empirical noise estimate, larger than the
  replicate's). The recommendation pools the shuttle speed runs as replicates of one option;
  speed matters only for riders (and in private mode).
- TD-013 With the 180 s dispatch window shuttles run less full, so at the measured Vegas
  throughput (~680 shuttles/h per direction) ~30 % of C1 tunnel-segment traversals are in
  over-capacity hours. Over-capacity throughput is possible only via jam teleports (120 s
  teleport time, A-sim-103): vehicles queued at a full tunnel jump through it. The private-EV
  SAR 10 run reached 3x the tunnel capacity this way (98.7k relief vs its matched control is
  therefore teleport-assisted). Tunnel segment exceedance is now measured for both modes and
  gates the recommendation; a private-EV engineering-capacity run was added. Optimiser
  restarted 16:30 (finished runs reused), ~4.5 h of runs left.
