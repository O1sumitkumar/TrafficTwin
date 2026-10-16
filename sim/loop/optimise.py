"""Loop optimisation: greedy corridor selection under the km budget, then a sweep on the selected
set, noise runs, the recommendation, and the results tables in docs/loop.md.

    python -m sim.loop.optimise                  # runs what is missing (sequential, resumable)
    python -m sim.loop.optimise --no-run         # re-render docs/loop.md from finished runs

1. Candidate results: sim/loop/results/evaluation.json (python -m sim.loop.evaluate); missing
   candidates are run first.
2. Noise: Track A's replicate machinery (TA-018 section of docs/policies.md): the weekday baseline
   re-simulated with sim seed 2 (no policy) gives the run-to-run noise of city VHT; a candidate
   whose VHT saving is inside that band is not selected. A network placebo (tunnels built, alpha
   0) checks that adding the tunnel network alone does not move the surface KPIs.
3. Greedy: candidates by VHT saved per tunnel-km, added while the budget (25 km) allows and the
   alignment does not overlap one already chosen. The selected set is run together (savings of
   separate lines are not assumed additive).
4. Sweep on the selected set. Levers: mode (shuttle / private-EV), tunnel speed {50, 90, 160} and
   toll {0, 10, 25 SAR}. Uncertainties (not choices): alpha {0.3, 0.7}, access radius 800 m,
   engineering vs measured capacity, capex range, simulation noise.
5. Recommendation: the lever setting with the best VHT saved per USD M at central assumptions
   among runs that pass the quality thresholds (capacity exceedance <= 10 %, teleports not worse
   than the comparison by more than the noise), with the band from the uncertainty runs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import typer

from sim.common import REPO_ROOT, SYNTHETIC_LABEL
from sim.loop.evaluate import (
    RESULTS,
    DiskFull,
    blocked,
    load_candidates,
    make_policy,
    merge_results,
    run_one,
)
from sim.loop.schema import loop_config
from sim.policies.edges import utm_xy

LOOP_DIR = Path(__file__).resolve().parent
DOC = REPO_ROOT / "docs" / "loop.md"
RECOMMENDED = REPO_ROOT / "sim" / "policies" / "loop_recommended.yaml"
SAMPLE, SEED = 0.10, 1

# (run suffix, mode, params, role, what it tests)
SWEEP: list[tuple[str, str, dict[str, Any], str, str]] = [
    (
        "",
        "shuttle",
        {},
        "lever",
        "shuttle, central assumptions (alpha 0.5, 90 km/h, measured capacity)",
    ),
    ("_v50", "shuttle", {"speed_kmh": 50.0}, "lever", "shuttle at the measured Vegas-like speed"),
    ("_v160", "shuttle", {"speed_kmh": 160.0}, "lever", "shuttle at the vendor-claimed speed"),
    ("_private_toll10", "private", {"toll_sar": 10.0}, "lever", "private-EV, SAR 10 toll"),
    ("_private_toll0", "private", {"toll_sar": 0.0}, "lever", "private-EV, free"),
    ("_private_toll25", "private", {"toll_sar": 25.0}, "lever", "private-EV, SAR 25 toll"),
    ("_a0p3", "shuttle", {"alpha": 0.3}, "uncertainty", "shift share alpha 0.3"),
    ("_a0p7", "shuttle", {"alpha": 0.7}, "uncertainty", "shift share alpha 0.7"),
    (
        "_r800",
        "shuttle",
        {"radius_o_m": 800.0, "radius_d_m": 800.0},
        "uncertainty",
        "access radius 800 m",
    ),
    (
        "_capeng",
        "shuttle",
        {"capacity": "engineering"},
        "uncertainty",
        "engineering capacity (1.5 s headway, vendor-side)",
    ),
    (
        "_comp",
        "shuttle",
        {"competitive_only": True},
        "uncertainty",
        "time-competitive shift only, measured case (90 km/h, 12.5 min wait, 5.3 s headway)",
    ),
    (
        "_comp_v50",
        "shuttle",
        {"competitive_only": True, "speed_kmh": 50.0},
        "uncertainty",
        "time-competitive shift only, Vegas-like speed (50 km/h, 12.5 min wait)",
    ),
    (
        "_comp_vendor",
        "shuttle",
        {"competitive_only": True, "speed_kmh": 160.0, "capacity": "engineering"},
        "uncertainty",
        "time-competitive shift only, vendor case (160 km/h, 2 min wait, 1.5 s headway)",
    ),
]


def stations_xy(c: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    return utm_xy([s["lon"] for s in c["stations"]], [s["lat"] for s in c["stations"]])


def overlap(a: dict[str, Any], b: dict[str, Any], cfg: dict[str, Any]) -> bool:
    from sim.loop.site import overlaps

    ax, ay = stations_xy(a)
    bx, by = stations_xy(b)
    return overlaps(pd.Series({"sx": ax, "sy": ay}), [pd.Series({"sx": bx, "sy": by})], cfg)


def greedy(
    cands: dict[str, dict[str, Any]],
    evals: dict[str, dict[str, Any]],
    budget: float,
    noise_vht: float,
    cfg: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    order = sorted(evals, key=lambda c: -(evals[c]["vht_saved_per_km"] or -1e9))
    chosen: list[str] = []
    used = 0.0
    log = []
    for cid in order:
        e, c = evals[cid], cands[cid]
        km = float(e["tunnel_km"])
        why = "selected"
        if e["vht_saved_per_day"] <= noise_vht:
            why = f"saving {e['vht_saved_per_day']:,} <= noise {noise_vht:,.0f} VHT/day"
        elif used + km > budget:
            why = f"over budget ({used + km:.1f} > {budget:g} km)"
        elif any(overlap(c, cands[o], cfg) for o in chosen):
            why = "overlaps " + ", ".join(o for o in chosen if overlap(c, cands[o], cfg))
        if why == "selected":
            chosen.append(cid)
            used += km
        log.append(
            {
                "candidate": cid,
                "km": km,
                "vht_saved_per_km": e["vht_saved_per_km"],
                "decision": why,
                "cumulative_km": round(used, 2),
            }
        )
    return chosen, log


def noise_runs(runs_dir: Path, base_vht: float, quiet: bool) -> dict[str, Any]:
    """Baseline replicate with sim seed 2 (Track A machinery), reused when present."""
    from sim.policies.run import run_policy
    from sim.schemas import Policy

    rid = "loop_noise_baseline_s2"
    meta_path = runs_dir / rid / "meta.json"
    if not meta_path.exists():
        null = Policy.model_validate(
            {
                "id": "loop_noise",
                "kind": "policy",
                "daytype": "weekday",
                "title": "Baseline replicate, simulation seed 2 (noise band)",
                "transforms": [
                    {
                        "type": "remote_work",
                        "share": 0.0,
                        "days_per_week": 1,
                        "eligible_sectors": ["government"],
                        "assumption": "no-op transform: replicate run (TA-018 noise)",
                    }
                ],
            }
        )
        run_policy(
            null,
            "weekday",
            SAMPLE,
            SEED,
            runs_dir,
            quiet=quiet,
            force_simulate=True,
            sim_seed=2,
            run_id=rid,
        )
        for name in ("edgedata.parquet", "emissions.parquet"):
            (runs_dir / rid / name).unlink(missing_ok=True)
    meta = json.loads(meta_path.read_text())
    vht = float(meta["result"]["vht"])
    am = float(meta["result"]["am_peak_mean_delay_s"])
    return {
        "run": rid,
        "vht": vht,
        "vht_delta": round(vht - base_vht),
        "noise_vht": round(abs(vht - base_vht)),
        "am_peak_delay_s": am,
        "teleport_share": meta["result"]["teleport_share"],
    }


def sweep_policy(
    suffix: str, mode: str, params: dict[str, Any], chosen: list[dict[str, Any]], tag: str
) -> Any:
    pid = f"loop_opt_{tag}{suffix}".lower()
    title = f"Loop {tag}: {' + '.join(c['id'] for c in chosen)} ({mode}; {SYNTHETIC_LABEL})"
    return make_policy(pid, title, chosen, mode, params)


def passes(rep: dict[str, Any], cfg: dict[str, Any], tele_tol: float) -> tuple[bool, str]:
    f = rep["flags"]
    ex = f.get("pair_exceedance_share") or 0.0
    if ex > float(cfg["quality"]["max_capacity_exceedance"]):
        return False, f"capacity exceedance {ex:.1%}"
    t, t0 = f.get("teleport_share"), f.get("teleport_share_compare")
    if t is not None and t0 is not None and t > t0 + tele_tol:
        return False, f"teleports {t:.3f} vs {t0:.3f}"
    if rep["vht_saved_per_day"] <= 0:
        return False, "no VHT saving"
    return True, "ok"


# ---------------------------------------------------------------------------- rendering


def fmt(v: Any, nd: int = 1) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    if isinstance(v, float):
        return f"{v:,.{nd}f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def table(rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(h for _, h in cols) + " |"
    sep = "|" + "---|" * len(cols)
    body = ["| " + " | ".join(fmt(r.get(k)) for k, _ in cols) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def rank_rows(cands: dict[str, dict[str, Any]], evals: dict[str, dict[str, Any]]) -> list[dict]:
    rows = []
    for cid, e in evals.items():
        c = cands[cid]
        per = e["vht_saved_per_usd_m"]
        rows.append(
            {
                "id": cid,
                "name": c["name"],
                "origin": c["origin"],
                "km": e["tunnel_km"],
                "stations": e["stations"],
                "pax": e["passengers_per_day"],
                "vht": e["vht_saved_per_day"],
                "vht_pct": e["vht_saved_pct"],
                "road_vht": e["road_vht_saved_per_day"],
                "am": e["am_peak_delay_change_pct"],
                "per_km": e["vht_saved_per_km"],
                "per_usd": f"{per['central']:.1f} ({per['high']:.1f}-{per['low']:.1f})",
                "capex": f"{e['capex_usd_m']['low']:,.0f}-{e['capex_usd_m']['high']:,.0f}",
                "exceed": e["flags"].get("pair_exceedance_share"),
                "slower": e["flags"].get("share_slower_than_car"),
                "tele": e["flags"].get("teleport_share"),
            }
        )
    rows.sort(key=lambda r: -(r["per_km"] or -1e9))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


RANK_COLS = [
    ("rank", "rank"),
    ("id", "id"),
    ("name", "alignment"),
    ("origin", "origin"),
    ("km", "tunnel-km"),
    ("stations", "stations"),
    ("pax", "passengers/day"),
    ("vht", "city VHT saved/day"),
    ("vht_pct", "VHT %"),
    ("road_vht", "road VHT saved/day"),
    ("am", "AM-peak delay %"),
    ("per_km", "VHT/day per km"),
    ("per_usd", "VHT/day per USD M (range)"),
    ("capex", "capex USD M"),
    ("exceed", "pair exceedance"),
    ("slower", "riders slower than car"),
    ("tele", "teleports/veh"),
]

SWEEP_COLS = [
    ("config", "configuration"),
    ("role", "role"),
    ("km", "tunnel-km"),
    ("pax", "passengers or cars re-routed"),
    ("vht", "city VHT saved/day"),
    ("vht_pct", "VHT %"),
    ("am", "AM-peak delay %"),
    ("per_usd", "VHT/day per USD M"),
    ("exceed", "pair exceedance"),
    ("seg", "segment peak util."),
    ("slower", "riders slower than car"),
    ("tele", "teleports/veh"),
    ("ok", "quality"),
]


def sweep_row(desc: str, role: str, rep: dict[str, Any], ok: str) -> dict[str, Any]:
    per = rep["vht_saved_per_usd_m"]
    return {
        "config": desc,
        "role": role,
        "km": rep["tunnel_km"],
        "run": rep["run_id"],
        "pax": rep.get("passengers_per_day") or rep.get("cars_rerouted"),
        "vht": rep["vht_saved_per_day"],
        "vht_pct": rep["vht_saved_pct"],
        "am": rep["am_peak_delay_change_pct"],
        "per_usd": f"{per['central']:.1f} ({per['high']:.1f}-{per['low']:.1f})",
        "per_usd_central": per["central"],
        "exceed": rep["flags"].get("pair_exceedance_share"),
        "seg": rep["flags"].get("segment_peak_utilisation"),
        "slower": rep["flags"].get("share_slower_than_car"),
        "tele": rep["flags"].get("teleport_share"),
        "ok": ok,
    }


def replace_section(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- LOOP:{name} -->)(.*?)(<!-- /LOOP:{name} -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"docs/loop.md has no LOOP:{name} markers")
    return pat.sub(lambda m: f"{m.group(1)}\n{body.strip()}\n{m.group(3)}", text)


# ---------------------------------------------------------------------------- main


def optimise(run: bool = True, budget: float | None = None, quiet: bool = False) -> dict[str, Any]:
    cfg = loop_config()
    budget = float(budget or cfg["budget_km"])
    runs_dir = REPO_ROOT / "runs"
    cands = load_candidates(LOOP_DIR / "candidates.yaml")
    ev_doc = json.loads((RESULTS / "evaluation.json").read_text())
    evals = {
        r["candidate"]: r
        for r in ev_doc["runs"].values()
        if r.get("candidate") and r["run_id"] == f"loop_{r['candidate'].lower()}"
    }
    missing = sorted(set(cands) - set(evals))
    if missing and run:
        for cid in missing:
            c = cands[cid]
            pol = make_policy(f"loop_{cid.lower()}", f"Loop {cid} {c['name']}", [c], "shuttle", {})
            rep = run_one(pol, SAMPLE, SEED, runs_dir, prune=True, quiet=quiet)
            rep["candidate"] = cid
            merge_results(RESULTS / "evaluation.json", [rep])
            evals[cid] = rep
    base_meta = json.loads(
        (runs_dir / next(iter(evals.values()))["compare"] / "meta.json").read_text()
    )
    noise = (
        noise_runs(runs_dir, float(base_meta["result"]["vht"]), quiet)
        if run
        else (json.loads((RESULTS / "optimise.json").read_text())["noise"])
    )
    chosen_ids, glog = greedy(cands, evals, budget, noise["noise_vht"], cfg)
    chosen = [cands[c] for c in chosen_ids]
    tag = "".join(c.lower() for c in chosen_ids)
    sweep: list[dict[str, Any]] = []
    reports: dict[str, dict[str, Any]] = {}
    tele_tol = abs(noise["teleport_share"] - base_meta["result"]["teleport_share"])
    for suffix, mode, params, role, desc in SWEEP:
        pol = sweep_policy(suffix, mode, params, chosen, tag)
        rep_path = runs_dir / pol.id / "loop_report.json"
        if run:
            rep = run_one(pol, SAMPLE, SEED, runs_dir, prune=True, quiet=quiet)
            merge_results(RESULTS / "optimise_runs.json", [rep])
        elif rep_path.exists():
            rep = json.loads(rep_path.read_text())
        else:
            continue
        reports[suffix] = rep
        ok, why = passes(rep, cfg, max(tele_tol, 0.01))
        sweep.append(sweep_row(desc, role, rep, why) | {"suffix": suffix, "pass": ok})
    # network placebo: tunnels built, nobody shifted
    placebo = None
    pol = sweep_policy("_placebo_a0", "shuttle", {"alpha": 0.0}, chosen, tag)
    if run or (runs_dir / pol.id / "loop_report.json").exists():
        placebo = run_one(pol, SAMPLE, SEED, runs_dir, prune=True, quiet=quiet)
    levers = [r for r in sweep if r["role"] == "lever" and r["pass"]]
    best = max(levers, key=lambda r: r["per_usd_central"]) if levers else None
    result = {
        "label": SYNTHETIC_LABEL,
        "budget_km": budget,
        "noise": noise,
        "greedy": glog,
        "selected": chosen_ids,
        "selected_km": round(sum(evals[c]["tunnel_km"] for c in chosen_ids), 2),
        "sweep": sweep,
        "placebo": placebo,
        "recommended": best,
    }
    if best is not None:
        rec = reports[best["suffix"]]
        result["band"] = band(rec, reports, noise, best["suffix"])
        if run:
            result["replicate"] = replicate(best, chosen, tag, runs_dir, quiet, noise)
        else:
            prev = RESULTS / "optimise.json"
            if prev.exists():
                result["replicate"] = json.loads(prev.read_text()).get("replicate")
    if best is not None:
        suffix, mode, params = next((s, m, p) for s, m, p, _, _ in SWEEP if s == best["suffix"])
        write_policy_yaml(sweep_policy(suffix, mode, params, chosen, tag), RECOMMENDED, best)
    (RESULTS / "optimise.json").write_text(json.dumps(result, indent=2, default=float))
    render(result, cands, evals, cfg)
    return result


def write_policy_yaml(pol: Any, path: Path, best: dict[str, Any]) -> None:
    """The recommended configuration as a reusable policy file (python -m sim.loop.run ...)."""
    import yaml

    doc = pol.model_dump(exclude_none=True, exclude={"report"})
    doc["id"] = path.stem
    head = (
        f"# Recommended Loop configuration (python -m sim.loop.optimise; run {best['run']}).\n"
        f"# {SYNTHETIC_LABEL}. Run: uv run python -m sim.loop.run {path.stem}\n"
    )
    path.write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))


def band(
    rec: dict[str, Any], reports: dict[str, dict[str, Any]], noise: dict[str, Any], suffix: str
) -> dict[str, Any]:
    """Uncertainty band of the recommended configuration's VHT saved per USD M."""
    vals = [rec["vht_saved_per_day"]]
    if suffix == "":  # shuttle: alpha / radius / capacity runs are its sensitivity
        vals += [
            reports[s]["vht_saved_per_day"]
            for s in ("_a0p3", "_a0p7", "_r800", "_capeng")
            if s in reports
        ]
    lo, hi = min(vals) - noise["noise_vht"], max(vals) + noise["noise_vht"]
    cx = rec["capex_usd_m"]
    return {
        "vht_saved_per_day": rec["vht_saved_per_day"],
        "vht_saved_range": [round(lo), round(hi)],
        "per_usd_m_central": rec["vht_saved_per_usd_m"]["central"],
        "per_usd_m_range": [round(max(lo, 0) / cx["high"], 2), round(hi / cx["low"], 2)],
        "capex_usd_m": cx,
    }


