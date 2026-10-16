# TrafficTwin Jeddah: one-command entry points. Everything is synthetic demand, uncalibrated.
#
#   make demo        setup + city network (unless CITY=0) + demo runs + API and viewer on :5173
#   make city        city network + 10 % weekday 24 h baseline (long: about 2 h uncached)
#   make test        ruff + pytest (demo window only, about 3 min)
#   make stop        stop servers started with `./run_app.sh --detach`
#   make movies      render every film in movies/specs/ + the showreel (needs ffmpeg, Chrome)
#   make movie FILM=tahlia-street   render one film to movies/<film>.mp4
#
# Variables: CITY=0 skips the 243 MB OSM download and the Tier A smoke; SEED=1; SAMPLE=0.10;
# DETACH=1 leaves the servers running in the background (used by the screenshot proof).

SHELL := /bin/bash
SEED ?= 1
SAMPLE ?= 0.10
CITY ?= 1
DETACH ?= 0
UV := uv
CITY_NET := data/jeddah/jeddah.net.xml
M2_NET := data/jeddah/jeddah.m2.net.xml

.PHONY: demo setup city-net demo-runs ingest serve city city-baseline test screenshots stop clean-demo \
	movies movie showreel movies-check

demo: setup $(if $(filter 1,$(CITY)),city-net) demo-runs ingest serve

setup:
	@command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/ (brew install uv)"; exit 1; }
	@command -v npm >/dev/null || { echo "node/npm is required (brew install node)"; exit 1; }
	$(UV) python install 3.12
	$(UV) sync --frozen
	@$(MAKE) --no-print-directory web/node_modules/.package-lock.json

# npm ci only when the lockfile changed (it wipes node_modules, even under a running Vite server)
web/node_modules/.package-lock.json: web/package-lock.json
	cd web && npm ci --include=dev --no-audit --no-fund

# Jeddah network (M1): downloads the Geofabrik GCC extract on first run, clips, netconvert, fixes.
city-net: $(CITY_NET)
$(CITY_NET):
	@command -v osmium >/dev/null || { \
	  if command -v brew >/dev/null; then brew install osmium-tool; \
	  else echo "osmium-tool is required (apt install osmium-tool)"; exit 1; fi; }
	$(UV) run python -m sim.network.build_city

demo-runs:
	$(UV) run python -m sim.demo --seed $(SEED)

ingest:
	$(UV) run python -m api.ingest --all

serve:
	./run_app.sh $(if $(filter 1,$(DETACH)),--detach)

# Long-running (documented in README): the M2 network variant and the weekday baseline.
ZONES := data/population/zones/zones.json
city: city-net $(M2_NET) $(ZONES) city-baseline
$(M2_NET): $(CITY_NET)
	$(UV) run python -m sim.network.build_city --config sim/population/config/network-m2.yaml \
	  --out $(M2_NET) --no-side-outputs
$(ZONES): $(M2_NET)
	$(UV) run python -m sim.population.zones
city-baseline: $(M2_NET) $(ZONES)
	mkdir -p logs
	set -o pipefail; $(UV) run python -m sim.runner --baseline --daytype weekday --sample $(SAMPLE) --seed $(SEED) \
	  --gzip 2>&1 | tee logs/city-baseline.log

test:
	$(UV) run ruff check . && $(UV) run ruff format --check . && $(UV) run pytest -q
	cd web && npm run typecheck

# Headless Chrome screenshots of the running viewer (docs/img/final-*.png); needs `make demo DETACH=1`.
screenshots:
	cd web && node scripts/final-shots.mjs

stop:
	@if [[ -f logs/app.pids ]]; then kill $$(cat logs/app.pids) 2>/dev/null || true; rm -f logs/app.pids; echo stopped; \
	else echo "no logs/app.pids (nothing started with --detach)"; fi

clean-demo:
	rm -rf runs/demo-manifest.json data/demo-cache

# Cinematic films of existing runs (Track E, docs/movies.md). One film at a time; frames are
# deleted after encoding. MOVIE_FLAGS passes options through (e.g. --4k, --fps 60, --letterbox).
FILM ?= tahlia-street
MOVIE_FLAGS ?=
movies-check:
	@command -v ffmpeg >/dev/null || { \
	  if command -v brew >/dev/null; then brew install ffmpeg; \
	  else echo "ffmpeg is required (apt install ffmpeg)"; exit 1; fi; }
	@$(MAKE) --no-print-directory web/node_modules/.package-lock.json
movie: movies-check
	mkdir -p logs
	set -o pipefail; $(UV) run python -m scripts.movies.render $(FILM) $(MOVIE_FLAGS) 2>&1 | tee logs/movie-$(FILM).log
movies: movies-check
	mkdir -p logs
	set -o pipefail; $(UV) run python -m scripts.movies.render --all $(MOVIE_FLAGS) 2>&1 | tee logs/movies.log
	$(UV) run python -m scripts.movies.showreel
showreel:
	$(UV) run python -m scripts.movies.showreel
