"""Convert run outputs for the viewer: edgedata.xml -> edgedata.parquet, fcd.xml -> fcd.parquet,
and build the edge index and the dense bin arrays (contract docs/contracts/run-outputs.md §10).

    python -m api.ingest runs/<run_id>
    python -m api.ingest --all
    python -m api.ingest --all --force

XML is streamed with iterparse (elements cleared as they are consumed) and Parquet is written in
row groups, so memory stays flat whatever the file size.
"""

from __future__ import annotations

import math
import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import typer

from api import settings
from api.runs import iter_runs, read_meta
from api.util import build_lock, is_stale, tmp_path_for

SECONDS_PER_HOUR = 3600  # unit conversion
EDGE_ROW_GROUP = 65_536  # rows buffered before a Parquet row group is written
FCD_ROW_GROUP = 131_072
DUCKDB_MEMORY_LIMIT = "1GB"  # external sort of FCD spills to disk beyond this

DICT_STR = pa.dictionary(pa.int32(), pa.string())
EDGE_SCHEMA = pa.schema(
    [
        ("bin_begin_s", pa.int32()),
        ("bin_end_s", pa.int32()),
        ("edge_id", DICT_STR),
        ("speed_ms", pa.float32()),
        ("speed_rel", pa.float32()),
        ("density_veh_km", pa.float32()),
        ("occupancy_pct", pa.float32()),
        ("flow_veh_h", pa.float32()),
        ("entered", pa.int32()),
        ("left", pa.int32()),
        ("sampled_s", pa.float32()),
        ("traveltime_s", pa.float32()),
        ("time_loss_s", pa.float32()),
        ("waiting_s", pa.float32()),
    ]
)
# parquet column -> SUMO edgeData attribute (floats; NaN when absent)
EDGE_FLOAT_ATTRS = {
    "speed_ms": "speed",
    "speed_rel": "speedRelative",
    "density_veh_km": "density",
    "occupancy_pct": "occupancy",
    "sampled_s": "sampledSeconds",
    "traveltime_s": "traveltime",
    "time_loss_s": "timeLoss",
    "waiting_s": "waitingTime",
}
FCD_SCHEMA = pa.schema(
    [
        ("time_s", pa.float32()),
        ("vehicle_id", DICT_STR),
        ("vtype", DICT_STR),
        ("lon", pa.float64()),
        ("lat", pa.float64()),
        ("speed_ms", pa.float32()),
        ("angle_deg", pa.float32()),
    ]
)

Log = Callable[[str], None]


def _f(value: str | None) -> float:
    return float(value) if value not in (None, "") else math.nan


def _i(value: str | None) -> int:
    return int(float(value)) if value not in (None, "") else 0


def _edge_table(cols: dict[str, list[Any]]) -> pa.Table:
    arrays = []
    for field in EDGE_SCHEMA:
        if field.name == "edge_id":
            arrays.append(pa.array(cols["edge_id"], pa.string()).dictionary_encode())
        else:
            arrays.append(pa.array(cols[field.name], field.type))
    return pa.Table.from_arrays(arrays, schema=EDGE_SCHEMA)


