"""Track D unit tests (fast, demo window): Loop schema, parameters, tunnel network build, shuttle
generation, capacity flags, run naming and the siting geometry."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

import sim.policies.edges as E
from sim.common import REPO_ROOT
from sim.loop.evaluate import defaults, eval_id, make_policy
from sim.loop.network import build_loop_net, meso_types_file, shuttle_route
from sim.loop.params import capacity_figures, resolve_params
from sim.loop.schema import LoopPolicy, LoopShuttle, load_loop_policy, loop_config, loop_transform
from sim.loop.transforms import capacity_flags, nearest_station, shuttles
from sim.metrics import xml_content_hash

DEMO_NET = REPO_ROOT / "data" / "demo" / "demo.net.xml"
STATIONS = [
    {"name": "south-west", "lon": 39.1500, "lat": 21.5440},
    {"name": "centre", "lon": 39.1571, "lat": 21.5505},
    {"name": "north-east", "lon": 39.1640, "lat": 21.5560},
]


@pytest.fixture(autouse=True)
def edge_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(E, "CACHE", tmp_path / "edges")
    import sim.loop.network as N

    monkeypatch.setattr(N, "CACHE", tmp_path / "edges")


def test_demo_policies_validate() -> None:
    for name in ("loop_demo", "loop_demo_private"):
        pol = load_loop_policy(name)
        t = loop_transform(pol)
        assert t is not None and len(t.alignments[0].stations) == 3
        assert t.assumption and "A-loop-016" in t.assumption


def test_schema_rejects_bad_policies() -> None:
    a = {"id": "x", "stations": STATIONS}
    with pytest.raises(ValidationError):  # two loop transforms
        two = [{"type": "loop_shuttle", "alignments": [a], "assumption": "t"},
               {"type": "loop_private", "alignments": [a], "assumption": "t"}]  # fmt: skip
        LoopPolicy.model_validate({"id": "p", "kind": "policy", "title": "p",
                                   "daytype": "weekday", "transforms": two})  # fmt: skip
    with pytest.raises(ValidationError):  # duplicate alignment ids
        LoopShuttle.model_validate({"type": "loop_shuttle", "alignments": [a, a],
                                    "assumption": "t"})  # fmt: skip
    with pytest.raises(ValidationError):  # provenance required
        LoopShuttle.model_validate({"type": "loop_shuttle", "alignments": [a]})


def test_capacity_scenarios_and_defaults() -> None:
    cfg = loop_config()
    m = capacity_figures("measured", 2.0, cfg)
    assert m["pair_capacity_pph"] == 1355 and m["headway_s"] == pytest.approx(3600 * 2 / 1355, 1e-3)
    e = capacity_figures("engineering", 2.0, cfg)
    assert e["headway_s"] == 1.5 and e["pair_capacity_pph"] == pytest.approx(4800)
    t = loop_transform(load_loop_policy("loop_demo"))
    p = resolve_params(t)
    assert p["alpha"] == 0.5 and p["radius_o_m"] == 450 and p["min_trip_km"] == 0.6
    assert p["occupancy"] == cfg["shuttle"]["occupancy"] and p["capacity"] == "measured"
    tp = loop_transform(load_loop_policy("loop_demo_private"))
    pp = resolve_params(tp)
    assert pp["toll_penalty_s"] == pytest.approx(10 / 40 * 3600)


def tunnel_lanes(net: Path) -> dict[str, str]:
    import xml.etree.ElementTree as ET

    out = {}
    with gzip.open(net) as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == "lane" and el.get("id", "").startswith("loop_"):
                out[el.get("id")] = el.get("allow", "")
    return out


def ramp_connections(net: Path) -> int:
    with gzip.open(net, "rt") as fh:
        return sum(1 for line in fh if "<connection " in line and 'to="loop_demo_D' in line
                   and 'from=":' not in line)  # fmt: skip


@pytest.mark.parametrize("mode", ["shuttle", "private"])
def test_build_loop_net_on_demo(mode: str, tmp_path: Path) -> None:
    from sim.loop.schema import Alignment

    before = xml_content_hash(DEMO_NET)
    al = [Alignment.model_validate({"id": "demo", "stations": STATIONS})]
    edges = E.load_edges(DEMO_NET)
    net, st, info = build_loop_net(DEMO_NET, al, mode, 90.0, tmp_path, edges)
    assert net.parent == tmp_path and net.name.startswith("demo.loop-") and net.exists()
    assert xml_content_hash(DEMO_NET) == before  # base network untouched
    assert len(st) == 3 and (st["connect_m"] < 800).all() and info["stations"] == 3
    assert 1.5 < info["alignment_km"]["demo"] < 3.0
    lanes = tunnel_lanes(net)
    want = "custom1" if mode == "shuttle" else "passenger"
    # 2 x 2 tunnel edges + 3 down + 3 up ramps, one lane each, restricted to the mode's class
    assert len(lanes) == 10 and all(a == want for a in lanes.values())
    n_conn = ramp_connections(net)
    assert (n_conn > 0) if mode == "private" else (n_conn == 0)
    again, _, _ = build_loop_net(DEMO_NET, al, mode, 90.0, tmp_path, edges)
    assert again == net  # reused, same key


def test_shuttle_route_and_meso_types(tmp_path: Path) -> None:
    assert shuttle_route("A", 0, 2) == ["loop_A_D0", "loop_A_T0_1", "loop_A_T1_2", "loop_A_U2"]
    assert shuttle_route("A", 2, 1) == ["loop_A_D2", "loop_A_T2_1", "loop_A_U1"]
    text = meso_types_file(tmp_path / "m.add.xml", 5.0, 0.1).read_text()
    assert 'tauff="50.000"' in text and "loop_tunnel" in text and "loop_ramp" in text


def test_nearest_station() -> None:
    idx, d = nearest_station(np.array([0.0, 900.0, np.nan]), np.array([0.0, 0.0, 0.0]),
                             np.array([0.0, 1000.0]), np.array([0.0, 0.0]))  # fmt: skip
    assert list(idx[:2]) == [0, 1] and d[1] == pytest.approx(100) and np.isinf(d[2])


def test_shuttles_fill_by_occupancy_and_reposition() -> None:
    pax = pd.DataFrame({"line": "A", "os": [0, 0, 0, 0, 0, 2], "ds": [2, 2, 2, 2, 2, 0],
                        "t_station": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]})  # fmt: skip
    seg = {("A", 0): 1000.0, ("A", 1): 1500.0}
    p = {"occupancy": 2.0, "empty_reposition_factor": 0.0, "dwell_s": 30.0, "speed_kmh": 90.0}
    sh = shuttles(pax, seg, p, seed=1)
    loaded = sh[~sh["empty"]]
    assert loaded["pax"].sum() == 6 and len(loaded) == 4  # 5 pax -> 3 shuttles, 1 pax -> 1
    first = loaded[(loaded["os"] == 0)].sort_values("depart")
    assert list(first["depart"]) == [20.0, 40.0, 50.0]  # leaves with its last passenger
    assert set(loaded["ride_m"]) == {2500.0}
    p["empty_reposition_factor"] = 1.0
    sh2 = shuttles(pax, seg, p, seed=1)
    back = sh2[sh2["empty"]]
    assert len(back) == 4 and (back["pax"] == 0).all()
    assert set(zip(back["os"], back["ds"], strict=True)) == {(2, 0), (0, 2)}
    assert sh2["veh_id"].is_unique
    assert shuttles(pax, seg, p, seed=1).equals(sh2)  # deterministic


def test_capacity_flags() -> None:
    # 200 sampled passengers in one hour = 2,000/h city-equivalent at 10 % > 1,355 capacity
    pax = pd.DataFrame({"line": "A", "os": 0, "ds": 1, "t_station": np.linspace(0, 3500, 200)})
    sh = pd.DataFrame({"line": "A", "os": 0, "ds": 1, "depart": np.linspace(0, 3500, 100)})
    p = {"pair_capacity_pph": 1355.0, "headway_s": 3600 * 2 / 1355}
    f = capacity_flags(pax, sh, p, 0.1)
    assert f["pair_exceedance_share"] == pytest.approx((2000 - 1355) / 2000, abs=1e-3)
    assert f["segment_peak_utilisation"] == pytest.approx(1000 / (1355 / 2), rel=1e-3)
    assert f["segment_exceedance_share"] == 1.0


def test_eval_ids_name_what_differs() -> None:
    cfg = loop_config()
    d = defaults(cfg)
    assert eval_id("C1", "shuttle", {"alpha": 0.5, "speed_kmh": None}, d) == "loop_c1"
    assert eval_id("C1", "shuttle", {"alpha": 0.3}, d) == "loop_c1_a0p3"
    assert eval_id("S", "private", {"toll_sar": 25.0, "speed_kmh": 160.0}, d) == (
        "loop_s_private_v160_toll25"
    )
    pol = make_policy("loop_x", "x", [{"id": "C1", "stations": STATIONS}], "shuttle",
                      {"alpha": 0.3, "speed_kmh": None})  # fmt: skip
    t = loop_transform(pol)
    assert isinstance(t, LoopShuttle) and t.alpha == 0.3 and t.speed_kmh is None


def test_station_placement_respects_spacing() -> None:
    from sim.loop.site import place_stations

    cfg = loop_config()
    sites = pd.DataFrame({"x": [0.0, 12000.0, 4600.0, 6000.0], "y": [0.0, 0.0, 300.0, 2500.0],
                          "score_h": [5.0, 5.0, 100.0, 1000.0], "anchor": ""})  # fmt: skip
    sx, sy, ids = place_stations(sites.iloc[0], sites.iloc[1], sites, cfg)
    sp = np.hypot(np.diff(sx), np.diff(sy))
    lo, hi = cfg["siting"]["station_spacing_m"]
    assert 4 <= len(sx) <= 8 and (sp >= lo * 0.95).all() and (sp <= hi * 1.05).all()
    assert ids[0] == 0 and ids[-1] == 1 and 2 in ids  # snapped to the nearby site
    assert 3 not in ids  # 2.5 km off the line: beyond the snap distance
    too_long = pd.DataFrame({"x": [0.0, 40000.0], "y": [0.0, 0.0], "score_h": 1.0, "anchor": ""})
    assert place_stations(too_long.iloc[0], too_long.iloc[1], too_long, cfg) is None
