#!/usr/bin/env python3
"""
Interactive LGA map visualiser for a Shapefile using Folium.

Usage:
  python visualize_lga.py --shapefile ../../AD_LGA_AREA_POLYGON.shp --out map.html

Notes:
  - Folium renders in WGS84 (EPSG:4326). The script reprojects if needed.
  - Shapefiles require companion files (.shx, .dbf, .prj). Place them next
    to the .shp file. If missing, attribute tooltips may not work or the
    read may fail. If reading fails, the script prints a helpful message.
  - You can also pass any vector file supported by GeoPandas (e.g. GeoJSON).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _fail(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interactive map visualiser for LGA polygons")
    p.add_argument(
        "--shapefile",
        "-s",
        type=str,
        default="../../AD_LGA_AREA_POLYGON.shp",
        help="Path to shapefile (or any GeoPandas-readable vector file)",
    )
    p.add_argument(
        "--out",
        "-o",
        type=str,
        default="map.html",
        help="Output HTML file for the interactive map",
    )
    p.add_argument(
        "--name-field",
        type=str,
        default=None,
        help="Optional attribute field to use as primary label",
    )
    p.add_argument(
        "--tiles",
        type=str,
        default="CartoDB positron",
        help="Base tiles name or URL template for Folium",
    )
    return p.parse_args()


def main() -> None:
    try:
        import geopandas as gpd
        import folium
        from folium import plugins
    except ImportError as e:
        _fail(
            "Missing dependencies. Please install requirements first, e.g.\n"
            "  pip install -r requirements.txt\n\n"
            f"Details: {e}"
        )

    args = parse_args()
    shp_path = Path(args.shapefile)
    out_path = Path(args.out)

    if not shp_path.exists():
        _fail(f"Input not found: {shp_path}")

    try:
        gdf = gpd.read_file(shp_path)
    except Exception as e:
        # Common cause: missing .dbf/.shx alongside .shp
        msg = (
            f"Failed to read vector file: {shp_path}\n"
            f"Reason: {e}\n\n"
            "If using a Shapefile, ensure the companion files (.shx, .dbf, .prj)\n"
            "are present next to the .shp. Alternatively, try a GeoJSON file."
        )
        _fail(msg)

    if gdf.empty:
        _fail("The dataset is empty. Nothing to display.")

    # Reproject to WGS84 for Folium if needed
    try:
        if gdf.crs is None:
            print("Warning: CRS is undefined; assuming data is already in EPSG:4326.")
            gdf_4326 = gdf
        else:
            gdf_4326 = gdf.to_crs(epsg=4326)
    except Exception as e:
        _fail(f"Failed to project data to EPSG:4326: {e}")

    # Compute a map center using the dataset bounds
    minx, miny, maxx, maxy = gdf_4326.total_bounds
    center_lat = (miny + maxy) / 2.0
    center_lon = (minx + maxx) / 2.0

    # Choose some useful fields for tooltip
    object_cols = [c for c in gdf_4326.columns if gdf_4326[c].dtype == "object"]

    preferred_names = [
        "LGA_NAME", "LGA_NAME_2016", "LGA_NAME_2018", "LGA_NAME_2021",
        "LGA", "NAME", "NAME_2016", "NAME_2021", "STATE", "STATE_NAME",
        "REGION", "REGION_NAME",
    ]

    fields = []
    if args.name_field and args.name_field in gdf_4326.columns:
        fields.append(args.name_field)
    else:
        fields.extend([c for c in preferred_names if c in gdf_4326.columns])

    # Fill with additional object columns up to a reasonable count
    for c in object_cols:
        if c not in fields and len(fields) < 5:  # cap to keep tooltip tidy
            fields.append(c)

    # Ensure at least one field exists for tooltip; if not, skip tooltip
    use_tooltip = len(fields) > 0

    # Build the map
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles=args.tiles)

    # Add nice plugins
    try:
        plugins.Fullscreen(position="topleft").add_to(fmap)
        plugins.MousePosition(
            position="bottomleft",
            separator=" , ",
            num_digits=6,
            prefix="Lat, Lon:"
        ).add_to(fmap)
        plugins.ScaleBar(position="bottomright").add_to(fmap)
    except Exception:
        # Plugins are optional; continue if any issue
        pass

    style = lambda feature: {
        "fillColor": "#66c2a5",
        "color": "#225ea8",
        "weight": 1,
        "fillOpacity": 0.5,
    }
    highlight = lambda feature: {
        "fillColor": "#feb24c",
        "color": "#bd0026",
        "weight": 2,
        "fillOpacity": 0.7,
    }

    tooltip = None
    if use_tooltip:
        tooltip = folium.GeoJsonTooltip(fields=fields, aliases=fields, sticky=True)

    # Convert to GeoJSON string to avoid engine-dependent file pointers
    geojson_str = gdf_4326.to_json()
    geojson = json.loads(geojson_str)

    gj = folium.GeoJson(
        data=geojson,
        name="LGA Areas",
        style_function=style,
        highlight_function=highlight,
        tooltip=tooltip,
        control=True,
        smooth_factor=0.1,
        zoom_on_click=True,
        embed=False,
    )
    gj.add_to(fmap)

    # Optional: add a simple search by name if we have a likely field
    try:
        name_field = None
        for c in fields:
            if c.lower().startswith("lga") or c.lower() in ("name", "lga", "lganame"):
                name_field = c
                break
        if name_field:
            plugins.Search(
                layer=gj,
                geom_type="Polygon",
                search_label=name_field,
                placeholder="Search LGA",
                collapsed=False,
            ).add_to(fmap)
    except Exception:
        pass

    folium.LayerControl(collapsed=False).add_to(fmap)

    # Save output
    try:
        fmap.save(str(out_path))
    except Exception as e:
        _fail(f"Failed to save map HTML to {out_path}: {e}")

    print(f"Saved interactive map to: {out_path}")


if __name__ == "__main__":
    main()

