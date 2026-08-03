"""``terraria-tracker-refresh`` — rebuild data/*.json from the official wiki."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from terraria_tracker.logging_setup import setup_logging
from terraria_tracker.scraper.alternatives import fetch_ingredient_groups
from terraria_tracker.scraper.items import fetch_items
from terraria_tracker.scraper.recipes import fetch_recipes
from terraria_tracker.scraper.wiki import WIKI, CargoClient

DEFAULT_OUT = Path(__file__).resolve().parents[3] / "data"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=False)
        handle.write("\n")
    size_kb = path.stat().st_size / 1024
    print(f"  wrote {path.name:<16} {size_kb:>8.0f} KB")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terraria-tracker-refresh",
        description="Rebuild the bundled item, recipe and crafting station data from terraria.wiki.gg.",
    )
    parser.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT, help=f"output directory (default {DEFAULT_OUT})")
    parser.add_argument("--game-version", default=None, help="Terraria version to stamp into the data, e.g. 1.4.5.6")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = setup_logging(args.verbose)

    meta = {
        "source": WIKI,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "gameVersion": args.game_version or "unknown",
    }

    logger.info("fetching from %s (this takes a couple of minutes)", WIKI)
    try:
        with CargoClient() as client:
            items = fetch_items(client)
            groups = fetch_ingredient_groups(client)
            recipes, stations = fetch_recipes(client, items, groups)
    except Exception as exc:
        logger.error("refresh failed: %s", exc)
        return 1

    if not items:
        logger.error("no items returned — refusing to overwrite the existing data")
        return 1

    meta["itemCount"] = len(items)
    meta["recipeCount"] = len(recipes)
    meta["stationCount"] = len(stations)

    _write(args.out / "items.json", {"meta": meta, "items": items})
    _write(args.out / "recipes.json", {"meta": meta, "recipes": recipes})
    _write(
        args.out / "stations.json",
        {"meta": meta, "stations": {str(k): v for k, v in sorted(stations.items())}},
    )
    _write(args.out / "ingredient-groups.json", {"meta": meta, "groups": groups})

    logger.info(
        "done: %d items, %d recipes, %d stations, %d ingredient groups",
        len(items),
        len(recipes),
        len(stations),
        len(groups),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
