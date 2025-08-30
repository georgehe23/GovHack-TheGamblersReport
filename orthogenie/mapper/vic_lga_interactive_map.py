from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wrapper: calls the master LGA map generator in georgehe23/map")
    p.add_argument("--shapefile", "-s", type=str, default="../../vic_lga_boundaries.geojson", help="Path to GeoJSON or Shapefile")
    p.add_argument("--out", "-o", type=str, default="../../vic_lga_expenditure_per_egm_map.html", help="Output HTML path")
    p.add_argument("--name-field", type=str, default=None, help="Property name used as LGA label/search field")
    p.add_argument("--tiles", type=str, default="CartoDB positron", help="Base tile layer")
    p.add_argument("--overlay-fields", type=str, default=None, help="Comma-separated property names to choropleth")
    return p.parse_args()


def main() -> None:
    # Make repo root importable
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    try:
        from georgehe23.map.visualize_lga import build_map  # type: ignore
    except Exception as e:
        print(f"Failed to import master map generator: {e}", file=sys.stderr)
        sys.exit(1)

    args = parse_args()
    overlays = [s.strip() for s in args.overlay_fields.split(',')] if args.overlay_fields else None
    build_map(
        shapefile=args.shapefile,
        out=args.out,
        name_field=args.name_field,
        tiles=args.tiles,
        overlay_fields_arg=overlays,
    )
    print(f"Interactive map saved to {args.out}")


if __name__ == "__main__":
    main()
