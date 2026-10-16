# Contract: run outputs (`runs/<run_id>/`) and the viewer API

Version 1 (M3, 2026-10-16). Owner: Track C. Producers: `sim.runner` (Tracks A and B), `strategist/`
(Track B). Consumer: `api/` (FastAPI, file-backed) and `web/` (viewer). All results are
**synthetic demand, uncalibrated**; every JSON file carries `"label": "synthetic demand, uncalibrated"`.

The API reads everything **defensively**: a missing optional file means "not available" (HTTP 404
with `{"detail": "...not available"}`), never a server error. Unknown extra keys are kept and passed
through. Files a producer does not write yet can be derived by `python -m api.ingest`.

## 1. Directory layout

| file | required | written by | read by API as |
|---|---|---|---|
| `meta.json` | yes | runner | run list, run metadata, network lookup |
| `metrics.json` | no | runner (M2+) | KPIs; derived from `meta.json["result"]` when absent |
| `edgedata.parquet` | no (Tier A and B) | runner or `api.ingest` from `edgedata.xml` | 5-minute edge bins |
| `edgedata.xml` | no | SUMO `edgeData` (`freq=300`) | input to `api.ingest` only |
| `fcd.parquet` | no (Tier B only) | runner or `api.ingest` from `fcd.xml` | trajectories |
| `fcd.xml` | no | SUMO `--fcd-output --fcd-output.geo true` (Tier B only) | input to `api.ingest` only |
| `policy_report.json` | no | policy lab (Track A, M4) | policy report + district choropleth |
| `scenario_report.json` | no | events (Track B, M5) | scenario report + event/closure overlays |
| `recommendations.json` | no | strategist (Track B, M6) | strategist panel |
| `decisions.jsonl` | no | API approve endpoint (and strategist) | decision log, append-only |

A directory under `runs/` without a readable `meta.json` is skipped. Directories starting with `_`
or `.` are ignored.

## 2. `meta.json`
Already written by `sim.runner` (M1). Fields the API relies on:

| key | type | note |
|---|---|---|
| `run_id` | str | equals the directory name |
| `label` | str | "synthetic demand, uncalibrated" |
| `kind` | str | `smoke`, `baseline`, `policy`, `scenario`, `strategist`, `evacuation` |
| `tier` | `"A"` or `"B"` | |
| `mode` | `"meso"` or `"micro"` | |
| `seed`, `config_hash`, `network_hash`, `population_hash`, `sumo_version` | | determinism |
| `network` | str | repo-relative path to the `.net.xml`; the edge index is built from it |
| `sim_seconds` | int | simulated span |

Optional keys (new in v1; producers should add them when they apply):
`begin_s` (int, default 0), `baseline_run_id` (str; default comparison run for difference mode),
`policy_id`, `scenario_id`, `window` (Tier B window name), `edgedata_freq_s` (default 300),
`day_type`, `sample_fraction`.

## 3. `metrics.json`
```json
{"label": "synthetic demand, uncalibrated", "run_id": "...",
 "metrics": {"vkt": {"value": 1.2e6, "unit": "veh-km"}, "mean_speed": {"value": 22.7, "unit": "m/s"}}}
```
When absent the API returns `meta.json["result"]` reshaped into the same form (unit `""` when unknown).

## 4. `edgedata.parquet` (5-minute edge bins)
One row per (bin, edge) with data (SUMO `excludeEmpty`). Sorted by `bin_begin_s`, then `edge_id`.

| column | arrow type | unit | from SUMO `edgeData` |
|---|---|---|---|
| `bin_begin_s` | int32 | s | `interval@begin` |
| `bin_end_s` | int32 | s | `interval@end` |
| `edge_id` | dictionary<string> | | `edge@id` |
| `speed_ms` | float32 | m/s | `speed` (NaN when absent) |
| `speed_rel` | float32 | - | `speedRelative` (speed / allowed speed) |
| `density_veh_km` | float32 | veh/km | `density` |
| `occupancy_pct` | float32 | % | `occupancy` |
| `flow_veh_h` | float32 | veh/h | `flow` (meso and newer micro); else `entered * 3600 / bin` |
| `entered` | int32 | veh | `entered` |
| `left` | int32 | veh | `left` |
| `sampled_s` | float32 | veh-s | `sampledSeconds` |
| `traveltime_s` | float32 | s | `traveltime` |
| `time_loss_s` | float32 | s | `timeLoss` (summed over vehicles in the bin) |
| `waiting_s` | float32 | s | `waitingTime` |

