#!/usr/bin/env python3
"""Copy a built web client into the package so the server can serve it on its own port.

The result is committed. That is what lets someone with an empty machine run

    uvx --from <this repo's zip> terraria-journey-tracker

and get the whole application rather than a bare JSON API.

Usage:
    uv run python scripts/bundle-web.py ../terraria-journey-tracker-web-client/build
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "src" / "terraria_tracker" / "web"

# The client ships a copy of the item data for its no-server mode. Behind the tracker it
# reads /api/items instead, so bundling it here would add ~3 MB to every install for
# nothing.
SKIP = shutil.ignore_patterns("data")


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
    shutil.copytree(source, TARGET, ignore=SKIP)

    files = [p for p in TARGET.rglob("*") if p.is_file()]
    size_kb = sum(p.stat().st_size for p in files) / 1024
    print(f"bundled {len(files)} files ({size_kb:.0f} KB) into {TARGET}")
    print("commit this so a fresh install serves the UI without Node")
    return 0


if __name__ == "__main__":
    sys.exit(main())