def convert_edgedata(xml: Path, out: Path) -> int:
    """Stream SUMO edgeData XML to Parquet sorted by (bin_begin_s, edge_id); return row count."""
    tmp = tmp_path_for(out)
    rows = 0
    names = [f.name for f in EDGE_SCHEMA]
    buf: dict[str, list[Any]] = {n: [] for n in names}
    interval: list[tuple[str | None, ...]] = []
    wanted = ("id", *EDGE_FLOAT_ATTRS.values(), "entered", "left", "flow")
    begin = end = 0
    root: ET.Element | None = None

    def flush(writer: pq.ParquetWriter) -> None:
        if buf["edge_id"]:
            writer.write_table(_edge_table(buf), row_group_size=EDGE_ROW_GROUP)
            for v in buf.values():
                v.clear()

    with pq.ParquetWriter(tmp, EDGE_SCHEMA, compression="zstd") as writer:
        for event, elem in ET.iterparse(xml, events=("start", "end")):
            if root is None:
                root = elem
                continue
            if event == "start":
                if elem.tag == "interval":
                    begin, end = _i(elem.get("begin")), _i(elem.get("end"))
                continue
            if elem.tag == "edge":
                interval.append(tuple(elem.get(k) for k in wanted))
                elem.clear()
            elif elem.tag == "interval":
                width = end - begin
                interval.sort(key=lambda t: t[0] or "")
                for values in interval:
                    a = dict(zip(wanted, values, strict=True))
                    buf["bin_begin_s"].append(begin)
                    buf["bin_end_s"].append(end)
                    buf["edge_id"].append(a["id"] or "")
                    for col, attr in EDGE_FLOAT_ATTRS.items():
                        buf[col].append(_f(a[attr]))
                    entered = _i(a["entered"])
                    flow = a["flow"]
                    buf["flow_veh_h"].append(
                        _f(flow) if flow is not None else entered * SECONDS_PER_HOUR / width
                    )
                    buf["entered"].append(entered)
                    buf["left"].append(_i(a["left"]))
                    if len(buf["edge_id"]) >= EDGE_ROW_GROUP:
                        flush(writer)
                rows += len(interval)
                interval.clear()
                root.clear()
        flush(writer)
    os.replace(tmp, out)
    return rows


def _fcd_table(cols: dict[str, list[Any]]) -> pa.Table:
    arrays = []
    for field in FCD_SCHEMA:
        if field.type == DICT_STR:
            arrays.append(pa.array(cols[field.name], pa.string()))
        else:
            arrays.append(pa.array(cols[field.name], field.type))
    return pa.Table.from_arrays(arrays, names=FCD_SCHEMA.names)


def convert_fcd(xml: Path, out: Path) -> int:
    """Stream SUMO FCD XML (geo) to Parquet sorted by (vehicle_id, time_s); return row count.

    Pass 1 writes time-ordered row groups to a scratch file; pass 2 sorts them with DuckDB
    (which spills to disk under its memory limit) and streams the result into the final file.
    """
    scratch = out.with_name(f".{out.name}.unsorted.parquet")
    tmp = tmp_path_for(out)
    names = FCD_SCHEMA.names
    buf: dict[str, list[Any]] = {n: [] for n in names}
    plain = pa.schema([(f.name, pa.string() if f.type == DICT_STR else f.type) for f in FCD_SCHEMA])
    rows = 0
    t = math.nan
    root: ET.Element | None = None
    try:
        with pq.ParquetWriter(scratch, plain) as writer:
            for event, elem in ET.iterparse(xml, events=("start", "end")):
                if root is None:
                    root = elem
                    continue
                if event == "start":
                    if elem.tag == "timestep":
                        t = _f(elem.get("time"))
                    continue
                if elem.tag == "vehicle":
                    buf["time_s"].append(t)
                    buf["vehicle_id"].append(elem.get("id", ""))
                    buf["vtype"].append(elem.get("type", ""))
                    buf["lon"].append(_f(elem.get("x")))
                    buf["lat"].append(_f(elem.get("y")))
                    buf["speed_ms"].append(_f(elem.get("speed")))
                    buf["angle_deg"].append(_f(elem.get("angle")))
                    rows += 1
                    elem.clear()
                    if len(buf["time_s"]) >= FCD_ROW_GROUP:
                        writer.write_table(_fcd_table(buf))
                        for v in buf.values():
                            v.clear()
                elif elem.tag == "timestep":
                    root.clear()
            if buf["time_s"]:
                writer.write_table(_fcd_table(buf))
        con = duckdb.connect()
        con.execute(f"SET memory_limit='{DUCKDB_MEMORY_LIMIT}'")
        con.execute("SET preserve_insertion_order=false")
        reader = con.execute(
            "SELECT * FROM read_parquet(?) ORDER BY vehicle_id, time_s", [str(scratch)]
        ).to_arrow_reader(FCD_ROW_GROUP)
        with pq.ParquetWriter(tmp, FCD_SCHEMA, compression="zstd") as writer:
            for batch in reader:
                table = pa.Table.from_batches([batch]).cast(FCD_SCHEMA)
                writer.write_table(table)
        con.close()
        os.replace(tmp, out)
    finally:
        scratch.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
    return rows


