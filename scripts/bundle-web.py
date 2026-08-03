#!/usr/bin/env python3
"""Copy a built web client into the package so the server can serve it on its own port.

Usage:
    uv run python scripts/bundle-web.py ../terraria-journey-tracker-web-client/build
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "src" / "terraria_tracker" / "web"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", type=Path, help="the client's build/ directory")
    args = parser.parse_args()

    source = args.build_dir.resolve()
    if not (source / "index.html").is_file():
        print(f"error: {source} has no index.html — run `npm run build` in the client first", file=sys.stderr)
        return 1

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(source, TARGET)

    files = sum(1 for _ in TARGET.rglob("*") if _.is_file())
    print(f"bundled {files} files into {TARGET}")
    print("the tracker will now serve the UI on its own port")
    return 0


if __name__ == "__main__":
    sys.exit(main())
