# Network v2: closing the Tier A capacity gap (Track F)

Date: 2026-10-17. Eclipse SUMO 1.28.0, same OSM clip as v1/m2 (`data/osm/jeddah.osm.gz`, hash
b491ff1d; GCC extract of 2026-10-14). All results: **synthetic demand, uncalibrated**. Decisions
TF-nnn are in `docs/status/trackF.md`; assumptions A-net-301/302 in `docs/assumptions-trackF.md`.

## 1. Profiles and hashes

| profile | config | network file | hash | lanes / maxspeed on untagged ways |
|---|---|---|---|---|
| v1 (M1) | `sim/network/config/city.yaml` | `data/jeddah/jeddah.net.xml` | 5b8a19d3a3fd4d59 | SUMO typemap (A-network-003) |
| m2 (Track A) | `sim/population/config/network-m2.yaml` | `data/jeddah/jeddah.m2.net.xml` | e5f1906af7fded33 | judgement overlay (A-net-201) |
| **v2 (default)** | `sim/network/config/city-v2.yaml` | `data/jeddah/jeddah.v2.net.xml` | **ae7645589de321f9** | measured medians (A-net-301/302) |

```
uv run python -m sim.network.build_city                          # v2 (default profile)
uv run python -m sim.network.build_city --network-profile v1     # M1 settings
uv run python -m sim.network.build_city --network-profile m2 --out data/jeddah/jeddah.m2.net.xml --no-side-outputs
```
v1 and m2 rebuilt from their settings into `/tmp` reproduce 5b8a19d3 and e5f1906a byte for byte;
v2 built twice (once with an uncompressed and once with a gzipped pre-pass file) gives ae764558
both times.

| | v1 | m2 | v2 |
|---|---|---|---|
| edges / junctions / TLS | 156,126 / 62,513 / 72 | 155,366 / 61,774 / 74 | 155,663 / 62,136 / 73 |
| lane-km | 20,952.9 | 22,968.2 | 25,410.8 |
| main passenger SCC | 99.10 % | 99.09 % | 99.10 % (154,250 of 155,653; 617 SCCs) |

## 2. Evidence-based lane and speed defaults

`python -m sim.network.lane_defaults stats` exports every highway way of the measured classes from
the clip (osmium), measures its length, and for each class x oneway computes the km-weighted
distribution of **lanes per direction** (oneway: `lanes`; two-way: `lanes:forward`/`backward`,
else `lanes`/2) and of `maxspeed`, over the ways that carry the tag. Output:
`sim/network/types/jeddah-lanes.json` (committed, with the source hash cafede24).

| class x direction | km | tagged km (share) | lanes p25 / p50 / p75 | maxspeed p25 / p50 / p75 (tagged km) | v2 default |
|---|---|---|---|---|---|
| motorway oneway | 450.7 | 172.6 (38 %) | 3 / 4 / 4 | 100 / 100 / 120 (405) | 4 lanes, 100 km/h |
| trunk oneway | 159.2 | 55.3 (35 %) | 3 / 3 / 3 | 90 / 90 / 90 (73) | 3, 90 |
| primary oneway | 863.1 | 251.5 (29 %) | 2 / 3 / 4 | 80 / 80 / 90 (308) | 3, 80 |
| secondary oneway | 1,389.9 | 235.1 (17 %) | 3 / 3 / 3 | 60 / 80 / 90 (152) | 3, 80 |
| tertiary oneway | 1,143.5 | 122.6 (11 %) | 2 / 2 / 3 | 80 / 80 / 80 (75) | 2, 80 |
| motorway_link oneway | 177.2 | 27.4 (15 %) | 2 / 2 / 2 | 60 / 60 / 90 (6.5) | 2, 60 |
| primary_link oneway | 88.1 | 13.6 (15 %) | 1 / 1 / 2 | - | 1, typemap speed |
| secondary / tertiary / primary two-way | 106 / 78 / 3 | 1.4 / 2.1 / 2.0 | (too little) | class median | typemap lanes, 80 km/h |
| trunk_link, secondary_link, tertiary_link | 39 / 38 / 10 | 1.2 / 3.3 / 0.6 | (too little) | - | typemap |

Rules (TF-001, TF-002): a median is used only with >= 5 km of tagged evidence; lanes round half up;
two-way ways are never widened from the dual-carriageway median (undivided roads); minor classes
(residential, unclassified) keep the typemap.

