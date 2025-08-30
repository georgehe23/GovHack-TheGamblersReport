# LGA Map Visualiser

This script renders an interactive Folium map from a Shapefile (or any GeoPandas-supported vector file).

Quick start (from this folder):

pip install -r requirements.txt
python visualize_lga.py --shapefile ../../AD_LGA_AREA_POLYGON.shp --out map.html

Notes:
- Shapefiles must include all companion files next to the `.shp`: `.shx`, `.dbf`, and ideally `.prj`.
- If reading the shapefile fails, convert to GeoJSON as a fallback and point `--shapefile` to that file.
- The output `map.html` opens in any web browser and includes hover tooltips, highlight, search (when a name field exists), a scale bar, and coordinates.
