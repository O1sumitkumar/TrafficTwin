# Track E: MOVIES (cinematic films of the simulations)

Branch `trackE`, worktree `.worktrees/trackE`, cut from `main` after FINAL. Everything below is
synthetic demand, uncalibrated.

## Decisions

- **E-D-001 Browser driver.** The prompt names Playwright; the repo's screenshot scripts actually use
  puppeteer-core with the installed Google Chrome (`web/scripts/lib.mjs`). The frame stepper
  `web/scripts/cinema.mjs` reuses that (no new dependency, same GPU flags: ANGLE Metal on the M3
  Pro); `scripts/movies/render.py` drives it over stdin/stdout.
- **E-D-002 Python plans, the browser draws.** Camera interpolation, sun position, KPI values,
  fades and all data preparation are Python (`scripts/movies/`, unit-tested with pytest); the
  bundle in `runs/movies/<film>/bundle/` is static. The renderer (`web/src/cinema/`) is a plain
  deck.gl `Deck` without MapLibre or React, mounted only for `?cinema=<film>` (`main.tsx` branches;
  `App.tsx` is not touched). The viewer's API is reused in-process (run registry, bins,
  FCD normaliser), read only (`TT_RUNS_READONLY=1`).
- **E-D-003 Disk budget.** Frames are written to `runs/movies/<film>/frames/` in chunks of 150 PNGs;
  each chunk is encoded (libx264 CRF 18 yuv420p, bitexact) and its PNGs deleted, then the chunks
  are joined with the concat demuxer (stream copy). A whole 1080p film as PNGs would be about
  1 GB; the chunked render stays under 0.3 GB.
- **E-D-004 Package location.** The pipeline lives in `scripts/movies/` (presentation, outside
  `sim/`): `python -m scripts.movies.render|showreel|preview|spec|basemap|assets`.
- **E-D-005 Runs used.** This worktree has no runs of its own; `runs/` holds symlinks to the main
  checkout's runs (Tier A weekday baseline, remote_work_30, accident_tahlia, the M7 evacuation),
  Track A's matched-control policy runs and Track B's event runs (rain, flood, motorcade,
  emergency) and the strategist recommendation `rec-20261016T114454Z-22d13986`. All read only.
  `data/windows` is a symlink to the main checkout (window networks).
- **E-D-007 One new SUMO run.** The M7 evacuation runs are "as written" (simultaneous release, no
  contraflow), so the evacuation film had nothing to show for contraflow and phasing. One window run
  was added: the strategist's `near_first_full` candidate written into a copy of the scenario
  (`movies/specs/scenarios/evac_corniche_hamra_film.yaml`), run once with
  `uv run python -m sim.events.evacuation run --scenario movies/specs/scenarios/evac_corniche_hamra_film.yaml --seed 1`
  (about 5 min) -> `runs/evac_corniche_hamra_film-tahlia-s1-99ab2558`: T50 1,365 s, T90 2,934 s,
  T100 3,673 s, 2000/2000 out, contraflow on cf1-cf3 at 1,500 s, background +59.7 veh-h.
  No city run was started.
- **E-D-008 Incident framing.** `accident_tahlia` closes the whole edge and drivers re-route
  (A-event-003): the run has no queue shockwave at the crash (stopped vehicles within 1 km of it
  stay below 5 in both runs). The film shows the side-by-side and the speed-difference map and
  says so in its caption; it does not draw a queue the run does not contain.
- **E-D-009 Strategist film.** The what-ifs saved no FCD; the ambulance is moved along each route
  edge over the recorded `ambulance_edge_s` (A-mov-008, ETAs exact), the cars around it are the
  window baseline, the crash marker is the snapshot's closed lane. Options are no strategy, then
  ranks 1-3 of the recommendation.
- **E-D-010 Policy KPIs.** The policy-lab film shows the docs/policies.md results-table numbers
  (matched control for staggered schools and the cordon), entered as literals in the spec with a
  comment; edge colours are policy minus comparison run per 5-minute bin.
- **E-D-011 Tier B clock.** Window t = 0 is shown as 08:00 (A-mov-007), as
  `strategist/scenarios/emergency_tahlia_0830.yaml`; the sun on window films follows it.
- **E-D-012 Previews in git.** `movies/` stays git-ignored (except `movies/specs/`); the README GIF
  previews and JPEG stills are copied to `docs/img/movies/` (`make movies-docs`) so the README shows
  them.
- **E-D-013 Loop.** `docs/loop.md` does not exist on this branch (Track D not merged):
  `movies/specs/loop.yaml` is a validated stub (`stub: true`), skipped by `make movies` and the
  showreel. `.worktrees/trackD` was not touched.
