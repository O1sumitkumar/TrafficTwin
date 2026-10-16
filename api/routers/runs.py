"""Run endpoints: list, metadata, metrics, bins, district effects, trajectories, reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from api import settings
from api.bins import METRICS, bin_array, ensure_bins
from api.decisions import LOG_NAME, append_decision, read_entries
from api.districts import COMPUTED_METRIC, computed_effects, report_effects
from api.edges import load_edge_index
from api.ingest import ensure_edgedata, ensure_fcd
from api.runs import (
    iter_runs,
    not_available,
    read_optional_json,
    run_dir,
    run_meta,
    summary,
)
from api.trajectories import trajectories

router = APIRouter(prefix="/api/runs", tags=["runs"])

# meta.json "result" key suffix -> unit, for the metrics fallback
UNIT_SUFFIXES = (
    ("_ms", "m/s"),
    ("_s", "s"),
    ("_seconds", "s"),
    ("_m", "m"),
    ("_share", "-"),
    ("_factor", "-"),
)
BINARY = "application/octet-stream"


def _unit(key: str) -> str:
    for suffix, unit in UNIT_SUFFIXES:
        if key.endswith(suffix):
            return unit
    return ""


def read_optional_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@router.get("")
def list_runs() -> list[dict[str, Any]]:
    return [summary(path, meta) for path, meta in iter_runs()]


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    meta = run_meta(run_id)
    meta.setdefault("label", settings.LABEL)
    return meta


@router.get("/{run_id}/metrics")
def get_metrics(run_id: str) -> dict[str, Any]:
    path = run_dir(run_id) / "metrics.json"
    if path.is_file():
        data = read_optional_json_file(path)
        if data is not None:
            data.setdefault("label", settings.LABEL)
            data.setdefault("source", "metrics.json")
            return data
    meta = run_meta(run_id)
    result = meta.get("result") or {}
    metrics = {
        k: {"value": v, "unit": _unit(k)}
        for k, v in sorted(result.items())
        if isinstance(v, int | float) and not isinstance(v, bool)
    }
    return {
        "label": meta.get("label", settings.LABEL),
        "run_id": run_id,
        "source": "meta.result",
        "metrics": metrics,
    }


def _bins_info(run_id: str) -> dict[str, Any]:
    path = run_dir(run_id)
    meta = run_meta(run_id)
    if not meta.get("network") or not meta.get("network_hash"):
        raise not_available("edge bins (no network in meta.json)")
    try:
        info = ensure_bins(path, meta)
    except FileNotFoundError as exc:
        raise not_available("edge bins") from exc
    return info


@router.get("/{run_id}/bins")
def get_bins(run_id: str) -> dict[str, Any]:
    info = dict(_bins_info(run_id))
    info["label"] = settings.LABEL
    return info


@router.get("/{run_id}/bins/{i}")
def get_bin(run_id: str, i: int, metric: str = "speed_rel") -> Response:
    if metric not in METRICS:
        raise HTTPException(status_code=422, detail=f"unknown metric; one of {list(METRICS)}")
    info = _bins_info(run_id)
    if not 0 <= i < info["n_bins"]:
        raise HTTPException(status_code=404, detail="bin out of range")
    data = bin_array(run_id, metric)[i].tobytes()
    begin = info["begin_s"] + i * info["bin_s"]
    headers = {
        "X-Metric": metric,
        "X-Bin-Begin-S": str(begin),
        "X-Bin-End-S": str(begin + info["bin_s"]),
        "X-N-Edges": str(info["n_edges"]),
        "X-Network-Hash": str(info["network_hash"]),
        "X-Label": settings.LABEL,
    }
    return Response(content=data, media_type=BINARY, headers=headers)


@router.get("/{run_id}/district-effects")
def district_effects(
    run_id: str,
    baseline: str | None = None,
    metric: str = COMPUTED_METRIC,
) -> dict[str, Any]:
    path = run_dir(run_id)
    meta = run_meta(run_id)
    report_path = path / "policy_report.json"
    if report_path.is_file():
        report = read_optional_json_file(report_path) or {}
        if baseline is None or baseline == report.get("baseline_run_id"):
            rows = report_effects(report, metric)
            if rows is not None:
                return {
                    "label": settings.LABEL,
                    "run_id": run_id,
                    "baseline_run_id": report.get("baseline_run_id"),
                    "source": "policy_report",
                    "metric": metric,
                    "unit": "%" if metric.endswith("_pct") else "",
                    "example": bool(report.get("example", False)),
                    "districts": rows,
                }
    if metric != COMPUTED_METRIC:
        raise not_available(f"district metric {metric!r}")
    baseline = baseline or meta.get("baseline_run_id")
    if not baseline:
        raise HTTPException(status_code=422, detail="baseline run required (?baseline=<run_id>)")
    base_meta = run_meta(baseline)
    if base_meta.get("network_hash") != meta.get("network_hash"):
        raise HTTPException(status_code=422, detail="runs do not share a network_hash")
    run_pq, base_pq = ensure_edgedata(path), ensure_edgedata(run_dir(baseline))
    if run_pq is None or base_pq is None:
        raise not_available("edge bins")
    index = load_edge_index(settings.resolve_repo_path(meta["network"]), meta["network_hash"])
    try:
        rows = computed_effects(run_pq, base_pq, index)
    except FileNotFoundError as exc:
        raise not_available("districts") from exc
    return {
        "label": settings.LABEL,
        "run_id": run_id,
        "baseline_run_id": baseline,
        "source": "computed",
        "metric": metric,
        "unit": "%",
        "method": "sampled-seconds-weighted mean speed per district, run vs baseline, all bins",
        "districts": rows,
    }


@router.get("/{run_id}/trajectories")
def get_trajectories(
    run_id: str,
    begin: float | None = None,
    end: float | None = None,
    step: int = Query(1, ge=1),
) -> dict[str, Any]:
    path = run_dir(run_id)
    meta = run_meta(run_id)
    if meta.get("tier") != "B":
        raise not_available("trajectories (Tier B only)")
    fcd = ensure_fcd(path)
    if fcd is None:
        raise not_available("trajectories")
    return trajectories(fcd, run_id, begin, end, step)


@router.get("/{run_id}/policy-report")
def policy_report(run_id: str) -> dict[str, Any]:
    return read_optional_json(run_id, "policy_report")


@router.get("/{run_id}/scenario-report")
def scenario_report(run_id: str) -> dict[str, Any]:
    return read_optional_json(run_id, "scenario_report")


@router.get("/{run_id}/recommendations")
def recommendations(run_id: str) -> dict[str, Any]:
    return read_optional_json(run_id, "recommendations")


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    operator: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=4000)


@router.post("/{run_id}/recommendations/{option_id}/decision")
def decide(run_id: str, option_id: str, body: DecisionIn) -> dict[str, Any]:
    recs = read_optional_json(run_id, "recommendations")
    options = [o for o in recs.get("options") or [] if o.get("option_id") == option_id]
    if not options:
        raise HTTPException(status_code=404, detail="option not found")
    return append_decision(
        run_dir(run_id),
        run_id=run_id,
        incident_id=recs.get("incident_id"),
        option_id=option_id,
        decision=body.decision,
        operator=body.operator,
        note=body.note,
    )


@router.get("/{run_id}/decisions")
def decisions(run_id: str) -> list[dict[str, Any]]:
    return read_entries(run_dir(run_id) / LOG_NAME)