def replicate(
    best: dict[str, Any],
    chosen: list[dict[str, Any]],
    tag: str,
    runs_dir: Path,
    quiet: bool,
    noise: dict[str, Any],
) -> dict[str, Any]:
    """The recommended configuration re-simulated with sim seed 2, against the seed-2 baseline."""
    suffix, mode, params = next((s, m, p) for s, m, p, _, _ in SWEEP if s == best["suffix"])
    pol = sweep_policy(suffix, mode, params, chosen, tag)
    rep = run_one(
        pol, SAMPLE, SEED, runs_dir, prune=True, sim_seed=2, run_id=f"{pol.id}-sim2", quiet=quiet
    )
    # saving against the seed-2 baseline replicate: policy(seed 2) vs baseline(seed 2)
    meta = json.loads((runs_dir / rep["run_id"] / "meta.json").read_text())
    saved_s2 = round(noise["vht"] - float(meta["result"]["vht"]))
    return {
        "run": rep["run_id"],
        "vht_saved_vs_seed2_baseline": saved_s2,
        "vht_saved_vs_seed1_baseline": rep["vht_saved_per_day"],
    }


def render(
    res: dict[str, Any],
    cands: dict[str, dict[str, Any]],
    evals: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
) -> None:
    text = DOC.read_text()
    rank = rank_rows(cands, evals)
    text = replace_section(text, "ranking", table(rank, RANK_COLS))
    cand_rows = [
        {
            "id": cid,
            "name": c["name"],
            "origin": c["origin"],
            "km": c["tunnel_km"],
            "n": len(c["stations"]),
            "stations": " · ".join(s["name"] for s in c["stations"]),
            "cap": c["captured_delay_h"],
            "trips": c["captured_trips"],
        }
        for cid, c in cands.items()
    ]
    text = replace_section(
        text,
        "candidates",
        table(
            cand_rows,
            [
                ("id", "id"),
                ("name", "alignment"),
                ("origin", "origin"),
                ("km", "tunnel-km"),
                ("n", "stations"),
                ("stations", "station sites (district or anchor)"),
                ("cap", "captured delay h/day (siting score)"),
                ("trips", "capturable trips/day"),
            ],
        ),
    )
    text = replace_section(
        text,
        "greedy",
        table(
            res["greedy"],
            [
                ("candidate", "candidate"),
                ("km", "tunnel-km"),
                ("vht_saved_per_km", "VHT/day per km"),
                ("decision", "decision"),
                ("cumulative_km", "selected km"),
            ],
        ),
    )
    text = replace_section(text, "sweep", table(res["sweep"], SWEEP_COLS))
    n = res["noise"]
    pl = res.get("placebo") or {}
    rep = res.get("replicate") or {}
    noise_md = (
        f"- Baseline replicate (sim seed 2, `runs/{n['run']}`): city VHT {n['vht_delta']:+,} "
        f"VHT/day vs seed 1 (noise band +/- {n['noise_vht']:,} VHT/day); teleports/veh "
        f"{n['teleport_share']:.3f}.\n"
    )
    if pl:
        noise_md += (
            f"- Network placebo (`runs/{pl['run_id']}`: tunnels built, alpha 0): city "
            f"VHT saved {pl['vht_saved_per_day']:+,}/day (should be inside the noise "
            f"band).\n"
        )
    if rep:
        noise_md += (
            f"- Recommended configuration re-simulated with sim seed 2 (`runs/{rep['run']}`)"
            f": VHT saved {rep['vht_saved_vs_seed2_baseline']:,}/day against the seed-2 "
            f"baseline (seed 1: {rep['vht_saved_vs_seed1_baseline']:,}).\n"
        )
    text = replace_section(text, "noise", noise_md)
    best = res.get("recommended")
    if best:
        b = res["band"]
        sel = " + ".join(
            f"{c} ({cands[c]['name']}, {cands[c]['tunnel_km']} km)" for c in res["selected"]
        )
        rec_md = (
            f"**Corridors:** {sel}; {res['selected_km']} tunnel-km of the {res['budget_km']:g} km "
            f"budget.\n\n**Policy:** {best['config']} (run `runs/{best['run']}`).\n\n"
            f"| item | value |\n|---|---|\n"
            f"| city VHT saved per day | {b['vht_saved_per_day']:,} "
            f"(band {b['vht_saved_range'][0]:,} to {b['vht_saved_range'][1]:,}) |\n"
            f"| VHT saved per day per USD M | {b['per_usd_m_central']:.1f} central capex (band "
            f"{b['per_usd_m_range'][0]:.1f} to {b['per_usd_m_range'][1]:.1f}) |\n"
            f"| capex USD M (low / central / high) | {b['capex_usd_m']['low']:,.0f} / "
            f"{b['capex_usd_m']['central']:,.0f} / {b['capex_usd_m']['high']:,.0f} |\n"
            f"| AM-peak delay change | {fmt(best['am'], 2)} % |\n"
            f"| passengers per day | {fmt(best['pax'])} |\n"
            f"| pair capacity exceedance | {fmt(best['exceed'], 3)} |\n"
            f"| tunnel segment peak utilisation | {fmt(best['seg'], 2)} |\n"
            f"| riders slower than by car | {fmt(best['slower'], 3)} |\n"
            f"| teleports per vehicle | {fmt(best['tele'], 3)} |\n"
        )
    else:
        rec_md = "No lever configuration passed the quality thresholds; see the sweep table."
    text = replace_section(text, "recommendation", rec_md)
    DOC.write_text(text)


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    no_run: bool = typer.Option(False, "--no-run", help="only re-render from finished runs"),
    budget_km: float | None = typer.Option(None),
) -> None:
    try:
        res = optimise(run=not no_run, budget=budget_km)
    except DiskFull as e:
        blocked("disk")
        raise typer.Exit(f"stopped: {e}") from e
    typer.echo(f"selected {res['selected']} ({res['selected_km']} km)")
    if res.get("recommended"):
        typer.echo(f"recommended: {res['recommended']['config']} ({res['recommended']['run']})")
    typer.echo("wrote docs/loop.md, sim/loop/results/optimise.json")


if __name__ == "__main__":
    app()
