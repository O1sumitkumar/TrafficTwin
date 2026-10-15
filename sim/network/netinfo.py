"""Streaming network statistics and GeoJSON export of edges (no full sumolib load).

python -m sim.network.netinfo stats data/jeddah/jeddah.net.xml
python -m sim.network.netinfo edges-geojson data/jeddah/jeddah.net.xml web/public/data/edges.geojson
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

import typer
from pyproj import Transformer

from sim.common import content_hash


@dataclass
class NetStats:
    edges: int
    junctions: int
    traffic_lights: int
    lanes: int
    lane_km: float
    edge_km: float
    net_hash: str

    def as_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


def net_stats(net: Path) -> NetStats:
    """Count non-internal edges, non-internal junctions, TLS programs and lane-km."""
    edges = junctions = lanes = 0
    tls_ids: set[str] = set()
    lane_m = edge_m = 0.0
    in_edge = False
    first_lane = True
    for event, elem in ET.iterparse(net, events=("start", "end")):
        tag = elem.tag
        if event == "start":
            if tag == "edge":
                in_edge = elem.get("function") != "internal"
                first_lane = True
            continue
        if tag == "lane" and in_edge:
            length = float(elem.get("length", 0.0))
            lanes += 1
            lane_m += length
            if first_lane:
                edge_m += length
                first_lane = False
        elif tag == "edge":
            if in_edge:
                edges += 1
            in_edge = False
            elem.clear()
        elif tag == "junction":
            if elem.get("type") != "internal":
                junctions += 1
            elem.clear()
        elif tag == "tlLogic":
            tls_ids.add(elem.get("id", ""))
            elem.clear()
    return NetStats(
        edges=edges,
        junctions=junctions,
        traffic_lights=len(tls_ids),
        lanes=lanes,
        lane_km=round(lane_m / 1000.0, 2),
        edge_km=round(edge_m / 1000.0, 2),
        net_hash=content_hash(net),
    )


def _location(net: Path) -> tuple[float, float, str]:
    for _, elem in ET.iterparse(net, events=("end",)):
        if elem.tag == "location":
            dx, dy = (float(v) for v in elem.get("netOffset", "0,0").split(","))
            return dx, dy, elem.get("projParameter", "!")
    raise ValueError(f"{net}: no <location> element")


def edges_geojson(net: Path, out: Path, precision: int = 5) -> int:
    """Write non-internal edges as LineStrings in WGS84; return the feature count."""
    dx, dy, proj = _location(net)
    if proj == "!":
        raise ValueError(f"{net}: network has no geo projection")
    to_geo = Transformer.from_crs(proj, "EPSG:4326", always_xy=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    current: dict[str, str] | None = None
    shape: str | None = None
    lanes = 0
    with out.open("w") as fh:
        fh.write('{"type":"FeatureCollection","features":[\n')
        for event, elem in ET.iterparse(net, events=("start", "end")):
            if event == "start":
                if elem.tag == "edge" and elem.get("function") != "internal":
                    current = dict(elem.attrib)
                    shape = elem.get("shape")
                    lanes = 0
                continue
            if elem.tag == "lane" and current is not None:
                lanes += 1
                if shape is None:
                    shape = elem.get("shape")
                current.setdefault("speed", elem.get("speed", ""))
            elif elem.tag == "edge":
                if current is not None and shape:
                    xs, ys = zip(
                        *(
                            (float(a) - dx, float(b) - dy)
                            for a, b in (p.split(",")[:2] for p in shape.split())
                        ),
                        strict=True,
                    )
                    lon, lat = to_geo.transform(xs, ys)
                    coords = [
                        [round(x, precision), round(y, precision)]
                        for x, y in zip(lon, lat, strict=True)
                    ]
                    feature = {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {
                            "id": current.get("id"),
                            "name": current.get("name", ""),
                            "type": current.get("type", ""),
                            "lanes": lanes,
                            "speed_kmh": round(float(current.get("speed") or 0) * 3.6),
                        },
                    }
                    fh.write(
                        ("," if count else "") + json.dumps(feature, ensure_ascii=False) + "\n"
                    )
                    count += 1
                current = None
                shape = None
                elem.clear()
            elif elem.tag in ("junction", "connection", "tlLogic"):
                elem.clear()
        fh.write("]}\n")
    return count


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def stats(net: Path) -> None:
    """Print network statistics as JSON."""
    typer.echo(json.dumps(net_stats(net).as_dict(), indent=2))


@app.command("edges-geojson")
def edges_geojson_cmd(net: Path, out: Path) -> None:
    """Export edges to GeoJSON for the viewer."""
    n = edges_geojson(net, out)
    typer.echo(f"wrote {n} edges -> {out}")


if __name__ == "__main__":
    app()
