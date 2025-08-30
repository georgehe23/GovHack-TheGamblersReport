#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import streamlit as st

from backend import run_pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


st.set_page_config(page_title="Gambling Harm Visualiser", layout="wide")

st.title("Gambling Harm Visualiser")
st.write(
    "Upload one or more gaming expenditure files (CSV or Excel). The app will combine them with "
    "historical, locational, socioeconomic, and educational data in `data/`, enrich the LGA GeoJSON, "
    "generate an updated interactive map, and display it below."
)

with st.expander("Configuration", expanded=False):
    default_geojson = DATA_DIR / "vic_lga_boundaries.geojson"
    geojson_path = st.text_input(
        "Base LGA GeoJSON path",
        value=str(default_geojson),
        help="GeoJSON that defines the LGA polygons to enrich with metrics.",
    )
    name_field = st.text_input(
        "Optional name field for map tooltips",
        value="",
        help="If set, used as primary label in the map tooltips",
    )
    basemap = st.text_input(
        "Basemap tiles",
        value="CartoDB positron",
        help="Folium tile layer name or URL template",
    )

uploaded = st.file_uploader(
    "Upload gaming expenditure file(s) (CSV/XLS/XLSX)",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=True,
)

run = st.button("Run Analysis and Generate Map", type="primary", disabled=not uploaded)

if run and uploaded:
    with st.spinner("Processing files and generating map…"):
        # Save uploads to a temp area under output
        uploads_dir = OUTPUT_DIR / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []
        for uf in uploaded:
            dest = uploads_dir / uf.name
            dest.write_bytes(uf.getbuffer())
            saved_paths.append(dest)

        try:
            result = run_pipeline(
                input_files=saved_paths,
                base_geojson=Path(geojson_path),
                data_dir=DATA_DIR,
                output_dir=OUTPUT_DIR,
                map_name_field=name_field or None,
                map_tiles=basemap,
            )
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.stop()

    # Show summary
    st.success("Pipeline completed.")
    if result.summary:
        st.subheader("Summary Metrics")
        st.json(result.summary)

    # Embed generated map
    st.subheader("Interactive Map")
    try:
        html = Path(result.map_html).read_text(encoding="utf-8")
        st.components.v1.html(html, height=720, scrolling=True)
        st.download_button(
            label="Download map.html",
            data=html,
            file_name=Path(result.map_html).name,
            mime="text/html",
        )
    except Exception as e:
        st.error(f"Could not display map: {e}")

    # Offer enriched GeoJSON download
    if result.enriched_geojson and Path(result.enriched_geojson).exists():
        try:
            geojson_text = Path(result.enriched_geojson).read_text(encoding="utf-8")
            st.download_button(
                label="Download enriched.geojson",
                data=geojson_text,
                file_name=Path(result.enriched_geojson).name,
                mime="application/geo+json",
            )
        except Exception:
            pass

