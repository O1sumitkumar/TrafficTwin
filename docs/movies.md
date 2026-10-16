# Movies: cinematic films of the simulations

Track E turns existing runs into short films, one per simulation mode, plus a showreel. Every
frame is drawn from run outputs (edge bins, FCD trajectories, event and evacuation reports, the
strategist's recommendation); nothing is animated by hand. Every film carries the footer
**synthetic demand, uncalibrated**.

```bash
make movies                          # every film in movies/specs/ + movies/showreel.mp4
make movie FILM=tahlia-street        # one film -> movies/tahlia-street.mp4 (+ .poster.png, .gif, .json)
make movie FILM=city-24h MOVIE_FLAGS="--4k --fps 60 --letterbox"
uv run python -m scripts.movies.preview strategist   # http://127.0.0.1:8765/?cinema=strategist&play=1
uv run python -m scripts.movies.spec validate        # check every spec
```

Needs ffmpeg (`make movies-check` installs it with brew), Google Chrome (the same headless Chrome
the screenshot scripts use; `CHROME_PATH` overrides) and the runs named in the specs under `runs/`
(`TT_RUNS_DIR` overrides). Output goes to `movies/` (git-ignored except `movies/specs/`).

## The films

| film | what it shows | runs (all seed 1) | length |
|---|---|---|---|
| `city-24h` | Tier A weekday baseline as a 24 h time-lapse (02:00 to 02:00): edge speed/limit per 5-minute bin, camera pulls back from the Corniche to the whole city, sun rises and sets over Jeddah | `baseline-weekday-f0.1-s1-e5f1906a-65fac195-65b0f3` (10 % sample, meso) | 40 s |
| `tahlia-street` | Street level (pitch about 60 deg) dolly east along Tahlia Street, then north into the queue on the corridor to Madinah Road; trails, vehicles coloured by speed | `accident_tahlia-tahlia-s1-257eae8d~baseline` (window baseline) | 30 s |
| `incident` | Split screen, window baseline against the crash run (both lanes of the northbound corridor closed 08:10 to 08:30), then the speed difference map; KPIs from the scenario report | `accident_tahlia-tahlia-s1-257eae8d` and its `~baseline` | 32 s |
| `events` | One cut each: heavy rain (difference against the dry baseline), storm flood with the closed flood-site edges, a six-vehicle motorcade on Tahlia Street | `rain_tahlia-…-67ab9112` (+ `~baseline`), `flood_tahlia-…-48d26de0`, `motorcade_tahlia-…-060b80d4` | 36 s |
| `strategist` | The 08:30 ambulance situation: no strategy, then the top 3 ranked options one after another, with the strategist's own reasons and ETAs on the HUD | `runs/strategist/rec-20261016T114454Z-22d13986` (emergency_tahlia_0830); cars around the ambulance from the window baseline | 40 s |
| `evacuation` | Al Hamra waterfront evacuation with a near-first phased release (three bands lighting up), balanced exits, evacuation signal plan and contraflow on three corridors; clearance times from the run | `evac_corniche_hamra_film-tahlia-s1-99ab2558` (run for the film, see below) | 40 s |
| `policy-lab` | Difference mode (blue = faster, red = slower): 30 % remote work against the baseline, staggered schools and the central cordon against their matched controls; KPI values from docs/policies.md | `remote_work_30`, `staggered_schools_60` (+ `--control`), `cordon_center` (+ `--control`), the weekday baseline | 36 s |
| `loop` | Stub: Track D (Loop) is not merged on this branch (no `docs/loop.md`) | - | - |
| `showreel` | All rendered films in order, each after a title card, cut to the spec's `showreel: [start, end]` excerpt, joined with 0.6 s crossfades | the films above | 2 min 55 s |

Stills (poster frames, from the middle of each film):

| | |
|---|---|
| ![city-24h](img/movies/city-24h.jpg) | ![tahlia-street](img/movies/tahlia-street.jpg) |
| ![incident](img/movies/incident.jpg) | ![events](img/movies/events.jpg) |
| ![strategist](img/movies/strategist.jpg) | ![evacuation](img/movies/evacuation.jpg) |
| ![policy-lab](img/movies/policy-lab.jpg) | |

### What the films do and do not show

- **Incident.** `accident_tahlia` closes the whole edge, so affected drivers re-route (A-event-003).
  The run has no long queue at the crash: the extra delay (+5.6 s per vehicle, +5.7 %) shows up on
  the detours and later in the hour. The film shows that; it does not draw a shockwave the run
  does not contain.
- **Strategist.** The what-if runs record the ambulance's time on every route edge, not its
  trajectory. The film moves the ambulance along each edge over exactly that time (A-mov-008), so
  the ETAs on screen are the runs' own; the cars around it come from the window baseline (the
  what-ifs saved no FCD) and the crash marker is the closed lane of the snapshot.
