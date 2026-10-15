"""Run SUMO at Tier A (city, meso) or Tier B (window, micro) and record a reproducible run.

M1 implements smoke runs: random trips on a network for one hour, reporting network size,
runtime, real-time factor and teleport share. Baselines, policies and scenarios arrive in M2+.

    python -m sim.runner --smoke --tier A --seed 1
    python -m sim.runner --smoke --tier B --seed 1                       # demo window, micro
    python -m sim.runner --smoke --tier A --net data/demo/demo.net.xml   # any network, meso
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import typer

from sim.common import (
    REPO_ROOT,
    config_hash,
    content_hash,
    load_yaml,
    python_tool_cmd,
    rel,
    run_cmd,
    sumo_bin,
    sumo_version,
)
from sim.network.netinfo import net_stats

RUNNER_CONFIG = REPO_ROOT / "sim" / "config" / "runner.yaml"
RUNS_DIR = REPO_ROOT / "runs"


def runner_config() -> dict[str, Any]:
    return load_yaml(RUNNER_CONFIG)


def smoke_config() -> dict[str, Any]:
    return runner_config()["smoke"]


def flatten(options: list[Any]) -> list[str]:
    out: list[str] = []
    for opt in options:
        out.extend([opt] if isinstance(opt, str) else [str(o) for o in opt])
    return out


def assert_tier_options(
    tier: str, args: list[str], additional_files: list[Path], cfg: dict[str, Any]
) -> None:
    """Micro-only features must never reach a Tier A (meso) run."""
    if tier != "A":
        return
    bad = [
        a
        for a in args
        if a.startswith("--") and any(a.startswith(p) for p in cfg["micro_only_options"])
    ]
    tags = set(cfg["micro_only_additional_elements"])
    for add in additional_files:
        for _, elem in ET.iterparse(add, events=("start",)):
            if elem.tag in tags:
                bad.append(f"{rel(add)}:<{elem.tag}>")
    if bad:
        raise ValueError(f"micro-only features in a Tier A run: {', '.join(bad)}")


def make_random_trips(
    net: Path,
    out: Path,
    params: dict[str, Any],
    seed: int,
    begin: int,
    end: int,
    routes: Path | None = None,
    log: Path | None = None,
) -> None:
    """randomTrips.py; with `routes`, duarouter also writes routes and drops unroutable trips."""
    out.parent.mkdir(parents=True, exist_ok=True)
    opts = {
        "-n": net,
        "-o": out,
        "-b": begin,
        "-e": end,
        "-p": params["period"],
        "--fringe-factor": params["fringe_factor"],
        "--min-distance": params["min_distance"],
        "--vclass": params["vclass"],
        "--seed": seed,
        "--prefix": "smoke",
    }
    args = [str(x) for kv in opts.items() for x in kv]
    if routes is not None:
        args += ["-r", str(routes)]
        run_cmd(python_tool_cmd("randomTrips.py", *args), log=log)
        return
    # trips only: still route them (into a scratch file next to `out`, so the path recorded in
    # the trips header is stable) so that unroutable trips are dropped
    scratch = out.with_name(out.name + ".scratch.rou.xml")
    try:
        args += ["-r", str(scratch)]
        run_cmd(python_tool_cmd("randomTrips.py", *args), log=log)
    finally:
        scratch.unlink(missing_ok=True)


def parse_statistics(stats_xml: Path) -> dict[str, Any]:
    """Pull vehicles, teleports and performance from SUMO's --statistic-output."""
    root = ET.parse(stats_xml).getroot()

    def attrs(tag: str) -> dict[str, str]:
        el = root.find(tag)
        return dict(el.attrib) if el is not None else {}

    return {
        "performance": attrs("performance"),
        "vehicles": attrs("vehicles"),
        "teleports": attrs("teleports"),
        "safety": attrs("safety"),
        "vehicleTripStatistics": attrs("vehicleTripStatistics"),
    }


def summarise(stats: dict[str, Any], sim_seconds: int, wall_seconds: float) -> dict[str, Any]:
    veh = stats["vehicles"]
    loaded = int(veh.get("loaded", 0))
    teleports = int(stats["teleports"].get("total", 0))
    trips = stats["vehicleTripStatistics"]
    return {
        "vehicles_loaded": loaded,
        "vehicles_inserted": int(veh.get("inserted", 0)),
        "vehicles_running_at_end": int(veh.get("running", 0)),
        "vehicles_waiting_at_end": int(veh.get("waiting", 0)),
        "teleports": teleports,
        "teleports_jam": int(stats["teleports"].get("jam", 0)),
        "teleports_yield": int(stats["teleports"].get("yield", 0)),
        "teleports_wrong_lane": int(stats["teleports"].get("wrongLane", 0)),
        "teleport_share": round(teleports / loaded, 6) if loaded else 0.0,
        "completed_trips": int(trips.get("count", 0)),
        "mean_trip_duration_s": float(trips.get("duration", 0.0)),
        "mean_route_length_m": float(trips.get("routeLength", 0.0)),
        "mean_speed_ms": float(trips.get("speed", 0.0)),
        "wall_seconds": round(wall_seconds, 2),
        "real_time_factor": round(sim_seconds / wall_seconds, 1) if wall_seconds else None,
        "sumo_real_time_factor": float(stats["performance"].get("realTimeFactor", 0) or 0),
    }