Bin width is 300 s (`meta.edgedata_freq_s`). Edge ids are the network's edge ids (Tier B windows
are cut from the city net, so their ids match Tier A).

## 5. `fcd.parquet` (Tier B trajectories; never Tier A)

| column | arrow type | unit |
|---|---|---|
| `time_s` | float32 | s |
| `vehicle_id` | dictionary<string> | |
| `vtype` | dictionary<string> | SUMO vType id |
| `lon`, `lat` | float64 | WGS84 |
| `speed_ms` | float32 | m/s |
| `angle_deg` | float32 | degrees, SUMO convention |

Sorted by `vehicle_id`, then `time_s`. Default FCD period 1 s.

## 6. `policy_report.json`
```json
{"label": "...", "run_id": "...", "baseline_run_id": "...",
 "policy": {"id": "remote-work-20", "name": "Remote work 20 %", "file": "sim/policies/remote_work.yaml"},
 "summary": {"vkt": {"baseline": 1.0, "policy": 0.9, "delta_pct": -10.0, "unit": "veh-km"}},
 "districts": [{"district_id": "r19268635", "name_en": "Ar Rayah",
                "metrics": {"mean_speed_delta_pct": 3.1, "vkt_delta_pct": -8.2}}],
 "assumptions": ["A-pop-001"]}
```
`district_id` = `osm_id` in `data/jeddah/districts.geojson`. The viewer's choropleth uses
`districts[].metrics[<metric>]`. When no policy report exists the API computes
`mean_speed_delta_pct` per district from the edge bins of the run and its comparison run (§9).

## 7. `scenario_report.json`
```json
{"label": "...", "run_id": "...", "baseline_run_id": "...",
 "scenario": {"id": "accident-tahlia", "name": "...", "fictional": true},
 "events": [{"id": "ev1", "type": "accident", "begin_s": 1800, "end_s": 3000,
             "edges": ["123#0"], "geometry": {"type": "Point", "coordinates": [39.157, 21.55]},
             "description": "two lanes blocked"}],
 "closures": [{"id": "cl1", "edges": ["456#1"], "begin_s": 1800, "end_s": 3600, "reason": "flood"}],
 "summary": {"delay_veh_h": {"baseline": 10, "scenario": 25, "delta_pct": 150, "unit": "veh-h"}}}
```
`type` is one of `accident`, `rain`, `flood`, `motorcade`, `closure`, `evacuation`, `other`.
`geometry` (GeoJSON, lon/lat) is optional; without it the overlay draws the listed edges. Real-city
emergency scenarios stay private (PROJECT.md section 11); public examples are demo-window and fictional.

## 8. `recommendations.json` and `decisions.jsonl`
```json
{"label": "...", "run_id": "...", "incident_id": "ev1", "generated_at": "2026-10-16T02:00:00Z",
 "options": [{"option_id": "opt-1", "rank": 1, "title": "Reroute via Prince Sultan Road",
              "action_class": "high_impact", "requires_approval": true, "score": 0.82,
              "explanation": "plain language ...", "effects": {"delay_veh_h_delta_pct": -35.0},
              "actions": [{"type": "reroute", "edges": ["..."]}]}]}
```
`action_class` is `advisory` or `high_impact`; high-impact options always require approval.

`POST /api/runs/{run_id}/recommendations/{option_id}/decision` appends one line to `decisions.jsonl`:
```json
{"ts": "2026-10-16T02:01:00Z", "run_id": "...", "incident_id": "ev1", "option_id": "opt-1",
 "decision": "approved", "operator": "duty-officer", "note": "", "label": "...",
 "prev_hash": "<hash of previous line or 64 zeros>", "hash": "<sha256>"}
```
`hash` = SHA-256 hex of the canonical JSON (sorted keys, no spaces, UTF-8) of the entry without
`hash`. Lines are never rewritten. The strategist's own decision log (Track B) must use the same chain
rule so both writers can share the file. Simulation and decision support only: approving logs the
decision, it never actuates anything.

