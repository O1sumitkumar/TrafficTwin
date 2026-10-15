import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";

// Edge colour by posted speed (km/h), from the network's lane speeds.
const SPEED_STOPS: Array<[number, string]> = [
  [0, "#4c566a"],
  [40, "#88c0d0"],
  [60, "#a3be8c"],
  [80, "#ebcb8b"],
  [100, "#d08770"],
  [120, "#bf616a"],
];

// No API keys: OSM raster tiles as an optional basemap, with attribution.
const style: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "(c) OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#0e1116" } },
    { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.35 } },
  ],
};

const map = new maplibregl.Map({
  container: "map",
  style,
  center: [39.18, 21.55],
  zoom: 10.5,
});
map.addControl(new maplibregl.NavigationControl(), "top-right");

function byId<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
}

async function loadJson(url: string): Promise<FeatureCollection> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status} (run python -m sim.network.build_city)`);
  return (await res.json()) as FeatureCollection;
}

map.on("load", async () => {
  const stats = byId<HTMLDivElement>("stats");
  try {
    const [edges, districts] = await Promise.all([
      loadJson("/data/edges.geojson"),
      loadJson("/data/districts.geojson"),
    ]);
    map.addSource("districts", { type: "geojson", data: districts });
    map.addLayer({
      id: "districts-fill",
      type: "fill",
      source: "districts",
      paint: { "fill-color": "#5e81ac", "fill-opacity": 0.08 },
    });
    map.addLayer({
      id: "districts-line",
      type: "line",
      source: "districts",
      paint: { "line-color": "#81a1c1", "line-width": 1, "line-dasharray": [2, 2] },
    });
    map.addSource("edges", { type: "geojson", data: edges });
    const colour: unknown[] = ["interpolate", ["linear"], ["get", "speed_kmh"]];
    for (const [speed, c] of SPEED_STOPS) colour.push(speed, c);
    map.addLayer({
      id: "edges",
      type: "line",
      source: "edges",
      paint: {
        "line-color": colour as maplibregl.ExpressionSpecification,
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, ["*", 0.4, ["get", "lanes"]], 16, ["*", 2, ["get", "lanes"]]],
      },
    });
    stats.textContent = `${edges.features.length.toLocaleString()} edges, ${districts.features.length} districts`;
    byId<HTMLDivElement>("legend").innerHTML = SPEED_STOPS.map(
      ([s, c]) => `<div><span class="swatch" style="background:${c}"></span>${s}+ km/h</div>`,
    ).join("");

    const popup = new maplibregl.Popup({ closeButton: false });
    map.on("click", "edges", (e) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      popup
        .setLngLat(e.lngLat)
        .setHTML(`<b>${p.name || "(unnamed)"}</b><br>${p.id}<br>${p.type}<br>${p.lanes} lanes, ${p.speed_kmh} km/h`)
        .addTo(map);
    });
    map.on("click", "districts-fill", (e) => {
      const p = e.features?.[0]?.properties;
      if (!p || map.queryRenderedFeatures(e.point, { layers: ["edges"] }).length) return;
      popup.setLngLat(e.lngLat).setHTML(`<b>${p.name_ar ?? ""}</b><br>${p.name_en ?? ""}<br>${p.area_km2} km²`).addTo(map);
    });
  } catch (err) {
    stats.textContent = String(err);
  }
});

byId<HTMLInputElement>("basemap").addEventListener("change", (e) => {
  map.setLayoutProperty("osm", "visibility", (e.target as HTMLInputElement).checked ? "visible" : "none");
});
byId<HTMLInputElement>("districts").addEventListener("change", (e) => {
  const v = (e.target as HTMLInputElement).checked ? "visible" : "none";
  map.setLayoutProperty("districts-fill", "visibility", v);
  map.setLayoutProperty("districts-line", "visibility", v);
});