- **Evacuation.** The M7 runs in `runs/` are "as written" (simultaneous release, no contraflow).
  For the film, one window run was added with the strategist's `near_first_full` candidate written
  into a copy of the scenario (`movies/specs/scenarios/evac_corniche_hamra_film.yaml`, same zone,
  crowd, timing and seed):
  `uv run python -m sim.events.evacuation run --scenario movies/specs/scenarios/evac_corniche_hamra_film.yaml --seed 1`
  (about 5 min). Release bands are drawn as hulls of where each band's evacuees start, lit from the
  band's first departure in the FCD.
- **Policy lab.** Edge colours are the policy run minus its comparison run, per 5-minute bin. The
  KPI numbers are copied from the docs/policies.md results table (matched controls where the
  policy re-routes baseline vehicles, TA-018), never the raw unmatched deltas.
- **Tier B clock.** Window runs start at t = 0; the HUD shows t = 0 as 08:00 (A-mov-007), as the
  strategist scenario does.

## How it works

```mermaid
flowchart LR
  spec[movies/specs/film.yaml] --> plan[camera.py: frame plan]
  runs[(runs/: edge bins, FCD, reports, recommendation)] --> bundle[bundle.py]
  pbf[(data/osm PBF)] --> basemap[basemap.py: buildings, water, sea]
  plan --> bundle
  basemap --> bundle
  sun[sun.py: NOAA sun] --> bundle
  bundle --> files[(runs/movies/film/bundle)]
  files --> server[127.0.0.1 static server + web/dist]
  server --> chrome[headless Chrome: ?cinema=film]
  driver[web/scripts/cinema.mjs] -->|renderFrame i, screenshot| chrome
  chrome --> png[(frames, one chunk at a time)]
  png --> ffmpeg[ffmpeg: H.264 chunks, concat]
  ffmpeg --> out[movies/film.mp4, .poster.png, .gif, .json]
```

1. **Plan** (`scripts/movies/camera.py`). Frame i is at film time i / fps. Each frame gets its shot,
   camera (lon, lat, zoom, pitch, bearing) and simulated time from the shot's keyframes.
