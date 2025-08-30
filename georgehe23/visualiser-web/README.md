## Visualiser Web (React + Vite + Tailwind)

Client-side web app that:
- Loads base LGA GeoJSON (default path `../../data/vic_lga_boundaries.geojson` in dev)
- Accepts CSV/XLS/XLSX uploads similar to gaming expenditure files
- Aggregates numeric columns by LGA heuristically and merges metrics into the GeoJSON
- Renders an interactive map (React Leaflet) with choropleth styling by a chosen metric

### Dev setup

1) Install Node 18+ and pnpm/npm/yarn
2) Install deps:
   - npm: `npm install`
   - pnpm: `pnpm install`
   - yarn: `yarn`
3) Start dev server:
   - npm: `npm run dev`
4) Open the printed localhost URL

Default map.html
- If you have a pre-generated `map.html` from the Python script, place it at `georgehe23/visualiser-web/public/map.html`.
- The app will display it by default on load. Later, you can upload files and click "Process & Merge" to replace it with an enriched, client-side view.

Notes:
- `vite.config.ts` allows reading files from the repo root in dev so you can fetch `../../data/vic_lga_boundaries.geojson` directly.
- In production, copy your GeoJSON to the web root or use a URL, and update the path in the UI.
- No backend is required; parsing and joining happen in the browser. If you later add a backend, swap the merge logic accordingly.
