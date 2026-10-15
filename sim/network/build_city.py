"""Build the Tier A (city, mesoscopic) Jeddah network from OpenStreetMap.

Pipeline (each step is skipped when its output is newer than its input, unless --force):
  1. download the Geofabrik extract (only with --download, or if missing and allowed)
  2. clip it to data/osm/jeddah.poly with osmium
  3. convert the clip to OSM XML (netconvert does not read PBF)
  4. netconvert with the options in sim/network/config/city.yaml -> <net>.raw.net.xml
  5. apply the reviewed fix list (data/osm/fixes/*.yaml) -> data/jeddah/jeddah.net.xml
  6. side outputs: districts.geojson, buildings.geojson, viewer edges, build.json

    python -m sim.network.build_city                       # full city build
    python -m sim.network.build_city --osm data/demo/demo.osm.xml.gz --out /tmp/demo.net.xml \
        --no-side-outputs                                  # same builder on a small extract
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import typer

from sim.common import (
    REPO_ROOT,
    file_hash,
    load_yaml,
    rel,
    run_cmd,
    sumo_bin,
    sumo_home,
    sumo_version,
)
from sim.network import geo
from sim.network.fixes import apply_fixes, load_fixes
from sim.network.netinfo import edges_geojson, net_stats

DEFAULT_CONFIG = REPO_ROOT / "sim" / "network" / "config" / "city.yaml"


def _p(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def _fresh(out: Path, *inputs: Path) -> bool:
    return out.exists() and all(out.stat().st_mtime >= i.stat().st_mtime for i in inputs)


def netconvert_args(cfg: dict[str, Any]) -> list[str]:
    """Flatten the configured netconvert options and type files into an argument list."""
    args: list[str] = []
    for opt in cfg["netconvert_options"]:
        args.extend([opt] if isinstance(opt, str) else [str(o) for o in opt])
    type_files = [str(_p(t.replace("${SUMO_HOME}", str(sumo_home())))) for t in cfg["type_files"]]
    args.extend(["--type-files", ",".join(type_files)])
    return args


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    typer.echo(f"downloading {url} -> {rel(dest)}")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed https URL from config
    tmp.rename(dest)


def osm_timestamp(pbf: Path) -> str:
    out = subprocess.run(
        ["osmium", "fileinfo", "-g", "header.option.osmosis_replication_timestamp", str(pbf)],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out or "unknown"


def build_net(
    osm_xml: Path,
    net_out: Path,
    cfg: dict[str, Any],
    fixes_dir: Path,
    log: Path,
    strict_fixes: bool = True,
) -> dict[str, list[str]]:
    """netconvert + fix list. Returns the edges each fix resolved to."""
    net_out.parent.mkdir(parents=True, exist_ok=True)
    raw = net_out.with_name(net_out.name.replace(".net.xml", ".raw.net.xml"))
    cmd = [
        sumo_bin("netconvert"),
        "--osm-files",
        str(osm_xml),
        "-o",
        str(raw),
        *netconvert_args(cfg),
    ]
    run_cmd(cmd, log=log)
    resolved = apply_fixes(raw, net_out, fixes_dir, log=log, strict=strict_fixes)
    return resolved


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    config: Path = typer.Option(DEFAULT_CONFIG, help="build configuration YAML"),
    osm: Path | None = typer.Option(None, help="use this OSM XML instead of the city clip"),
    out: Path | None = typer.Option(None, help="output .net.xml (default from config)"),
    fixes_dir: Path | None = typer.Option(None, help="fix list directory (default from config)"),
    download_extract: bool = typer.Option(False, "--download", help="(re)download the extract"),
    side_outputs: bool = typer.Option(True, help="write districts/buildings/viewer GeoJSON"),
    force: bool = typer.Option(False, help="rebuild every step"),
    strict_fixes: bool = typer.Option(True, help="fail if a fix matches no edge"),
) -> None:
    cfg = load_yaml(config)
    net = out or _p(cfg["net"])
    fixes = fixes_dir or _p(cfg["fixes_dir"])
    log = REPO_ROOT / "logs" / f"build_city-{net.stem.split('.')[0]}.log"
    t0 = time.perf_counter()
    meta: dict[str, Any] = {
        "config": rel(config),
        "sumo_version": sumo_version(),
        "sumo_home": str(sumo_home()),
    }

    if osm is None:
        extract = _p(cfg["extract"]["file"])
        if download_extract or not extract.exists():
            download(cfg["extract"]["url"], extract)
        poly = _p(cfg["polygon"])
        clip = _p(cfg["clip_pbf"])
        osm = _p(cfg["osm_xml"])
        if force or not _fresh(clip, extract, poly):
            run_cmd(
                [
                    "osmium",
                    "extract",
                    "-p",
                    str(poly),
                    str(extract),
                    "-o",
                    str(clip),
                    "--overwrite",
                ],
                log=log,
            )
        if force or not _fresh(osm, clip):
            run_cmd(["osmium", "cat", str(clip), "-o", str(osm), "--overwrite"], log=log)
        meta.update(
            extract=rel(extract),
            extract_timestamp=osm_timestamp(extract),
            polygon=rel(poly),
            polygon_hash=file_hash(poly),
        )
    meta["osm_input"] = rel(osm)
    meta["osm_hash"] = file_hash(osm)

    resolved = build_net(osm, net, cfg, fixes, log, strict_fixes=strict_fixes)
    meta["fixes"] = {f.id: resolved.get(f.id, []) for f in load_fixes(fixes)}
    stats = net_stats(net)
    meta["network"] = stats.as_dict()
    typer.echo(f"network {rel(net)}: {json.dumps(stats.as_dict())}")

    if side_outputs:
        clip_pbf = _p(cfg["clip_pbf"])
        districts = _p(cfg["districts"]["out"])
        n_d = geo.write_districts(clip_pbf, _p(cfg["polygon"]), districts, cfg["districts"])
        buildings = _p(cfg["buildings"]["out"])
        heights = load_yaml(_p(cfg["buildings"]["heights"]))
        n_b = geo.write_buildings(clip_pbf, buildings, heights)
        edges_out = _p(cfg["viewer"]["edges_out"])
        n_e = edges_geojson(net, edges_out)
        shutil.copyfile(districts, _p(cfg["viewer"]["districts_out"]))
        meta["side_outputs"] = {
            "districts": {"file": rel(districts), "features": n_d},
            "buildings": {
                "file": rel(buildings),
                "features": n_b,
                "mb": round(buildings.stat().st_size / 1e6, 1),
            },
            "viewer_edges": {"file": rel(edges_out), "features": n_e},
        }
    meta["build_seconds"] = round(time.perf_counter() - t0, 1)
    meta_path = net.with_name(net.name.replace(".net.xml", ".build.json"))
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    typer.echo(f"build metadata -> {rel(meta_path)} ({meta['build_seconds']} s)")


if __name__ == "__main__":
    os.environ.setdefault("LC_ALL", "C")
    app()