2. **Bundle** (`scripts/movies/bundle.py`). Everything the browser draws is precomputed into
   `runs/movies/<film>/bundle/`: road geometry (`roads.bin`), edge metric per 5-minute bin as
   uint8 (`heat-<source>.bin`, via the API's bin cache), vehicle paths for TripsLayer
   (`trips-<source>.bin`, from the FCD Parquet through the API's normaliser), overlays (events,
   closures, evacuation zone, exits, release bands, contraflow corridors, strategist routes),
   the basemap, and `frames.json` with, per frame: camera, sim time, sun light (NOAA position for
   Jeddah, A-mov-003), HUD clock, KPI values and fades. Runs are read only
   (`TT_RUNS_READONLY=1`; conversions go to `runs/_viewer-cache/`).
3. **Basemap** (`scripts/movies/basemap.py`). osmium cuts the camera's bounding box out of the
   Geofabrik PBF in `data/osm/`; buildings get `height`, else `building:levels` x 3.2 m, else 6 m
   (A-mov-001/002); the sea is built by polygonizing the coastline against the box (OSM coastlines
   keep land on the left) and continued past the box so pitched views show no edge. Cached per box
   in `runs/movies/_basemap/`. No tile server, no API key.
4. **Render** (`web/src/cinema/`, `?cinema=<film>`). A plain deck.gl `Deck` (no MapLibre, no React)
   with water, road base, edge heat with an additive glow, 3D buildings lit by a `LightingEffect`
   (ambient + a directional sun from the bundle), overlays, TripsLayer trails and vehicle heads
   (emergency vehicles pulse red/blue by frame index). The HUD is HTML: title card, caption and
   detail, clock, up to three KPIs counting up, legend, split labels, the footer. No wall-clock
   time and no randomness: `window.__cinema.renderFrame(i)` resolves after deck.gl has drawn
   frame i and the HUD shows it. The normal viewer is untouched (`main.tsx` only branches on
   `?cinema=`).
5. **Encode** (`scripts/movies/render.py`). `web/scripts/cinema.mjs` (puppeteer-core, as the
   screenshot scripts) steps frames into `runs/movies/<film>/frames/` in chunks of 150; each chunk
   is encoded with libx264 (CRF 18, yuv420p, bitexact flags) and its PNGs deleted, so at most one
   chunk is on disk; the chunks are joined without re-encoding. Then the poster (middle frame of
   the shot at the film's midpoint, clear of cuts), a GIF preview (palette, 10 fps, exactly 6 s, at most 3 MB) and `movies/<film>.json` (sizes, frame hashes,
   peak browser RSS, peak disk, timings, the GPU used).
6. **Showreel** (`scripts/movies/showreel.py`). Title cards are drawn with Pillow over the blurred
   poster (Homebrew's ffmpeg has no `drawtext`); each film is cut to its `showreel` excerpt; films and
   cards are joined with `xfade` crossfades. `make movies-docs` exports the README GIFs (10 fps, at
   most 360 px wide, narrower when needed to stay <= 1.2 MB) and JPEG stills to `docs/img/movies/`.

### Determinism

Same spec + same runs give the same bundle (`bundle/hashes.json`) and the same frames: the render
clock is the frame index, the bundle is fixed, layers are a pure function of (bundle, frame). Each
render records the SHA-256 of the first, middle and last frame free of any fade (no black or
half-black frames); the smoke test renders frames 100-110 of `tahlia-street` (past the title
card) twice at 640x360 and compares the three hashes. Frames are bit-identical on one machine and GPU; another GPU or Chrome
version can differ in the last bits of anti-aliasing (not verified).

## Spec schema

```yaml
film: tahlia-street          # = file name, [a-z0-9-]
title: Tahlia Street, morning peak
subtitle: Tier B microscopic window, every vehicle simulated at 1 s
duration_s: 30               # must equal the sum of the shot durations
date: 2026-10-18             # sun model date (default)
clock_t0: "08:00"            # local time of sim t = 0 (Tier B windows); omit for Tier A (t = seconds of day)
tier: B                      # A (city, meso) | B (window, micro): HUD tier line
title_card_s: 2.5            # title card over the first seconds (0 = none)
showreel: [2.5, 24.5]        # excerpt used in the showreel
basemap: {bbox: null, margin_deg: 0.01, buildings: true, water: true, road_classes: all}
sources:                     # named data sources used by the shots
  base: {run: "accident_tahlia-tahlia-s1-257eae8d~baseline"}         # any run id the API lists
  r1: {strategist: rec-..., candidate: "A:reroute+rescue_lane", background: "<run id>"}
shots:
  - id: dolly
    duration_s: 30
    layers:
      heat: base             # edge colour source (speed / limit by default)
      compare: null          # with mode: diff -> heat minus compare (blue relief, red worse)
      mode: single           # single | diff | split
      split: null            # [left, right] sources (heat + vehicles per half)
      metric: speed_rel      # speed_rel | delay_s_per_veh | density_veh_km
      trips: base            # vehicle trajectories (Tier B)
      color_by: speed        # speed | class (car, truck, bus, emergency, convoy, evacuee)
      overlays: []           # events, closures, zone, exits, phases, contraflow, routes
      route_source: null     # strategist source whose route glows
      outline: null          # extra polygon, e.g. a policy cordon
      buildings: true
    camera:                  # keyframes; t = 0 first, strictly increasing
      - {t: 0,  lon: 39.148, lat: 21.549, zoom: 16.9, pitch: 58, bearing: 74, sim_t: 2700}
      - {t: 30, lon: 39.171, lat: 21.560, zoom: 17.5, pitch: 64, bearing: 340, sim_t: 2880, ease: in_out}
    hud:
      caption: Tahlia Street to the corridor into Madinah Road   # may use {source.fact:fmt}
      detail: Colour = vehicle speed; trails = last 40 simulated seconds
      legend: speed          # speed | diff | class | none
      split_labels: null     # [left, right]
      kpis:                  # up to 3; exactly one of value / series / fact
        - {label: Vehicles in the window, series: running, source: base}       # running | halted | arrived | mean_speed_kmh
        - {label: Mean delay, fact: delta.mean_delay_s.pct, source: crash, unit: "%", decimals: 1, sign: true}
        - {label: Mean delay, value: -9.3, unit: "%", decimals: 1, sign: true}  # literal, counts up over count_s
```

Facts are flattened from the run's normalised report: `summary.*` (scenario KPIs, e.g.
`mean_delay_s.delta_pct`), `delta.*`, `convoy.*`, `result.clearance.*` (evacuation), or for a
strategist source the candidate's result and option (`travel_time_s`, `vs_no_strategy_s`,
`label`, `rank`, `reason`, `title`). A missing fact fails the bundle; it is never filled in.

## Camera-path cookbook