def run_smoke(
    tier: str,
    seed: int,
    net: Path | None = None,
    end: int | None = None,
    runs_dir: Path = RUNS_DIR,
    quiet: bool = False,
    period: float | None = None,
) -> dict[str, Any]:
    cfg = runner_config()
    smoke = cfg["smoke"]
    tier_key = f"tier_{tier}"
    tier_smoke = dict(smoke[tier_key])
    if period is not None:
        tier_smoke["random_trips"] = {**tier_smoke["random_trips"], "period": period}
    net = net or (REPO_ROOT / tier_smoke["net"])
    if not net.exists():
        raise FileNotFoundError(f"{rel(net)} missing; build it first (see README)")
    begin = int(tier_smoke["begin"])
    end = int(end if end is not None else tier_smoke["end"])
    nhash = content_hash(net)
    run_cfg = {
        "tier": tier,
        "seed": seed,
        "begin": begin,
        "end": end,
        "random_trips": tier_smoke["random_trips"],
        "sumo_common": cfg["sumo_common"],
        "tier_options": cfg[tier_key]["options"],
    }
    chash = config_hash(run_cfg)
    run_id = f"smoke-{tier}-s{seed}-{nhash[:8]}-{chash[:8]}"
    out = runs_dir / run_id
    out.mkdir(parents=True, exist_ok=True)
    log = out / "build.log"
    log.unlink(missing_ok=True)

    trips = out / "trips.xml"
    routes = out / "routes.rou.xml"
    t0 = time.perf_counter()
    make_random_trips(net, trips, tier_smoke["random_trips"], seed, begin, end, routes, log)
    demand_seconds = time.perf_counter() - t0

    additional = out / "edgedata.add.xml"
    additional.write_text(
        "<additional>\n"
        f'    <edgeData id="ed" freq="{smoke["edgedata_freq_s"]}" file="edgedata.xml" '
        'excludeEmpty="true"/>\n</additional>\n'
    )
    args = [
        "-n",
        str(net),
        "-r",
        str(routes),
        "--additional-files",
        str(additional),
        "--begin",
        str(begin),
        "--end",
        str(end),
        "--seed",
        str(seed),
        "--tripinfo-output",
        str(out / "tripinfo.xml"),
        "--statistic-output",
        str(out / "stats.xml"),
        "--log",
        str(out / "sumo.log"),
        *flatten(cfg["sumo_common"]),
        *flatten(cfg[tier_key]["options"]),
    ]
    assert_tier_options(tier, args, [additional], cfg)
    t1 = time.perf_counter()
    run_cmd([sumo_bin("sumo"), *args], log=log)
    wall = time.perf_counter() - t1

    stats = parse_statistics(out / "stats.xml")
    result = summarise(stats, end - begin, wall)
    meta = {
        "run_id": run_id,
        "label": cfg["label"],
        "kind": "smoke",
        "tier": tier,
        "mode": cfg[tier_key]["mode"],
        "seed": seed,
        "config_hash": chash,
        "network": rel(net),
        "network_hash": nhash,
        "population_hash": content_hash(routes),
        "sumo_version": sumo_version(),
        "sim_seconds": end - begin,
        "demand_seconds": round(demand_seconds, 1),
        "network_stats": net_stats(net).as_dict(),
        "result": result,
        "teleport_share_max": smoke["teleport_share_max"],
        "teleport_ok": result["teleport_share"] < smoke["teleport_share_max"],
        "sumo_statistics": stats,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    if not quiet:
        print_report(meta, out)
    return meta


def print_report(meta: dict[str, Any], out: Path) -> None:
    ns, r = meta["network_stats"], meta["result"]
    lines = [
        f"TrafficTwin smoke run {meta['run_id']}  [{meta['label']}]",
        f"  tier {meta['tier']} ({meta['mode']}), seed {meta['seed']}, {meta['sumo_version']}",
        f"  network {meta['network']}: {ns['edges']} edges, {ns['junctions']} junctions, "
        f"{ns['traffic_lights']} traffic lights, {ns['lane_km']} lane-km",
        f"  vehicles loaded {r['vehicles_loaded']}, inserted {r['vehicles_inserted']}, "
        f"completed {r['completed_trips']}, running at end {r['vehicles_running_at_end']}, "
        f"waiting {r['vehicles_waiting_at_end']}",
        f"  runtime {r['wall_seconds']} s for {meta['sim_seconds']} s simulated "
        f"(real-time factor {r['real_time_factor']}); demand generation {meta['demand_seconds']} s",
        f"  teleports {r['teleports']} (jam {r['teleports_jam']}, yield {r['teleports_yield']}, "
        f"wrong lane {r['teleports_wrong_lane']}) = {100 * r['teleport_share']:.3f}% of loaded "
        f"vehicles -> {'OK' if meta['teleport_ok'] else 'FAIL'} "
        f"(limit {100 * meta['teleport_share_max']:.1f}%)",
        f"  outputs {rel(out)}/",
    ]
    typer.echo("\n".join(lines))


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    smoke: bool = typer.Option(False, "--smoke", help="random-trips smoke run"),
    tier: str = typer.Option("A", help="A = city (meso), B = window (micro)"),
    seed: int = typer.Option(1),
    net: Path | None = typer.Option(None, help="override the network"),
    end: int | None = typer.Option(None, help="override the end time (s)"),
    period: float | None = typer.Option(None, help="override the random-trips period (s)"),
    runs_dir: Path = typer.Option(RUNS_DIR),
) -> None:
    if tier not in ("A", "B"):
        raise typer.BadParameter("tier must be A or B")
    if not smoke:
        raise typer.BadParameter("only --smoke is implemented in M1 (baselines arrive in M2)")
    meta = run_smoke(tier, seed, net, end, runs_dir, period=period)
    if not meta["teleport_ok"]:
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
