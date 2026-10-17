# Track I status: MOVIES_V2 (narration, legends, Obhur evacuation)

Branch `trackI`, worktree `.worktrees/trackI`. Owner feedback: voice-over, legends (street names,
north arrow), and the evacuation moved from Al Hamra to Obhur near the Jeddah Tower site.
Everything stays **synthetic demand, uncalibrated**; the evacuation is fictional.

## Decisions

- **TI-001 Nine films.** There are eight films plus the showreel; "all nine" is read as the eight
  films and the showreel, all re-rendered with labels and narration.
- **TI-002 Al Hamra withdrawn.** `sim/scenarios/evac_corniche_hamra.yaml` and
  `movies/specs/scenarios/evac_corniche_hamra_film.yaml` are deleted: the only tests that used the
  Hamra YAML (`tests/test_evacuation.py`: shipped-scenario validation and corridors-avoid-zone)
  now use `evac_obhur`, so no test depends on Hamra. Its results section in docs/evacuation.md is
  replaced by Obhur; historical status logs (docs/status/trackB.md, trackE.md, integration.md) are
  left as written. Al Hamra still appears as a district name (windows, Loop corridors, cordon,
  flood sites), which is not the evacuation demo.
- **TI-003 Tier A exit run re-made.** The windows were cut from `runs/tierA-exit-2f1822b7-cc34910d`,
  which no longer exists on disk. It was re-run once in this worktree with the documented command
  (`sim.link tier-a --routes runs/source-smoke-A/routes.rou.xml --seed 1`; Track B's M1 smoke route
  set, 18,001 vehicles, 1 h, meso, 110 s wall): the same config hash `cc34910d`, so the same run id.
  This is a small meso re-run of the link input, not a city baseline (the compute rule's city runs).
- **TI-004 Obhur window.** Polygon over the creek mouth (24.8 km2 with about 4 km2 of water), built
  with `sim.link window` + `cut` + `check` like the other windows; it sits in the shared
  `data/windows/obhur/` (new name, nothing overwritten). 2,339 edges, 1,014 junctions, no signals;
  2,757 cut vehicles; flow check PASS (GEH < 5 on 100 % of 91 edges, total ratio 1.000).
- **TI-005 Zone and crowd.** South bank of the creek mouth west of King Abdulaziz Road (generic
  polygon, 285 origin edges, 1.42 km2), 1,500 cars: the north bank at the Tower site is mostly a
  construction site with few streets, so the crowd sits across the water from it. Fictional
  (A-evac-039).
- **TI-006 Film option.** The strategist recommends balanced exit guidance (T90 1,402 s, no
  approval). The film shows the fastest-clearance option `far_first_full` (far-first phased release
  + balanced exits + contraflow, T90 1,349 s) because phasing and contraflow are what the film can
  show, and says on screen and in the voice-over that the recommendation is balanced guidance alone.
- **TI-007 Labels as HTML.** deck.gl's TextLayer does not shape Arabic (letters come out isolated
  and left-to-right), so street, district and landmark labels, the compass, scale bar, callouts and
  subtitles are HTML in the HUD, positioned per frame with deck's WebMercatorViewport; the browser
  shapes Arabic. Placement is greedy by priority with collision boxes; opacity is the share of the
  last 8 frames in which a label fits, so labels fade instead of popping and frames stay a pure
  function of the frame index.
- **TI-008 TTS venv.** Kokoro needs torch (large); it lives in `.venv-tts` (pinned
  `scripts/movies/tts-requirements.txt`, `make voice-setup`) and is called as a subprocess, so the
  project lock and CI stay unchanged. The CI smoke render is silent (`voice=False`); narration has
  its own tests and the TTS determinism test skips without the venv.
- **TI-009 TTS determinism.** Three sources of run-to-run differences, all fixed in the worker:
  (1) Kokoro's vocoder draws noise: torch is seeded before every line; (2) its G2P iterates over
  Python sets: the worker re-executes itself with PYTHONHASHSEED=0; (3) on the M3 the float32 CPU
  kernel of the 1x1 Conv1d `predictor.F0_proj` returned different sums for identical inputs in
  different processes (found by hashing every module's output over 6 processes: the first
  divergence was that layer), which the vocoder's sine phase turns into audible differences (up to
  368 LSB): Conv1d, ConvTranspose1d and Linear now run in float64 and cast back
  (`deterministic_cpu`). Result: 10 of 10 processes gave the same WAV for two test lines (before:
  2-3 variants in 6-10 processes). The first full render was stopped and restarted with this worker.
- **TI-011 Window cap.** The first Obhur polygon was 25.7 km2, over the 25 km2 cap that
  `tests/test_link.py` enforces. Its west and north-west vertices were pulled in over sea and the
  empty Tower site only, at least 398 m from any edge: 24.8 km2, and a rebuild into a temporary
  directory gave the byte-identical cut net (`f4fd448bd8799e25`), window net (`41f3b38254f9fbec`)
  and edge map, so every Obhur run stays valid. `obhur.window.json` records the new polygon; the
  window's `obhur.osm.gz` service-road extract is still the one cut with the first polygon (the
  graft result is identical).
- **TI-010 Subtitles.** Homebrew's ffmpeg has neither libass (`subtitles` filter) nor `drawtext`,
  so the burnt-in subtitles are drawn by the HUD from the same lines; the MP4 also carries a soft
  mov_text track and `movies/<film>.srt` sits next to it. `--no-subtitles` / `--no-voice` exist.