Easing names the motion of the segment that ends at a keyframe (`linear`, `in`, `out`, `in_out`,
`hold`). Position moves in Web Mercator, zoom linearly, bearing along the shorter arc. The sim
clock is linear between keyframes that set `sim_t` and held outside them, so the time-lapse rate
is constant within a segment: rate = (sim_t1 - sim_t0) / (t1 - t0).

- **Fly-in**: zoom 11 -> 15.5 and pitch 20 -> 55 over 6-8 s, `ease: in_out`, a little bearing
  (10-20 deg) so the buildings turn.
- **Slow orbit**: keep lon/lat, change bearing by 40-90 deg over 15-20 s, `linear` or `in_out`;
  pitch 45-60.
- **Dolly along a corridor**: put each keyframe on the road's centreline (read it from the edge
  geometry, `api.edges` or the viewer), bearing = the road's direction (atan2 of east and north
  offsets), pitch 55-65, zoom 16.5-17.5. A 4-8x time-lapse keeps vehicles readable.
- **Pull-back reveal**: start at zoom 13.5-14 with pitch 55-60, end at zoom 10-10.5 (whole city at
  1080p) with pitch 30-35; long `in_out` segments.
- **Split screen**: `mode: split` draws the two sources side by side with the same camera; keep
  the subject in the middle of each half (zoom about 0.5 lower than a full-frame shot).
- Check a spec before rendering: `uv run python -m scripts.movies.preview <film>` and open
  `?cinema=<film>&play=1`, or render a few frames: `--frames 300:310 --keep-frames`.

## Adding a film

1. Make sure its runs are listed by the API (`uv run python -m api.ingest <run>` or just
   `GET /api/runs`). If a run is missing, produce it with its documented demo command, one SUMO
   run at a time (never a city baseline or the 25 %/100 % population).
2. Write `movies/specs/<film>.yaml` (schema above), add the name to `movies/specs/order.yaml`.
3. `uv run python -m scripts.movies.spec validate`, preview, then `make movie FILM=<film>`.
4. Register any new display assumption in `scripts/movies/settings.yaml` and
   `docs/assumptions-trackE.md` (`A-mov-NNN`).

## Performance (M3 Pro, 1920x1080, 30 fps)

Budgets: browser at most 2 GB RSS, at most 1 GB per film on disk during the render (bundle plus one
chunk of 150 PNG frames), no frames left behind. Measured on the final full render of 16 Oct 2026 (`make movies`)
(`movies/<film>.json`; hardware WebGL, ANGLE Metal on the Apple M3 Pro; another agent was
simulating in parallel):

| film | size | frames | duration | MP4 | GIF | per frame | total | browser RSS max | disk max |
|---|---|---|---|---|---|---|---|---|---|
| `city-24h` | 1920x1080 | 1200 | 40.00 s | 85.4 MB | 2.49 MB | 0.16 s | 253 s | 1133 MB | 278 MB |
| `tahlia-street` | 1920x1080 | 900 | 30.00 s | 21.6 MB | 2.83 MB | 0.12 s | 154 s | 1009 MB | 97 MB |
| `incident` | 1920x1080 | 960 | 32.00 s | 30.1 MB | 2.25 MB | 0.14 s | 180 s | 1119 MB | 152 MB |
| `events` | 1920x1080 | 1080 | 36.00 s | 37.0 MB | 2.19 MB | 0.13 s | 197 s | 1036 MB | 158 MB |
| `strategist` | 1920x1080 | 1200 | 40.00 s | 28.1 MB | 2.43 MB | 0.13 s | 205 s | 1134 MB | 119 MB |
| `evacuation` | 1920x1080 | 1200 | 40.00 s | 49.0 MB | 2.42 MB | 0.18 s | 269 s | 1216 MB | 195 MB |
| `policy-lab` | 1920x1080 | 1080 | 36.00 s | 41.2 MB | 2.20 MB | 0.17 s | 234 s | 1475 MB | 241 MB |
| `showreel` | 1920x1080 | 5241 | 174.7 s | 173.5 MB | 2.60 MB | - | about 3 min | - | - |

"per frame" is draw + screenshot; "total" adds the bundle, chunk encoding, concat and GIF. All
seven films render in about 25 minutes; the bundles take 1-10 s each (the first build of a
policy run's edge bins takes longer). `--4k` quadruples the pixels (not measured).

## Licences and credits

Map data © OpenStreetMap contributors (ODbL), simulated with Eclipse SUMO (EPL-2.0); rendering with
deck.gl (MIT), encoding with FFmpeg (LGPL/GPL, not bundled). The footer of every film carries the
OSM attribution and the synthetic label.
