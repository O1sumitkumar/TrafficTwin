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
