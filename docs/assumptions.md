# Assumptions register

Every parameter that describes how Jeddah behaves (not how the code behaves) is listed here and in
the YAML where it is used (see the `assumptions-register` skill). Status: `assumed` | `sourced` |
`calibrated` (only M8 sets `calibrated`). All results are **synthetic demand, uncalibrated**.

| id | parameter | value | unit | range | source or assumption | status | used in |
|---|---|---|---|---|---|---|---|
| A-network-001 | building floor-to-floor height | 3.2 | m | 3.0-3.6 | Typical Saudi residential/commercial storey height; no Jeddah source found | assumed | sim/network/config/buildings.yaml |
| A-sim-001 | meso-tls-penalty (expected red-phase delay scaling on meso edges) | 0.5 | factor | 0.3-1.0 | SUMO docs suggest 0.5-1; no Jeddah signal timing data; revisit in the M2 meso-vs-micro fidelity test | assumed | sim/config/runner.yaml |
| A-sim-002 | time-to-teleport | 300 | s | 120-600 | SUMO default; governs the teleport acceptance metric | assumed | sim/config/runner.yaml |
| A-network-003 | lanes and speed for OSM ways without `lanes` / `maxspeed` tags | SUMO typemap defaults (e.g. secondary 1 lane per direction at 100 km/h, primary 2 lanes) | lanes, km/h | class-dependent | Not a choice yet: inherited from `osmNetconvert.typ.xml`. 83 % of secondary and 73 % of primary km are untagged (docs/network-qa.md). Planned M2 overlay with sourced or argued values | assumed | sim/network/config/city.yaml (type_files) |
| A-network-002 | levels for untagged building footprints | 3 | levels | 2-4 | Most untagged Jeddah footprints are low-rise villas and walk-ups | assumed | sim/network/config/buildings.yaml |

Notes
- Smoke-run random-trip rates (`sim/config/runner.yaml`, `smoke:`) are test load for exercising the
  network, not behavioural demand, so they are not registered here. Behavioural demand starts in M2.
- Network-build settings (netconvert options, junction join distance, teleport time) are model
  settings, recorded in `sim/network/config/city.yaml` and `sim/config/runner.yaml`.
