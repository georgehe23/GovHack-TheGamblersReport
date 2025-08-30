from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


@dataclass
class PipelineResult:
    enriched_geojson: Optional[Path]
    map_html: Path
    summary: Dict


def _normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    return "".join(ch for ch in name.upper() if ch.isalnum() or ch.isspace()).strip()


def _read_tabular(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in {".xls", ".xlsx"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {path}")


def _detect_lga_column(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "LGA_NAME", "LGA", "LGA Name", "LGA_NAME_2021", "Local Government Area", "LG A",
        "lga", "lga_name", "name", "LGA_NAME_2016", "AREA_NAME",
    ]
    cols_lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    # Fallback: any column with 'lga' in the name
    for c in df.columns:
        if "lga" in c.lower() and df[c].dtype == object:
            return c
    return None


def _detect_value_columns(df: pd.DataFrame) -> List[str]:
    # Heuristic: numeric columns that look like expenditures or losses
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    priority = [c for c in numeric_cols if any(k in c.lower() for k in ["exp", "loss", "amount", "value"]) ]
    return priority or numeric_cols[:1]


def aggregate_to_lga(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for df in dfs:
        lga_col = _detect_lga_column(df)
        if not lga_col:
            continue
        val_cols = _detect_value_columns(df)
        if not val_cols:
            continue
        tmp = df[[lga_col] + val_cols].copy()
        tmp.columns = ["LGA_NAME"] + [f"metric_{i+1}" for i in range(len(val_cols))]
        # Normalize names for grouping
        tmp["_key"] = tmp["LGA_NAME"].map(_normalize_name)
        g = tmp.groupby(["_key", "LGA_NAME"], dropna=False).sum(numeric_only=True).reset_index()
        rows.append(g)

    if not rows:
        return pd.DataFrame(columns=["_key", "LGA_NAME", "metric_1"])  # empty

    combined = pd.concat(rows, ignore_index=True)
    grouped = combined.groupby(["_key", "LGA_NAME"], dropna=False).sum(numeric_only=True).reset_index()
    return grouped


def enrich_geojson(base_geojson: Path, lga_metrics: pd.DataFrame) -> Dict:
    gj = json.loads(base_geojson.read_text(encoding="utf-8"))

    # Determine candidate name fields in GeoJSON properties
    name_candidates = [
        "LGA_NAME", "LGA_NAME_2021", "LGA_NAME_2016", "lga_name", "NAME", "name", "lga"
    ]

    # Build lookup from metrics
    metrics_by_key = {
        _normalize_name(row["LGA_NAME"]): {k: row[k] for k in lga_metrics.columns if k.startswith("metric_")}
        for _, row in lga_metrics.iterrows()
    }

    attached = 0
    for feat in gj.get("features", []):
        props = feat.setdefault("properties", {})
        # try each candidate field to find a match
        matched_key = None
        for cand in name_candidates:
            if cand in props and props[cand]:
                key = _normalize_name(str(props[cand]))
                if key in metrics_by_key:
                    matched_key = key
                    break
        # fallback: try common 'name'
        if not matched_key and "name" in props:
            key = _normalize_name(str(props["name"]))
            if key in metrics_by_key:
                matched_key = key

        if matched_key:
            props.update(metrics_by_key[matched_key])
            attached += 1

    gj["properties"] = gj.get("properties", {})
    gj["properties"]["_attached_count"] = attached
    gj["properties"]["_total_features"] = len(gj.get("features", []))
    return gj


def write_geojson(obj: Dict, path: Path) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def call_map_generator(geojson_path: Path, out_html: Path, name_field: Optional[str], tiles: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "georgehe23" / "map" / "visualize_lga.py"
    cmd = [
        sys.executable,
        str(script),
        "--shapefile",
        str(geojson_path),
        "--out",
        str(out_html),
        "--tiles",
        tiles,
    ]
    if name_field:
        cmd += ["--name-field", name_field]
    subprocess.check_call(cmd)


def run_pipeline(
    input_files: Iterable[Path],
    base_geojson: Path,
    data_dir: Path,
    output_dir: Path,
    map_name_field: Optional[str] = None,
    map_tiles: str = "CartoDB positron",
) -> PipelineResult:
    # Load uploaded tables
    dfs = []
    for p in input_files:
        try:
            dfs.append(_read_tabular(p))
        except Exception:
            continue

    lga_metrics = aggregate_to_lga(dfs)

    # Enrich the base GeoJSON with metrics (if any)
    enriched = enrich_geojson(base_geojson, lga_metrics)
    enriched_path = output_dir / "enriched.geojson"
    write_geojson(enriched, enriched_path)

    # Build a small summary for the UI
    summary = {
        "uploaded_files": [Path(p).name for p in input_files],
        "lgas_with_metrics": int(enriched.get("properties", {}).get("_attached_count", 0)),
        "total_lgas": int(enriched.get("properties", {}).get("_total_features", 0)),
    }

    # Call existing map generator to render HTML
    map_html = output_dir / "map.html"
    call_map_generator(enriched_path, map_html, map_name_field, map_tiles)

    return PipelineResult(
        enriched_geojson=enriched_path,
        map_html=map_html,
        summary=summary,
    )

