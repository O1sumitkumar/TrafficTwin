import { defineConfig } from "vite";

// Static network viewer (M1 stub). Data is generated into public/data/ by
// `python -m sim.network.build_city` (gitignored; ODbL-derived).
export default defineConfig({
  server: { port: 5173 },
});
