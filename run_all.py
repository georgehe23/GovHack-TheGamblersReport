from __future__ import annotations

import sys


def main() -> int:
    # Delegate to the canonical entry under orthogenie/mapper
    try:
        from orthogenie.mapper.run_all import main as _main  # type: ignore
    except Exception as e:
        print(f"Failed to import orthogenie.mapper.run_all: {e}", file=sys.stderr)
        return 1
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())