## 9. API (FastAPI, `api.main:app`, port 8000)

| method | path | returns |
|---|---|---|
| GET | `/health` | `{"status": "ok", "label": ...}` |
| GET | `/api/runs` | list of run summaries: `run_id, kind, tier, mode, seed, network_hash, sim_seconds, label, baseline_run_id, has{edgedata,fcd,policy_report,scenario_report,recommendations,decisions}` |
| GET | `/api/runs/{id}` | `meta.json` |
| GET | `/api/runs/{id}/metrics` | §3 |
| GET | `/api/runs/{id}/bins` | `{"bin_s":300,"begin_s":0,"n_bins":12,"n_edges":156126,"network_hash":"...","metrics":[...],"stats":{metric:{p5,p50,p95}}}` |
| GET | `/api/runs/{id}/bins/{i}?metric=speed_rel` | binary: Float32 LE `[n_edges]`, aligned to the network edge index; NaN = no data |
| GET | `/api/runs/{id}/district-effects?baseline={id}&metric=mean_speed_delta_pct` | `{"source":"policy_report"\|"computed","metric":...,"unit":"%","districts":[{"district_id","name_en","value"}]}` |
| GET | `/api/runs/{id}/trajectories?begin=&end=&step=` | TripsLayer JSON (below); Tier B only |
| GET | `/api/runs/{id}/policy-report` | §6 |
| GET | `/api/runs/{id}/scenario-report` | §7 |
| GET | `/api/runs/{id}/recommendations` | §8 |
| POST | `/api/runs/{id}/recommendations/{option_id}/decision` | body `{"decision":"approved"\|"rejected","operator":str,"note":str}`; returns the logged entry |
| GET | `/api/runs/{id}/decisions` | list of logged entries |
| GET | `/api/networks/{network_hash}/edges.bin` | binary edge geometry (below) |
| GET | `/api/networks/{network_hash}/edges.json` | `{"edge_ids":[...],"names":[...],"types":[...],"lanes":[...],"speed_kmh":[...]}` in index order |
| GET | `/api/geo/districts` | districts GeoJSON (`data/jeddah/districts.geojson`) |
| GET | `/api/geo/buildings?bbox=w,s,e,n` | buildings GeoJSON with `height_m`; optional bbox filter |
| POST | `/api/jobs` | body `{"kind":"smoke","tier":"A"\|"B","seed":int,"end":int?,"period":float?,"fcd":bool?}` -> `{"job_id"}` |
| GET | `/api/jobs/{job_id}` | `{"job_id","status":"running"\|"done"\|"failed","run_id","returncode"}` |
| GET | `/api/jobs/{job_id}/events` | Server-Sent Events: `event: log` (one log line), `event: status`, final `event: done` with `{"status","run_id"}` |

Bin metrics: `speed_ms`, `speed_kmh`, `speed_rel`, `density_veh_km`, `occupancy_pct`, `flow_veh_h`,
`delay_s_per_veh` (= `time_loss_s / entered`, NaN when `entered` is 0), `entered`.
Difference mode is computed in the browser (scenario bin minus baseline bin); both runs must share
`network_hash`.

Edge index: the order of non-internal edges in the run's `.net.xml` (the same order as
`python -m sim.network.netinfo edges-geojson`). `edges.bin` layout (little endian):

| offset | type | content |
|---|---|---|
| 0 | 4 bytes | magic `TTE1` |
| 4 | uint32 | `n_edges` |
| 8 | uint32 | `n_points` |
| 12 | uint32 `[n_edges + 1]` | start index of each edge's path in the point array |
| ... | float32 `[2 * n_points]` | lon, lat pairs |