**Mechanism.** A typemap applies one `numLanes` per class to both oneway and two-way ways, so it
cannot express the table. v2 uses a reproducible pre-pass instead: `python -m
sim.network.lane_defaults tag` streams the clipped OSM XML and adds `lanes` (two-way: 2 x per
direction) and `maxspeed` to ways that lack them, marked `traffictwin:defaults=A-net-301;A-net-302`.
Tagged ways are untouched. On the Jeddah clip it tags 4,110 ways with lanes and 4,275 with
maxspeed (81,602 ways read). `build_city` runs it when the config has a `lane_defaults:` block
(`data/osm/jeddah.v2.osm.gz`, gzip written with mtime 0 so the file hash is stable).

**Held-out cross-check** (`python -m sim.network.lane_defaults crosscheck --imagery-dir
<lane-audit data>/data/imagery --sets v2-holdout,holdout,v2-calibration,calibration`; reads the
existing lane-audit results, no imagery calls; `sim/network/types/jeddah-lanes-crosscheck.json`).
The lane-audit ways are tagged ways, so the question is: had this way been untagged, would the
default have matched its tag?

| class | ways | v2 default = tag | within 1 lane | SUMO typemap = tag | m2 overlay = tag | v2 default = imagery read |
|---|---|---|---|---|---|---|
| motorway oneway | 42 | 62 % | 98 % | 0 % | 36 % | 45 % (40 reads) |
| trunk oneway | 38 | 89 % | 95 % | 5 % | 89 % | 65 % (34) |
| primary oneway | 23 | 39 % | 74 % | 17 % | 39 % | 57 % (23) |
| secondary oneway | 25 | 60 % | 96 % | 4 % | 28 % | 68 % (25) |

No class disagrees strongly, so the tagged-OSM median stays (TF-003). The imagery reads failed
their own 80 % gate (docs/lane-audit.md) and are a weak second opinion; where they differ, they
read motorways as 3 lanes. Caveat: the sample overlaps the ways the medians are computed from, and
mappers tag bigger roads more often, so the medians may overstate untagged ways.

## 3. Junctions and ramps: peak probe

The 1-hour random-trip smoke (0.14 % teleports on v1) cannot separate variants. `python -m
sim.network.probe` (TF-004) takes the m2 baseline's own vehicle trips departing 05:00-09:00
(91,392 sampled vehicles, capacity-scaled vTypes), routes them once at free flow on the candidate
network and simulates 05:00-10:00 in meso with the baseline's Tier A options (limited junction
control, 120 s teleport time, tau x10). Teleports are counted per vehicle as in the baseline's
`teleport_share`. Free-flow routes load harder than the 3-step assignment (m2: 57.3 % in the probe,
50.5 % in its 24 h baseline), so the probe is a comparison, not a forecast.

| variant | change vs v2a | hash | teleports | mean speed | time loss | on junction internals / guessed ramps |
|---|---|---|---|---|---|---|
| m2 (control) | Track A overlay | e5f1906a | 57.3 % | 34.3 km/h | 1,608 s | 21 % / 18 % |
| **v2a = v2** | measured lanes + maxspeed, v1 netconvert options | ae764558 | **40.0 %** | 43.3 | 1,204 | 15 % / 19 % |
| v2h | `--junctions.join-dist 30` | 80b9c370 | 40.3 % | 43.7 | 1,188 | 15 % / 19 % |
| v2i | `--no-internal-links` | 08dbc7a4 | 41.5 % | 45.0 | 1,061 | 0 % / 18 % |
| v2b | `--ramps.no-split` | bf84c83a | 48.0 % | 41.8 | 1,226 | 17 % / 0 % |
| v2c | no-split + join-dist 30 | ebc9d3a3 | 48.6 % | 41.9 | 1,248 | 17 % / 0 % |
| v2d | no-split + no internal links | 290ec69b | 51.4 % | 43.5 | 1,082 | 0 % / 0 % |

Decisions: ramp splitting stays (TF-005: the 95-m ramp edges are where teleports are counted, but
they carry the extra lane; without them the diverge has fewer lanes and teleports rise);
`--no-internal-links` is rejected (TF-006: it removes junction-internal teleports by moving them
upstream, and Tier B windows need internal links); a 30-m join distance is neutral and rejected
(TF-007, it would also change more edge ids). `--tls.guess` was not tried: the meso TLS penalty
adds delay at every guessed signal and there is no signal inventory to check a count against
(docs/network-qa.md §4); the OSM signals stay. Roundabout guessing and turn lanes are unchanged
(no measurable lever in meso, where lanes are not modelled per movement).

Not completed: the probe of v2j (join-dist 30 + no internal links) was stopped to free the
machine for the city run; both of its parts were neutral or worse on their own.

## 4. City baseline on v2

(filled in after the run)

## 5. What remains

(filled in after the run)
