#!/usr/bin/env python3
"""
Interactive LGA map visualiser for a Shapefile using Folium.

Usage:
  python visualize_lga.py --shapefile ../../data/vic_lga_boundaries.geojson --out map.html

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
        default="../../data/vic_lga_boundaries.geojson",
        help="Path to GeoJSON or Shapefile (GeoPandas-readable)",
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
    # Parse args first so we can handle GeoJSON without GeoPandas if desired
    args = parse_args()
    shp_path = Path(args.shapefile)
    out_path = Path(args.out)

    if not shp_path.exists():
        _fail(f"Input not found: {shp_path}")

    is_geojson = shp_path.suffix.lower() in {".geojson", ".json"}

    # Import folium and optional geopandas depending on input type
    try:
        import folium
        from folium import plugins
        gpd = None
        if not is_geojson:
            import geopandas as gpd  # type: ignore
    except ImportError as e:
        _fail(
            "Missing dependencies. Install with:\n"
            "  pip install -r requirements.txt\n"
            "Or for GeoJSON only: pip install folium\n\n"
            f"Details: {e}"
        )

    # Data loading branch: GeoJSON (no GeoPandas) or Shapefile (GeoPandas)
    if is_geojson:
        try:
            with open(shp_path, "r", encoding="utf-8") as f:
                geojson = json.load(f)
        except Exception as e:
            _fail(f"Failed to read GeoJSON: {e}")

        # Extract bounds from coordinates
        def _walk_coords(obj, acc):
            if isinstance(obj, list):
                if len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
                    x, y = obj
                    acc[0] = min(acc[0], x)
                    acc[1] = min(acc[1], y)
                    acc[2] = max(acc[2], x)
                    acc[3] = max(acc[3], y)
                else:
                    for it in obj:
                        _walk_coords(it, acc)

        bounds = [float("inf"), float("inf"), float("-inf"), float("-inf")]
        for feat in geojson.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            _walk_coords(geom.get("coordinates"), bounds)
        if any(v in (float("inf"), float("-inf")) for v in bounds):
            _fail("Could not determine bounds from GeoJSON coordinates.")
        minx, miny, maxx, maxy = bounds
        center_lat = (miny + maxy) / 2.0
        center_lon = (minx + maxx) / 2.0

        # Determine tooltip fields from properties
        fields = []
        try:
            first_props = next(
                (f.get("properties", {}) for f in geojson.get("features", []) if f.get("properties")),
                {}
            )
            fields = list(first_props.keys())[:5]
        except Exception:
            fields = []
        use_tooltip = len(fields) > 0

        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles=args.tiles)
        try:
            plugins.Fullscreen(position="topleft").add_to(fmap)
            plugins.MousePosition(position="bottomleft", separator=" , ", num_digits=6, prefix="Lat, Lon:").add_to(fmap)
            plugins.ScaleBar(position="bottomright").add_to(fmap)
        except Exception:
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

        tooltip = folium.GeoJsonTooltip(fields=fields, aliases=fields, sticky=True) if use_tooltip else None
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

        # Optional search
        try:
            name_field = None
            for c in fields:
                cl = c.lower()
                if cl.startswith("lga") or cl in ("name", "lga", "lganame"):
                    name_field = c
                    break
            if name_field:
                plugins.Search(layer=gj, geom_type="Polygon", search_label=name_field, placeholder="Search LGA", collapsed=False).add_to(fmap)
        except Exception:
            pass

    else:
        # Shapefile or other vector: use GeoPandas
        try:
            gdf = gpd.read_file(shp_path)  # type: ignore
        except Exception as e:
            msg = (
                f"Failed to read vector file: {shp_path}\n"
                f"Reason: {e}\n\n"
                "If using a Shapefile, ensure the companion files (.shx, .dbf, .prj) are present.\n"
                "Alternatively, convert to GeoJSON and pass that instead."
            )
            _fail(msg)

        if gdf.empty:
            _fail("The dataset is empty. Nothing to display.")

        try:
            if gdf.crs is None:
                print("Warning: CRS is undefined; assuming data is already in EPSG:4326.")
                gdf_4326 = gdf
            else:
                gdf_4326 = gdf.to_crs(epsg=4326)
        except Exception as e:
            _fail(f"Failed to project data to EPSG:4326: {e}")

        minx, miny, maxx, maxy = gdf_4326.total_bounds
        center_lat = (miny + maxy) / 2.0
        center_lon = (minx + maxx) / 2.0

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
        for c in object_cols:
            if c not in fields and len(fields) < 5:
                fields.append(c)
        use_tooltip = len(fields) > 0

        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles=args.tiles)
        try:
            plugins.Fullscreen(position="topleft").add_to(fmap)
            plugins.MousePosition(position="bottomleft", separator=" , ", num_digits=6, prefix="Lat, Lon:").add_to(fmap)
            plugins.ScaleBar(position="bottomright").add_to(fmap)
        except Exception:
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

        tooltip = folium.GeoJsonTooltip(fields=fields, aliases=fields, sticky=True) if use_tooltip else None
        geojson = json.loads(gdf_4326.to_json())
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

        try:
            name_field = None
            for c in fields:
                cl = c.lower()
                if cl.startswith("lga") or cl in ("name", "lga", "lganame"):
                    name_field = c
                    break
            if name_field:
                plugins.Search(layer=gj, geom_type="Polygon", search_label=name_field, placeholder="Search LGA", collapsed=False).add_to(fmap)
        except Exception:
            pass

    folium.LayerControl(collapsed=False).add_to(fmap)

    try:
        fmap.save(str(out_path))
    except Exception as e:
        _fail(f"Failed to save map HTML to {out_path}: {e}")

    print(f"Saved interactive map to: {out_path}")


if __name__ == "__main__":
    main()
