"""Run directory lookup (defensive, traversal-safe) and run summaries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api import settings

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{6,64}$")

OPTIONAL_FILES = {
    "policy_report": "policy_report.json",
    "scenario_report": "scenario_report.json",
    "recommendations": "recommendations.json",
    "decisions": "decisions.jsonl",
}


def not_available(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not available")


def _listable(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(("_", "."))


def read_meta(run_dir: Path) -> dict[str, Any] | None:
    try:
        with (run_dir / "meta.json").open(encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def run_dir(run_id: str) -> Path:
    """The directory of an existing run; 404 for anything that is not a run name under runs/."""
    root = settings.runs_dir()
    if not RUN_ID_RE.match(run_id) or run_id.startswith(("_", ".")):
        raise HTTPException(status_code=404, detail="run not found")
    names = {p.name for p in root.iterdir() if _listable(p)} if root.is_dir() else set()
    if run_id not in names:
        raise HTTPException(status_code=404, detail="run not found")
    path = root / run_id
    if path.resolve().parent != root.resolve():
        raise HTTPException(status_code=404, detail="run not found")
    if not (path / "meta.json").is_file():
        raise HTTPException(status_code=404, detail="run not found")
    return path


def run_meta(run_id: str) -> dict[str, Any]:
    meta = read_meta(run_dir(run_id))
    if meta is None:
        raise HTTPException(status_code=404, detail="run not found")
    return meta


def iter_runs() -> list[tuple[Path, dict[str, Any]]]:
    root = settings.runs_dir()
    if not root.is_dir():
        return []
    out = []
    for path in sorted(root.iterdir()):
        if not _listable(path):
            continue
        meta = read_meta(path)
        if meta is not None:
            out.append((path, meta))
    return out


def has_files(path: Path, tier: str | None = None) -> dict[str, bool]:
    has = {
        "edgedata": (path / "edgedata.parquet").exists() or (path / "edgedata.xml").exists(),
        # trajectories are Tier B only (contract section 5)
        "fcd": tier != "A" and ((path / "fcd.parquet").exists() or (path / "fcd.xml").exists()),
    }
    has.update({k: (path / f).exists() for k, f in OPTIONAL_FILES.items()})
    return has


def summary(path: Path, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": meta.get("run_id", path.name),
        "kind": meta.get("kind"),
        "tier": meta.get("tier"),
        "mode": meta.get("mode"),
        "seed": meta.get("seed"),
        "network_hash": meta.get("network_hash"),
        "sim_seconds": meta.get("sim_seconds"),
        "label": meta.get("label", settings.LABEL),
        "baseline_run_id": meta.get("baseline_run_id"),
        "has": has_files(path, meta.get("tier")),
    }


def network_for_hash(network_hash: str) -> Path:
    """The .net.xml of any run with this network hash (404 when no run uses it)."""
    if not HEX_RE.match(network_hash):
        raise HTTPException(status_code=404, detail="network not found")
    for _, meta in iter_runs():
        if meta.get("network_hash") == network_hash and meta.get("network"):
            net = settings.resolve_repo_path(str(meta["network"]))
            if net.is_file():
                return net
    raise HTTPException(status_code=404, detail="network not found")


def read_optional_json(run_id: str, key: str) -> dict[str, Any]:
    path = run_dir(run_id) / OPTIONAL_FILES[key]
    if not path.is_file():
        raise not_available(key.replace("_", " "))
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise not_available(key.replace("_", " ")) from exc
    if isinstance(data, dict):
        data.setdefault("label", settings.LABEL)
    return data