def ensure_edgedata(run: Path, force: bool = False) -> Path | None:
    out, xml = run / "edgedata.parquet", run / "edgedata.xml"
    if not force and not is_stale(out, xml):
        return out
    if not xml.exists():
        return out if out.exists() else None
    with build_lock(f"edgedata:{run}"):
        if force or is_stale(out, xml):
            convert_edgedata(xml, out)
    return out


def ensure_fcd(run: Path, force: bool = False) -> Path | None:
    out, xml = run / "fcd.parquet", run / "fcd.xml"
    if not force and not is_stale(out, xml):
        return out
    if not xml.exists():
        return out if out.exists() else None
    with build_lock(f"fcd:{run}"):
        if force or is_stale(out, xml):
            convert_fcd(xml, out)
    return out


def ingest_run(run: Path, force: bool = False, log: Log = print) -> dict[str, Any]:
    """Everything the viewer needs for one run; returns timings and counts."""
    from api.bins import ensure_bins
    from api.edges import ensure_edge_index

    meta = read_meta(run)
    if meta is None:
        raise FileNotFoundError(f"{run}: no readable meta.json")
    report: dict[str, Any] = {"run_id": run.name}
    t0 = time.perf_counter()
    edp = ensure_edgedata(run, force)
    report["edgedata_s"] = round(time.perf_counter() - t0, 2)
    if edp is not None:
        report["edgedata_rows"] = pq.ParquetFile(edp).metadata.num_rows
    log(f"ingest {run.name}: edgedata {report.get('edgedata_rows', 'n/a')} rows")
    if meta.get("tier") == "B":
        t0 = time.perf_counter()
        fcdp = ensure_fcd(run, force)
        report["fcd_s"] = round(time.perf_counter() - t0, 2)
        if fcdp is not None:
            report["fcd_rows"] = pq.ParquetFile(fcdp).metadata.num_rows
        log(f"ingest {run.name}: fcd {report.get('fcd_rows', 'n/a')} rows")
    net, nhash = meta.get("network"), meta.get("network_hash")
    if net and nhash:
        t0 = time.perf_counter()
        ensure_edge_index(settings.resolve_repo_path(str(net)), str(nhash))
        report["edge_index_s"] = round(time.perf_counter() - t0, 2)
        log(f"ingest {run.name}: edge index {nhash} ready")
        if edp is not None:
            t0 = time.perf_counter()
            ensure_bins(run, meta, force=force)
            report["bins_s"] = round(time.perf_counter() - t0, 2)
            log(f"ingest {run.name}: dense bins ready")
    return report


def _resolve_run(arg: str) -> Path:
    path = Path(arg)
    if path.is_dir():
        return path
    candidate = settings.runs_dir() / arg
    if candidate.is_dir():
        return candidate
    raise typer.BadParameter(f"{arg}: not a run directory")


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    run: str | None = typer.Argument(None, help="runs/<run_id> or a run id"),
    all_runs: bool = typer.Option(False, "--all", help="ingest every run under TT_RUNS_DIR"),
    force: bool = typer.Option(False, "--force", help="rebuild even when outputs are fresh"),
) -> None:
    if all_runs == (run is not None):
        raise typer.BadParameter("give exactly one of RUN or --all")
    targets = [p for p, _ in iter_runs()] if all_runs else [_resolve_run(str(run))]
    for target in targets:
        t0 = time.perf_counter()
        report = ingest_run(target, force=force, log=typer.echo)
        report["total_s"] = round(time.perf_counter() - t0, 2)
        typer.echo(f"  {report}")


if __name__ == "__main__":
    app()
