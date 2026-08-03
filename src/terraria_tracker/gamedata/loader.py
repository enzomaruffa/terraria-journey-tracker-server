from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from terraria_tracker.gamedata.models import GameData, Ingredient, Item, Recipe, Station


class GameDataError(RuntimeError):
    pass


def data_dir() -> Path:
    """Locate the bundled snapshots, whether running from a checkout or an installed wheel."""
    packaged = Path(__file__).parent / "snapshots"
    if (packaged / "items.json").is_file():
        return packaged

    repo_data = Path(__file__).resolve().parents[3] / "data"
    if (repo_data / "items.json").is_file():
        return repo_data

    raise GameDataError("could not find the bundled game data. Run `uv run terraria-tracker-refresh` to build it.")


def _load(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise GameDataError(f"missing {path.name}; run `uv run terraria-tracker-refresh`") from exc
    except json.JSONDecodeError as exc:
        raise GameDataError(f"{path.name} is corrupt: {exc}") from exc


def _parse_items(payload: dict) -> dict[int, Item]:
    return {
        int(item_id): Item(
            id=int(raw["id"]),
            name=raw["name"],
            internal_name=raw["internalName"],
            research=int(raw["research"]),
            image_url=raw.get("imageUrl", ""),
            wiki_url=raw.get("wikiUrl", ""),
            categories=tuple(raw.get("categories", ())),
            rarity=int(raw.get("rarity", 0) or 0),
        )
        for item_id, raw in payload["items"].items()
    }


def _parse_recipes(payload: dict) -> list[Recipe]:
    return [
        Recipe(
            id=int(raw["id"]),
            name=raw["name"],
            station_ids=tuple(int(s) for s in raw["stationIds"]),
            ingredients=tuple(
                Ingredient(
                    name=ing["name"],
                    ids=tuple(int(i) for i in ing["ids"]),
                    amount=int(ing["amount"]),
                )
                for ing in raw["ingredients"]
            ),
        )
        for raw in payload["recipes"]
    ]


def _parse_stations(payload: dict) -> dict[int, Station]:
    return {
        int(station_id): Station(
            id=int(raw["id"]),
            name=raw["name"],
            image_urls=tuple(raw.get("imageUrls", ())),
            craftable_ids=tuple(int(i) for i in raw.get("craftableIds", ())),
        )
        for station_id, raw in payload["stations"].items()
    }


@lru_cache(maxsize=1)
def load_game_data() -> GameData:
    directory = data_dir()
    items_payload = _load(directory / "items.json")
    recipes_payload = _load(directory / "recipes.json")
    stations_payload = _load(directory / "stations.json")

    return GameData(
        meta=items_payload.get("meta", {}),
        items=_parse_items(items_payload),
        recipes=_parse_recipes(recipes_payload),
        stations=_parse_stations(stations_payload),
    )
