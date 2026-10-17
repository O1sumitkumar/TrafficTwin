# Track J — OBHUR_BRIDGE (bridges across Sharm Obhur)

## OBHUR_BRIDGE — 2026-10-17
All results: **synthetic demand, uncalibrated**. Full write-up: `docs/obhur-bridge.md`.

Built (all new files except the appended register section):
- `sim/bridge/`: `schema.py` (`BridgePolicy`: Track A's `network_change` plus a `bridges:` block),
  `network.py` (netconvert patch: abutment nodes, span, approaches, explicit lane connections;
  SCC-membership and duarouter through-route checks), `transforms.py` + `run.py` (city runs through
  Track A's `run_policy` with Track D's dispatch pattern; `--validate`), `desire.py` (desire lines,
  free-flow detours, landing accessibility), `window.py` (Tier B demand cut, baseline / matched
  control / variant micro runs, KPIs, `publish` for the viewer), `geo.py`, `config/bridge.yaml`,
  `config/sharm_obhur.geojson` (creek from the OSM coastline), `results/*.csv|json`.
- Policies `sim/policies/obhur_bridge_{b1,b2,b3}{,_3x3}.yaml`; window
  `sim/network/windows/obhur_creek.yaml`; film `movies/specs/obhur-bridge.yaml`; tests
  `tests/test_bridge.py` (18, synthetic two-bank network); `docs/obhur-bridge.md`,
  `docs/assumptions-trackJ.md` (A-obh-001..041, also appended to `docs/assumptions.md`),
  `docs/data-sources-trackJ.md`, `docs/img/obhur-desire.png`.

Measured:
- Public plans: a Sharm Obhur bridge was studied (2009), tendered by Metro Jeddah (2014-15, about
  US$1bn, 8 lanes + metro, 350-380 m water crossing), turned into a PPP (2018) and re-studied in the
  JDA Northern Obhur Road (2021-, five alignments); never awarded. No coordinates published.
- Validation on the city network (`jeddah.m2.net.xml`): all six policies pass
  `python -m sim.bridge.run <p> --validate` (every new edge in the main SCC, through-routes over each
  span both ways), 44-62 s and 1.4-1.7 GB each. B1: 1.28 km, 281 m over water; B2: 1.47 km, 890 m.
- Detour screen (no simulation, 19 min): 238,130 car trips/day cross the creek's desire line; B1 + B2
  shorten 145,370 of them by 6.0 km (2.9 min free flow); B1 does almost all of it, B2 alone 39,380
  trips by 2.6 km. Landing access: from 1.1 km away on the same bank it takes 8-24 km to reach
  three of the four landings (B1 south 1.3-1.6 km), which caps B2.
- Window (Tier B, `obhur_creek` 39 km2 / 3,221 edges, 66,660 AM and 59,540 PM vehicles, 25 micro runs,
  4-7.5 min each, grid 1 h 13 min): AM peak hour vs matched control, per vehicle: B1 -25.5/-26.9 s,
  B2 -26.2/-31.4 s, B3 -39.6/-44.0 s (seeds 1/2), B3 = -516/-573 veh-h; bridges carry 300-920 veh/h;
  3+3 adds little. PM: every variant -28 to -82 s, but seed spread up to 54 s (window near gridlock,
  26-34 % of peak vehicles arrive). Control-on-B3 network vs control: +2.8 s (unused links ~ no
  effect). Control vs cut-route baseline: AM +45 s, PM +184 s (routing gain, hence the matched control).
- Viewer: the API edge index of a bridge run holds the six new edges and its bins build with 0
  unmatched edges (span 1,164 veh/h at 06:00); `obhur-am-s1-obhur_bridge_b3` vs
  `obhur-am-s1-control-on-obhur_bridge_b3` share a network hash, so difference mode works.

Decisions:
- J-D-001 Bridges are `network_change` transforms with a `bridges:` block (`BridgePolicy`), run by
  `python -m sim.bridge.run` (Track D's `sim.loop.run` pattern). The brief's
  `python -m sim.policies.run <p> --validate` / `--control matched` do not exist (Track A's file, no
  such options, and its schema rejects `bridges`); the matched control is automatic. Integration hook
  (not done here, file not owned): `sim.schemas.validate_file` could validate a policy whose
  `network_change` has `bridges` as `BridgePolicy`, as it does for Loop.
- J-D-002 Own window `obhur_creek` instead of Track I's `obhur` (mouth only, up to 21.739 N): the
  head detour must be inside the window or a bridge cannot shorten it. Widened at the head so the
  King Abdulaziz Rd / Madinah Rd interchange is inside. 34 km2 of land, above the brief's 3-25 km2
  window range, deliberately.
- J-D-003 Shared inputs symlinked (gitignored), same pattern as `data/jeddah`: `data/population` and
  `runs/baseline-weekday-f0.1-s1-e5f1906a-65fac195-65b0f3` -> main checkout; edge caches copied to
  `data/policies/`.
- J-D-004 Explicit lane connections onto the approaches (netconvert drops edge-only connections for
  edges whose lanes were loaded); bridges are priority 12 (primary), landings unsignalised.
- J-D-005 Detours against free-flow shortest paths, not the baseline's assigned routes (16 % longer);
  pure-Python Dijkstra (no scipy; `pyproject.toml` not owned).
- J-D-006 Window evaluated on the peak hours 06-07 and 18-19 (the busiest window-entry hours), not
  the 3-h policy peaks: about 30 min per 3-h micro run on the shared machine.
- J-D-007 KPIs cover every vehicle due in the peak hour (tripinfo with unfinished and undeparted
  vehicles; time in system = arrival or run end minus planned departure): the first grid paired
  only arrived vehicles, biased by the different arrival shares, and was discarded and re-run.
- J-D-008 Seed-2 runs reuse the seed-1 baseline's routing weights: the seed changes only the
  simulation (noise band).
- J-D-009 Register rows appended to `docs/assumptions.md` (Track I precedent) so
  `test_merged_register_holds_every_track_row` holds; `docs/assumptions-trackJ.md` is the source.
- J-D-010 Narration kept as a comment block in the film spec: Track I's `scripts/movies/narrate.py`
  is not on main, and a `*.narration.yaml` file would fail main's spec validation.
- J-D-011 `control-on-obhur_bridge_b3`: the control's routes simulated on the B3 network, so the
  viewer (same-network-hash compare only, I-010) can show the difference; the film maps sources by
  edge id and uses the matched control.
- J-D-012 FCD only for the film runs (control, B3 AM) and only on edges within 900 m of a landing.

City runs for the coordinator (NOT run here; on the v2 network): see `docs/obhur-bridge.md` §5.
```
uv run python -m sim.bridge.run obhur_bridge_b3 --validate --net data/jeddah/<v2>.net.xml
uv run python -m sim.bridge.desire access --net data/jeddah/<v2>.net.xml
uv run python -m sim.bridge.run obhur_bridge_b3 --daytype weekday --sample 0.10 --seed 1
uv run python -m sim.bridge.run obhur_bridge_b1 --daytype weekday --sample 0.10 --seed 1
uv run python -m sim.bridge.run obhur_bridge_b2 --daytype weekday --sample 0.10 --seed 1
uv run python -m sim.bridge.run obhur_bridge_b3_3x3 --daytype weekday --sample 0.10 --seed 1   # optional
uv run python -m sim.bridge.desire detour --baseline runs/baseline-weekday-f0.1-s1-<v2 ...>
make movie FILM=obhur-bridge    # after re-pointing the spec sources to the city runs
```
Estimate: 30-40 min per policy including its matched control (about 45,000 sampled vehicles
re-routed), 1.5-2 h for the three 2+2 variants; plus about 2 h if the v2 weekday baseline must be
assigned first. Then fill the *pending city run* cells of `docs/obhur-bridge.md` §5-6.

Open: B2's value depends on landing access (re-check on v2); no interchange or signal design; no
induced demand; no bascule opening events.
