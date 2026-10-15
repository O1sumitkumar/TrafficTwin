# web: network viewer (M1 stub)

Single static page (Vite + MapLibre, no API keys) that draws the Tier A network edges coloured by
posted speed and the district boundaries, so the city network can be eyeballed. The full deck.gl
viewer (time slider, edge-bin playback, Tier B vehicles) is M3.

```bash
uv run python -m sim.network.build_city     # writes public/data/edges.geojson + districts.geojson
cd web && npm install --include=dev && npm run dev    # http://localhost:5173
```
`public/data/` is generated and gitignored (ODbL-derived). The optional basemap uses
tile.openstreetmap.org raster tiles with attribution (light, interactive use only).
