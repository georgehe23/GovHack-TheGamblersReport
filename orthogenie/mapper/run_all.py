from __future__ import annotations

import argparse
import contextlib
import os
import shlex
import signal
import subprocess
import sys
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def cmd_api(host: str, port: int, reload: bool) -> int:
    # Prefer uvicorn module; use uv run if available in your workflow
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "orthogenie.mapper.vic_lga_map_api:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        args.append("--reload")
    return subprocess.call(args, cwd=REPO_ROOT)


def cmd_generate(shapefile: str, out: str, name_field: str | None, tiles: str, overlay_fields: str | None, metrics_file: str | None) -> int:
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from georgehe23.map.visualize_lga import build_map  # type: ignore
    except Exception as e:
        print(f"Failed to import map generator: {e}", file=sys.stderr)
        return 1

    overlays = [s.strip() for s in overlay_fields.split(',')] if overlay_fields else None
    build_map(
        shapefile=shapefile,
        out=out,
        name_field=name_field,
        tiles=tiles,
        overlay_fields_arg=overlays,
        metrics_file=metrics_file,
    )
    print(f"Generated map at: {out}")
    return 0


def _find_web_runner() -> list[str] | None:
    """Find an installed JS package runner (npm/pnpm/yarn). Returns argv prefix."""
    for runner in ("npm", "pnpm", "yarn"):
        path = shutil.which(runner)
        if path:
            if runner == "yarn":
                return [path]  # yarn <script>
            return [path, "run"]  # npm run / pnpm run
    return None


def cmd_devall(api_port: int, web_dir: Path | None = None) -> int:
    web_dir = web_dir or REPO_ROOT
    procs: list[subprocess.Popen] = []
    try:
        # Start Vite dev server via available runner
        runner = _find_web_runner()
        if not runner:
            print("No JS runner found (npm/pnpm/yarn). Please install Node.js and try again.", file=sys.stderr)
            return 1
        web_cmd = runner + (["web"] if runner[-1] == "run" else ["web"])  # yarn web or npm run web
        procs.append(subprocess.Popen(web_cmd, cwd=str(web_dir)))
        # Start API with reload
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "orthogenie.mapper.vic_lga_map_api:app", "--host", "0.0.0.0", "--port", str(api_port), "--reload"],
                cwd=str(REPO_ROOT),
            )
        )

        # Wait for children
        exit_codes = [p.wait() for p in procs]
        # Return first non-zero
        for code in exit_codes:
            if code != 0:
                return code
        return 0
    except KeyboardInterrupt:
        for p in procs:
            with contextlib.suppress(Exception):
                p.send_signal(signal.SIGINT)
        return 130
    finally:
        for p in procs:
            if p.poll() is None:
                with contextlib.suppress(Exception):
                    p.terminate()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Entry script: run API, generate map, or run both (dev)")
    sub = p.add_subparsers(dest="cmd")
    # Default to `dev` if no subcommand provided
    p.set_defaults(cmd="dev")

    api = sub.add_parser("api", help="Run FastAPI (Uvicorn)")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    gen = sub.add_parser("generate", help="Generate map via georgehe23/map/visualize_lga.py")
    gen.add_argument("--shapefile", "-s", required=True)
    gen.add_argument("--out", "-o", default=str(REPO_ROOT / "georgehe23" / "map" / "map.html"))
    gen.add_argument("--name-field", default=None)
    gen.add_argument("--tiles", default="CartoDB positron")
    gen.add_argument("--overlay-fields", default=None, help="Comma-separated overlay fields")
    gen.add_argument("--metrics-file", default=None, help="CSV/XLSX for FastAPI-style overlays")

    dev = sub.add_parser("dev", help="Run Vite dev server and FastAPI together")
    dev.add_argument("--api-port", type=int, default=8000)
    dev.add_argument("--web-dir", default=str(REPO_ROOT), help="Directory with package.json (Vite app)")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.cmd == "api":
        return cmd_api(args.host, args.port, not args.no_reload)
    if args.cmd == "generate":
        return cmd_generate(args.shapefile, args.out, args.name_field, args.tiles, args["overlay_fields"] if isinstance(args, dict) else args.overlay_fields, args.metrics_file)
    if args.cmd == "dev":
        api_port = getattr(args, "api_port", 8000)
        web_dir = Path(getattr(args, "web_dir", str(REPO_ROOT)))
        return cmd_devall(api_port, web_dir)
    print("Unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
