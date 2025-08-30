#!/usr/bin/env python3
"""
Master LGA map creator with interactive features (Folium).

Features:
- Accepts a GeoJSON or Shapefile input; auto-reprojects Shapefiles to WGS84.
- Tooltips with common LGA name fields; highlight on hover.
- Plugins: Fullscreen, Mouse position, Scale bar, Search by LGA name.
- Optional choropleth overlays using numeric fields in the GeoJSON properties.

Usage (examples):
  # Using GeoJSON (recommended)
  python visualize_lga.py --shapefile ../../data/vic_lga_boundaries.geojson --out map.html \
    --overlay-fields "Expenditure per EGM,Unemployment Rate,EGMs per 1000 Adults"

  # Using a Shapefile (requires sidecar files: .dbf, .shx, .prj)
  python visualize_lga.py --shapefile ../../AD_LGA_AREA_POLYGON.shp --out map.html

Notes:
  - Folium renders in WGS84 (EPSG:4326). The script reprojects if needed.
  - For Shapefiles, ensure companion files (.shx, .dbf, .prj) are present.
  - To color polygons by metrics, pass --overlay-fields with property names that exist in the GeoJSON features.
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
    p = argparse.ArgumentParser(description="Master LGA map creator for LGA polygons")
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
    p.add_argument(
        "--overlay-fields",
        type=str,
        default=None,
        help=(
            "Comma-separated property names to choropleth. "
            "These must exist in the GeoJSON feature properties."
        ),
    )
    p.add_argument(
        "--metrics-file",
        type=str,
        default=None,
        help="Optional CSV/XLSX with LGA metrics to overlay (FastAPI-style aggregation)",
    )
    return p.parse_args()


def build_map(
    shapefile: str | Path,
    out: str | Path,
    name_field: str | None = None,
    tiles: str = "CartoDB positron",
    overlay_fields_arg: list[str] | None = None,
    metrics_file: str | Path | None = None,
) -> Path:
    """Builds the interactive LGA map and writes it to `out`.

    Returns the output path.
    """
    try:
        import folium  # type: ignore
        from folium import plugins  # type: ignore
    except ImportError as e:
        _fail("Missing folium. Install with: pip install folium\n\n" + f"Details: {e}")

    shp_path = Path(shapefile)
    out_path = Path(out)
    if not shp_path.exists():
        _fail(f"Input not found: {shp_path}")

    is_geojson = shp_path.suffix.lower() in {".geojson", ".json"}

    # Load geometry either via GeoJSON or GeoPandas for Shapefiles
    if is_geojson:
        try:
            with open(shp_path, "r", encoding="utf-8") as f:
                geojson = json.load(f)
        except Exception as e:
            _fail(f"Failed to read GeoJSON: {e}")
    else:
        try:
            import geopandas as gpd  # type: ignore
        except ImportError as e:
            _fail("Reading Shapefiles requires GeoPandas. Install with: pip install geopandas\n\n" + f"Details: {e}")
        try:
            gdf = gpd.read_file(shp_path)
        except Exception as e:
            _fail(f"Failed to read vector file: {shp_path}\nReason: {e}\nEnsure .shx/.dbf/.prj exist or use GeoJSON.")
        if gdf.empty:
            _fail("The dataset is empty. Nothing to display.")
        try:
            gdf_4326 = gdf if gdf.crs is None else gdf.to_crs(epsg=4326)
        except Exception as e:
            _fail(f"Failed to project data to EPSG:4326: {e}")
        geojson = json.loads(gdf_4326.to_json())

    # Determine center from bounds
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
        _fail("Could not determine bounds from geometry.")
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2.0
    center_lon = (minx + maxx) / 2.0

    # Choose tooltip fields
    preferred_names = [
        "LGA_NAME", "LGA_NAME_2016", "LGA_NAME_2018", "LGA_NAME_2021",
        "LGA", "NAME", "NAME_2016", "NAME_2021", "STATE", "STATE_NAME",
        "REGION", "REGION_NAME",
    ]
    first_props = next((f.get("properties", {}) for f in geojson.get("features", []) if f.get("properties")), {})
    fields = []
    if name_field and name_field in first_props:
        fields.append(name_field)
    else:
        fields.extend([c for c in preferred_names if c in first_props])
    for k, v in first_props.items():
        if isinstance(v, (str, int, float)) and k not in fields and len(fields) < 5:
            fields.append(k)
    use_tooltip = len(fields) > 0

    # Build the map with plugins
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles=tiles)
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

    # Optional search by name
    try:
        search_field = None
        for c in fields:
            if c.lower().startswith("lga") or c.lower() in ("name", "lga", "lganame"):
                search_field = c
                break
        if search_field:
            plugins.Search(layer=gj, geom_type="Polygon", search_label=search_field, placeholder="Search LGA", collapsed=False).add_to(fmap)
    except Exception:
        pass

    # --- Choropleth overlays ---
    # Option A: If a metrics_file is provided, aggregate like the FastAPI endpoint and key on the map's name field
    def _clean_lga_name(name: str) -> str:
        n = str(name).upper()
        for token in ['CITY OF ', 'SHIRE OF ', 'RURAL CITY OF ', 'BOROUGH OF ', ' (CITY)', ' (SHIRE)', ' (RURAL CITY)', ' (BOROUGH)']:
            n = n.replace(token, '')
        return ' '.join(n.split()).strip()

    metrics_df = None
    if metrics_file is not None:
        import pandas as pd  # type: ignore
        mf_path = Path(metrics_file)
        if mf_path.exists():
            if mf_path.suffix.lower() == '.csv':
                dfm = pd.read_csv(mf_path)
            else:
                dfm = pd.read_excel(mf_path)
            lga_2023_24_columns = [
                'LGA Name', 'LGA', 'Region', 'TOTAL Net Expenditure ($)',
                'SEIFA DIS Score', 'SEIFADIS Rank State', 'SEIFA DIS RANK COUNTRY',
                'SEIFA DIS RANK METRO', 'SEIFA ADVDIS Score', 'SEIFA ADVDIS Rank State',
                'SEIFA ADVDIS RANK COUNTRY', 'SEIFA ADVDIS RANK METRO',
                'Adult Population 2022', 'Adults per Venue 2022',
                'EGMs per 1,000 Adults 2022', 'EXP per Adult 2022',
                'Unemployed Workforce as at June 2022', 'as at June 2022',
                'Unemployment rate as at June 2022'
            ]
            if len(dfm.columns) == len(lga_2023_24_columns):
                dfm.columns = lga_2023_24_columns
            lga_col = 'LGA Name' if 'LGA Name' in dfm.columns else dfm.columns[0]
            exp_col = 'TOTAL Net Expenditure ($)' if 'TOTAL Net Expenditure ($)' in dfm.columns else None
            egm_col = 'EGMs per 1,000 Adults 2022' if 'EGMs per 1,000 Adults 2022' in dfm.columns else None
            unemp_col = 'Unemployment rate as at June 2022' if 'Unemployment rate as at June 2022' in dfm.columns else None
            adults_col = 'Adult Population 2022' if 'Adult Population 2022' in dfm.columns else None
            for c in [exp_col, egm_col, unemp_col, adults_col]:
                if c and c in dfm.columns:
                    dfm[c] = pd.to_numeric(dfm[c], errors='coerce')
            if adults_col and adults_col in dfm.columns:
                dfm = dfm[(dfm[adults_col].notnull()) & (dfm[adults_col] > 0)]
            dfm['LGA_NAME_CLEAN'] = dfm[lga_col].apply(_clean_lga_name)
            agg = {}
            if exp_col: agg[exp_col] = 'sum'
            if egm_col: agg[egm_col] = 'mean'
            if unemp_col: agg[unemp_col] = 'mean'
            if adults_col: agg[adults_col] = 'sum'
            metrics_df = dfm.groupby('LGA_NAME_CLEAN').agg(agg)
            if exp_col and egm_col and adults_col:
                metrics_df['Expenditure per EGM'] = metrics_df[exp_col] / (metrics_df[adults_col] * metrics_df[egm_col] / 1000)
            if unemp_col:
                metrics_df['Unemployment Rate'] = metrics_df[unemp_col]
            if egm_col:
                metrics_df['EGMs per 1000 Adults'] = metrics_df[egm_col]
            metrics_df = metrics_df.reset_index()

    overlay_fields = overlay_fields_arg if overlay_fields_arg is not None else [
        "Expenditure per EGM",
        "Unemployment Rate",
        "EGMs per 1000 Adults",
    ]
    label_field = search_field or (name_field if name_field else (fields[0] if fields else None))

    if label_field:
        try:
            import pandas as pd  # type: ignore
            if metrics_df is not None:
                # Use aggregated metrics keyed by cleaned LGA name
                for of in overlay_fields:
                    if of in metrics_df.columns:
                        folium.Choropleth(
                            geo_data=geojson,
                            name=of,
                            data=metrics_df,
                            columns=['LGA_NAME_CLEAN', of],
                            key_on=f'feature.properties.{label_field}',
                            fill_color='YlOrRd',
                            fill_opacity=0.7,
                            line_opacity=0.2,
                            legend_name=of,
                            nan_fill_color='white',
                            highlight=True,
                        ).add_to(fmap)
            else:
                # Fall back to using existing numeric properties in GeoJSON
                rows = []
                for f in geojson.get("features", []):
                    props = f.get("properties", {})
                    if label_field in props:
                        row = {"__name": props.get(label_field)}
                        for of in overlay_fields:
                            val = props.get(of)
                            if isinstance(val, (int, float)):
                                row[of] = val
                        rows.append(row)
                if rows:
                    df_props = pd.DataFrame(rows)
                    for of in overlay_fields:
                        if of in df_props.columns:
                            folium.Choropleth(
                                geo_data=geojson,
                                name=of,
                                data=df_props,
                                columns=["__name", of],
                                key_on=f"feature.properties.{label_field}",
                                fill_color='YlOrRd',
                                fill_opacity=0.7,
                                line_opacity=0.2,
                                legend_name=of,
                                nan_fill_color='white',
                                highlight=True,
                            ).add_to(fmap)
        except Exception:
            pass

    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(str(out_path))
    return out_path


def main() -> None:
    args = parse_args()
    overlay_list = [f.strip() for f in args.overlay_fields.split(',')] if args.overlay_fields else None
    build_map(
        shapefile=args.shapefile,
        out=args.out,
        name_field=args.name_field,
        tiles=args.tiles,
        overlay_fields_arg=overlay_list,
        metrics_file=args.metrics_file,
    )
    print(f"Saved interactive map to: {args.out}")


if __name__ == "__main__":
    main()