The browser builds a deck.gl `PathLayer` with binary attributes (`startIndices` + `getPath` buffer);
colours are a `Uint8` RGBA buffer rebuilt per bin. Measured on the full city (156,126 edges,
434,982 points): `edges.bin` 4.10 MB (2.07 MB gzip), `edges.json` 7.27 MB (0.43 MB gzip); one bin of
one metric 0.62 MB raw (37-44 KB gzip, as most edges are NaN in a 1 h smoke run), so 7.5 MB raw /
about 0.5 MB gzip per simulated hour per metric.

TripsLayer JSON:
```json
{"label": "...", "run_id": "...", "begin_s": 0, "end_s": 3600, "step": 1,
 "vehicles": [{"id": "smoke12", "vtype": "DEFAULT_VEHTYPE",
               "path": [[39.15, 21.55], ...], "timestamps": [12.0, ...], "speeds": [8.1, ...]}]}
```

## 10. Ingest and cache
`python -m api.ingest runs/<run_id>` (or `--all`, `--force`) converts `edgedata.xml` -> `edgedata.parquet`
and `fcd.xml` -> `fcd.parquet` (streaming `iterparse`, Parquet row groups; FCD is sorted by an
external DuckDB sort), builds the edge index for the run's network and the dense bin arrays. The
API calls the same functions lazily on first request (one builder per artefact; concurrent requests
wait). Parquet files are rebuilt when the XML is newer.

Derived caches live under `TT_CACHE_DIR`, default **`<TT_RUNS_DIR>/_viewer-cache`** (that is
`runs/_viewer-cache`; `runs/` is the writable mount in docker-compose, `data/` is read-only). The run
listing ignores it because the name starts with `_`. Deleting the cache is always safe.

| path under the cache | content |
|---|---|
| `<network_hash>/edges.bin`, `edges.json` | edge index (§9) |
| `<network_hash>/districts-<districts file hash>/` | edge -> district map (`edge_district.npy`, int32, -1 = none) |
| `runs/<run_id>/<metric>.npy` | float32 `[n_bins, n_edges]`, NaN = no data (read with mmap) |
| `runs/<run_id>/bins.json` | the `/bins` metadata incl. p5/p50/p95 per metric |

`TT_RUNS_DIR`, `TT_CACHE_DIR` and `TT_LOGS_DIR` (job logs, default `logs/`) may be relative; they
resolve against the repo root, so the API runs unchanged from `/app` in the container. `meta.json`
`network` paths are repo-relative for the same reason.

## 11. Implementation notes (v1, API side)
- `/bins/{i}` responses carry headers `X-Metric`, `X-Bin-Begin-S`, `X-Bin-End-S`, `X-N-Edges`,
  `X-Network-Hash`, `X-Label` (exposed via CORS). Out-of-range `i` = 404, unknown metric = 422.
- `/bins` adds `run_id`, `label`, `units`, `rows`, `unmatched_edges` (edgedata ids not in the index).
- `/district-effects`: a `policy_report.json` with the metric wins when no `baseline` is given or the
  given baseline equals the report's; otherwise the computed metric (only `mean_speed_delta_pct`;
  other metrics = 404). No baseline (query or `meta.baseline_run_id`) = 422; runs with different
  `network_hash` = 422. Computed rows add `run_mean_speed_ms` and `baseline_mean_speed_ms`.
  An edge belongs to the district containing its path midpoint (first polygon if they overlap).
- `/trajectories` adds `n_vehicles`; `step >= 1` (422 otherwise); 404 for Tier A runs.
- `/geo/buildings` adds `"attribution"` (OSM, ODbL); bad bbox = 422; header `X-Feature-Count`.
- `/api/jobs`: `fcd: true` with tier A = 422; one job at a time by default (`TT_MAX_JOBS`, 409
  beyond it). The job status JSON also carries `request`, `error`, `created`, `label`. A new run is
  ingested before the job reports `done`. Exit code != 0 (including the runner's teleport gate,
  exit 2) = `failed`, with `run_id` still set when the run directory exists.
- `/metrics` fallback adds `"source": "meta.result"`; units derive from key suffixes (`_ms` m/s,
  `_s` s, `_m` m, `_share`/`_factor` -), else `""`.
- JSON and binary responses are gzip-compressed when the client accepts it (SSE excluded).
