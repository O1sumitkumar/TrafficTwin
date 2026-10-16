"""Dense per-run, per-metric bin arrays aligned to the network edge index.

Cache layout: <TT_CACHE_DIR>/runs/<run_id>/<metric>.npy (float32 [n_bins, n_edges], NaN = no
data, read with mmap) plus bins.json (metadata and p5/p50/p95 per metric). Arrays are written via
open_memmap so even a 24 h city run is never held in RAM.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from api import settings
from api.edges import load_edge_index
from api.util import atomic_write_json, build_lock, is_stale, read_json

MS_TO_KMH = 3.6  # unit conversion
PERCENTILES = (5, 50, 95)
METRICS: dict[str, str] = {
    "speed_ms": "m/s",
    "speed_kmh": "km/h",
    "speed_rel": "-",
    "density_veh_km": "veh/km",
    "occupancy_pct": "%",
    "flow_veh_h": "veh/h",
    "delay_s_per_veh": "s/veh",
    "entered": "veh",
}
SOURCE_COLUMNS = [
    "bin_begin_s",
    "bin_end_s",
    "edge_id",
    "speed_ms",
    "speed_rel",
    "density_veh_km",
    "occupancy_pct",
    "flow_veh_h",
    "time_loss_s",
    "entered",
]


def bins_dir(run_id: str) -> Path:
    return settings.cache_dir() / "runs" / run_id


def _metric_values(batch: pa.RecordBatch) -> dict[str, np.ndarray]:
    def col(name: str) -> np.ndarray:
        return batch.column(name).to_numpy(zero_copy_only=False).astype(np.float32)

    speed = col("speed_ms")
    entered = col("entered")
    loss = col("time_loss_s")
    with np.errstate(divide="ignore", invalid="ignore"):
        delay = np.where(entered > 0, loss / entered, np.nan).astype(np.float32)
    return {
        "speed_ms": speed,
        "speed_kmh": speed * np.float32(MS_TO_KMH),
        "speed_rel": col("speed_rel"),
        "density_veh_km": col("density_veh_km"),
        "occupancy_pct": col("occupancy_pct"),
        "flow_veh_h": col("flow_veh_h"),
        "delay_s_per_veh": delay,
        "entered": entered,
    }


def _edge_positions(arr: pa.Array, position: dict[str, int]) -> np.ndarray:
    if not pa.types.is_dictionary(arr.type):
        arr = pc.dictionary_encode(arr)
    lookup = np.array([position.get(e, -1) for e in arr.dictionary.to_pylist()], dtype=np.int64)
    idx = arr.indices.to_numpy(zero_copy_only=False)
    return lookup[idx] if len(lookup) else np.full(len(idx), -1, dtype=np.int64)


def _bin_geometry(pf: pq.ParquetFile, meta: dict[str, Any]) -> tuple[int, int]:
    """(bin width, begin) from meta, falling back to the first row of the data."""
    begin = int(meta.get("begin_s", 0))
    width = meta.get("edgedata_freq_s")
    if width is None and pf.metadata.num_rows:
        first = pf.read_row_group(0, columns=["bin_begin_s", "bin_end_s"]).slice(0, 1)
        width = first["bin_end_s"][0].as_py() - first["bin_begin_s"][0].as_py()
    if not width:
        raise ValueError("cannot determine the edgedata bin width")
    return int(width), begin


def build_bins(run: Path, meta: dict[str, Any]) -> dict[str, Any]:
    run_id = run.name
    parquet = run / "edgedata.parquet"
    net = settings.resolve_repo_path(str(meta["network"]))
    index = load_edge_index(net, str(meta["network_hash"]))
    pf = pq.ParquetFile(parquet)
    width, begin = _bin_geometry(pf, meta)
    sim_seconds = int(meta.get("sim_seconds", 0))
    if not sim_seconds and pf.metadata.num_rows:
        ends = pc.max(pq.read_table(parquet, columns=["bin_end_s"])["bin_end_s"]).as_py()
        sim_seconds = int(ends) - begin
    n_bins = max(1, math.ceil(sim_seconds / width))
    n_edges = index.n_edges
    out = bins_dir(run_id)
    out.mkdir(parents=True, exist_ok=True)
    tmp = {m: out / f".{m}.npy.tmp" for m in METRICS}
    arrays = {
        m: np.lib.format.open_memmap(tmp[m], mode="w+", dtype="<f4", shape=(n_bins, n_edges))
        for m in METRICS
    }
    for a in arrays.values():
        a[:] = np.nan
    unmatched: set[str] = set()
    for batch in pf.iter_batches(columns=SOURCE_COLUMNS):
        pos = _edge_positions(batch.column("edge_id"), index.position)
        b = (batch.column("bin_begin_s").to_numpy() - begin) // width
        ok = (pos >= 0) & (b >= 0) & (b < n_bins)
        if not ok.all():
            ids = batch.column("edge_id").to_pylist()
            unmatched.update(ids[i] for i in np.flatnonzero(pos < 0))
        values = _metric_values(batch)
        for m, a in arrays.items():
            a[b[ok], pos[ok]] = values[m][ok]
    stats: dict[str, dict[str, float | None]] = {}
    for m, a in arrays.items():
        a.flush()
        finite = a[np.isfinite(a)]
        if finite.size:
            qs = np.percentile(finite, PERCENTILES)
            stats[m] = {f"p{p}": round(float(q), 4) for p, q in zip(PERCENTILES, qs, strict=True)}
        else:
            stats[m] = {f"p{p}": None for p in PERCENTILES}
        del a
    arrays.clear()
    for m, t in tmp.items():
        t.replace(out / f"{m}.npy")
    info = {
        "run_id": run_id,
        "label": settings.LABEL,
        "bin_s": width,
        "begin_s": begin,
        "n_bins": n_bins,
        "n_edges": n_edges,
        "network_hash": meta["network_hash"],
        "metrics": list(METRICS),
        "units": METRICS,
        "stats": stats,
        "rows": pf.metadata.num_rows,
        "unmatched_edges": len(unmatched),
        "dtype": "float32 little endian; NaN = no data",
    }
    atomic_write_json(out / "bins.json", info)
    _mmaps.clear()
    return info


def ensure_bins(run: Path, meta: dict[str, Any], force: bool = False) -> dict[str, Any]:
    from api.ingest import ensure_edgedata

    parquet = ensure_edgedata(run)
    if parquet is None:
        raise FileNotFoundError("edgedata not available")
    info_path = bins_dir(run.name) / "bins.json"
    if not force and not is_stale(info_path, parquet):
        return read_json(info_path)
    with build_lock(f"bins:{run.name}"):
        if not force and not is_stale(info_path, parquet):
            return read_json(info_path)
        return build_bins(run, meta)


_mmaps: dict[tuple[str, str, float], np.ndarray] = {}


def bin_array(run_id: str, metric: str) -> np.ndarray:
    path = bins_dir(run_id) / f"{metric}.npy"
    key = (run_id, metric, path.stat().st_mtime)  # a rebuild (any process) changes the mtime
    if key not in _mmaps:
        for old in [k for k in _mmaps if k[:2] == key[:2]]:
            del _mmaps[old]
        _mmaps[key] = np.load(path, mmap_mode="r")
    return _mmaps[key]
