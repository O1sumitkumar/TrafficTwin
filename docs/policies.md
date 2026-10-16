# Policy lab (M4)

All results: **synthetic demand, uncalibrated.** Tier A (SUMO mesoscopic), 10 % population sample
with capacity scaling (A-sim-101), seed 1. The city baselines are gridlock-affected in both peaks
(TA-011): every report shows the teleport share as a quality flag. Trust deltas more than levels.

## How a policy run works

```
uv run python -m sim.runner --policy remote_work_30 --daytype weekday --sample 0.10 --seed 1
```

1. **Baselines.** `--daytype` names the comparison baseline. A policy whose first transform is
   `daytype` (Friday, Ramadan) starts from that day type's baseline; otherwise the run starts from
   the comparison baseline. Baselines are looked up in `runs/` by day type, sample, seed, network
   hash and population hash (and run with `python -m sim.runner --baseline` if missing).
2. **Transforms** (`sim/policies/transforms.py`) edit the starting baseline's person trips and
   vehicle trips at the tour level: remove tours, re-time them, add tours, or change their mode.
   The plan is recomputed from the population and checked against the baseline's vehicles hash.
   Random draws use streams keyed by the seed and the transform type, so a sweep over a share
   selects nested sets of people and the response curve is monotone in the selection.
3. **Incremental routing** (TA-014, A-pol-090). Vehicles whose trip is unchanged (same id, type,
   departure, origin, destination) keep their baseline route. New, re-timed, re-moded and
   affected vehicles (closure, cordon) get a one-shot `duarouter` route on the starting baseline's
   congested travel times (its edgedata aggregated per 900 s, plus policy penalties). One-shot
   routing on fixed weights draws no random numbers, so it is repeatable with any thread count
   (tested). There is no re-equilibration: drivers do not move into capacity the policy frees,
   so deltas are first-order.
4. **Simulation** with exactly the baseline's options (meso, limited junction control, 120 s
   teleport time, capacity scaling); a policy that changes nothing reproduces the baseline
   tripinfo bit for bit (test `test_null_policy_reproduces_the_baseline`). A daytype-only policy
   reuses the day type's baseline outputs (hard links).
5. **Report** `runs/<id>/policy_report.json` and `.md`: city KPIs vs the baseline (mean delay,
   AM-peak delay, speed, VKT, VHT, delay hours, throughput, peak hour, top-hour share, CO2, NOx,
   teleports), peak spreading (AM 06-09, PM 16-19, baseline peak hour, hourly table), per-district
   winners and losers (origin district, change in mean delay per trip, districts with >= 1,000
   trips), the ten most relieved and most worsened corridors (time loss per street name,
   city-equivalent vehicle-hours), the transform effects, the assumption ids used and provenance.

Run directories are `runs/<policy id>` (suffixes `-vs-<daytype>`, `-f<sample>`, `-s<seed>` when a
run differs from the policy's defaults). Policy outputs are gzipped (TA-016).

## Transforms

| type | parameters | what it does |
|---|---|---|
| `remote_work` | share (or per sector), days_per_week, eligible_sectors, induced_trip_probability, induced_purposes | a worker in an eligible sector is at home today with probability share x days/5; their work tour (and its vehicles) is removed; with the induced probability they make one daytime non-work tour timed like homemakers' tours |
| `staggered_hours` | segment (school, government, ...), offset_minutes, spread_minutes, share | a share of institutions (grouped by district of the school or workplace; no school ids in the population) shifts every leg of its members' main tours by the offset plus an institution-level N(0, spread); escort legs follow |
| `daytype` | daytype | the run starts from that day type's baseline (whole population re-timed) |
| `pt_line` | line_id, stops (lon/lat), both_directions, headway_s, hours, catchment_m, shift_share, shift_modes | stops snapped to bus-capable edges in the line's direction; `ptlines2flows.py` (on a sub-network around the line) builds bus flows and stops; a fixed share of car tours with both ends within the catchment of different stops switches to bus |
| `road_pricing` | polygon, charge_sar, hours, direction, elasticity, base_trip_cost_sar, retime_share, value_of_time_sar_h | tours whose baseline route crosses the cordon during the hours: suppressed share 1 - (1 + charge/cost)^elasticity, of which retime_share move just outside the hours and the rest are dropped; the remaining crossers are re-routed with charge/VOT seconds added to cordon-crossing edges |
| `network_change` | edits (edges or name + bbox; closed, lanes, speed_kmh), new_edges, tls_program | netconvert patch on the baseline network (variant `data/jeddah/<base>.<policy>-<hash>.net.xml.gz`); an empty patch reproduces the network body byte for byte; vehicles using removed edges are re-routed, trip ends on removed edges move to the nearest open edge of the zone |
| `ridehail_share` | convert_share, deadhead_factor | a share of car-driver tours becomes ride-hail; each new ride gets an empty leg from a zone about deadhead_factor x trip distance away |

## Demo policies

| file | policy | compared with |
|---|---|---|
| `remote_work_30.yaml` | 30 % hybrid work in government and private offices, 3 days/week, induced trips 0.35 | weekday |
| `staggered_schools_60.yaml` | schools in half of the districts start 60 min later | weekday |
| `friday.yaml` | Friday profile | weekday |
| `ramadan_weekday.yaml` | Ramadan-weekday profile | weekday |
| `bus_line_tahlia.yaml` | bus line on Tahlia Street, 10 stops, every 10 min, 10 % car shift in the catchment | weekday |
| `cordon_center.yaml` | SAR 10 cordon around central Jeddah, 07:00-19:00 | weekday |
| `close_corniche_road.yaml` | close 3 km of the North Corniche Road (both directions) | weekday |
| `ramadan_remote_30.yaml` | composed: Ramadan weekday + 30 % hybrid work | Ramadan weekday |
| `ridehail_plus_10.yaml` | P1: 10 % of car tours to ride-hail with deadhead 0.4 | weekday |

## Results (10 % sample, seed 1)

RESULTS_TABLE

## Response curve: remote-work share

SWEEP_SECTION

## Limitations

- One-shot routing, no re-equilibration (A-pol-090); deltas are first-order.
- Meso gridlock makes delay strongly non-linear in demand: removing ~2 % of vehicle trips can cut
  mean delay by ~10 %. Delay changes overstate what a less congested (better-calibrated) network
  would show; VKT and trip counts are more robust.
- One seed; no confidence intervals yet.
- Bus vehicles are not capacity-scaled (A-pol-091); no bus passenger KPIs (no person-level PT
  simulation in v1).
- Road pricing is indicative (PROJECT.md section 7): constant elasticity, no destination choice.
- Ramadan baseline routes were assigned with 8 routing threads (TA-015), like the M2 weekday
  baseline: reproducible from the route cache, not from the seed alone. The Friday baseline used 1
  thread (deterministic).
