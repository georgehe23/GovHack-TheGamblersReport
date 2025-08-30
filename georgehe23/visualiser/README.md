# Visualiser Frontend

A Streamlit app that:
- Accepts gaming expenditure file(s) (CSV/XLS/XLSX)
- Combines them with reference data in `data/` (pipeline is a heuristic stub)
- Enriches the LGA GeoJSON
- Calls the existing map generator to produce `map.html`
- Displays the interactive map inline and offers downloads

## Quick start

1) Create and activate a virtual environment (recommended)

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2) Install dependencies

```
pip install -r georgehe23/map/requirements.txt
pip install -r georgehe23/visualiser/requirements.txt
```

3) Run the app

```
streamlit run georgehe23/visualiser/app.py
```

4) In the browser: upload one or more gaming expenditure files and click "Run Analysis and Generate Map".

Notes:
- The pipeline (`backend.py`) includes heuristics to detect an LGA column and numeric metric columns. Adjust to your data schema as needed.
- The map generator is reused from `georgehe23/map/visualize_lga.py` and defaults to `data/vic_lga_boundaries.geojson`.
- Outputs are saved to `georgehe23/visualiser/output/`.

