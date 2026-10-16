# Integration status

## INTEGRATE — 2026-10-16
Merged into `main`: trackC (M3 viewer/API; lane audit blocked), trackB (M5, M6, M7), trackA (M2, M4,
M8), in that order; only `sim/runner.py` conflicted (kept both sides). trackD (Loop tunnels) **skipped**:
its status reads `LOOP — in progress` (no `LOOP: done`), so a second integration pass is needed.
Lane audit blocked on accuracy: `jeddah.lanes.net.xml` does not exist; default network unchanged.

Gates on merged main: ruff clean; pytest 267 passed, 1 skipped (~3 min); web typecheck + build pass.
End to end (10 % sample, seed 1, synthetic demand, uncalibrated): weekday baseline (identical to
Track A's, 680 s from the route cache), remote_work_30 (mean delay -9.3 %), accident on Tahlia
(+5.7 % delay, 130 s), emergency strategist (top 3 in 11.6 s, best 68 s vs 173 s), evacuation via
`sim.runner --scenario evac_corniche_hamra` (T90 2,399 s). All five visible in the viewer through the
API (contract v1.1); screenshots `docs/img/integration-*.png`.
Verifier vs G1-G6: G1-G5 PASS; G6/hygiene/STATUS FAILs fixed (NOTICE, Esri crops untracked,
flood-site docs aligned, reproducible snapshot hash). Details and decisions I-001..I-005 in
docs/STATUS.md (Integration section).
Not verified: `docker compose up --build`.
Next: second pass to merge trackD once `LOOP: done`; re-link windows to the M2 baseline routes;
network capacity (TA-011, 50 % teleports); chunked Tier B trajectories; M9 docs and release.

INTEGRATE: done

## INTEGRATE pass 2 (Track E movies) — 2026-10-16
Merged `trackE` (MOVIES: done) into `main` with `--no-ff`. No conflicts: it was cut from main at cb98f6d.
Carried the specs, `scripts/movies/`, `web/src/cinema/`, tests, docs/movies.md, the README section and the
`docs/img/movies/` stills/GIFs. Nothing rendered under `movies/` went into git; only `movies/specs/` is tracked.
Track D was not merged or touched (still running).
Gates: ruff clean; pytest 292 passed, 1 skipped; tsc and vite build pass.
Film source runs: 11 runs that were reachable only through trackE's symlinks into the trackA, trackB and
trackE worktrees were copied into main's untracked `runs/` (I-006, about 1.1 GB). Main then rebuilt all
7 film bundles with hashes identical to Track E's; `tahlia-street` rendered in full on main (30.00 s,
155.9 s wall, same frame hashes).
Next: pass 3 for trackD once its status says `LOOP: done`, then render the `loop` film.

INTEGRATE: done

## INTEGRATE pass 3 (Track D Loop) — 2026-10-16
Merged `trackD` (`LOOP: done`) into `main` with `--no-ff` (b476837). No conflicts: purely additive plus
the one appended line in `sim/schemas.py`. Track E was not redone.
Fixes: the 21 A-loop rows merged into `docs/assumptions.md` (the register test failed after the merge);
`python -m sim.schemas` now validates `loop_*` policies; README "Loop tunnels" section.
Gates: ruff clean; pytest 316 passed, 1 skipped; tsc and vite build pass.
End to end (10 % sample, seed 1, synthetic demand, uncalibrated): `loop_demo --demo` 6.8 s, identical
to Track D's; `loop_recommended` on the city 504 s, reproduces `loop_opt_c1_a0p3` exactly (relief
57,671 VHT/day, 28,820 passengers/day). Both in the viewer via the API:
`docs/img/integration-loop{,-demo}.png`.
Loop film: real spec (C1 line and stations, morning-peak baseline, Loop-minus-baseline morning and
evening); `make movie FILM=loop` 34.00 s, 1020 frames, 246 s. Nothing copied from
`.worktrees/trackD/runs/`: its city runs had their edge Parquet pruned, so the film's run was produced
on main (I-007). Showreel: 8 films, 171.0 s (excerpts 20 s each, I-009). docs/movies.md and the README
preview updated. Verifier: 2 FAILs (bundle manifest keys, spec_sha note) fixed. Details in
docs/STATUS.md (Integration pass 3, I-007..I-010).
Open: viewer comparison across network variants (I-010).

INTEGRATE: done
