from __future__ import annotations

import re

from terraria_tracker.logging_setup import logger
from terraria_tracker.scraper.stations import SPECIAL_STATIONS, STATION_ALIASES
from terraria_tracker.scraper.wiki import CargoClient, image_url

FIELDS = "result,resultid,station,args"

# The wiki packs a recipe's ingredients into one string: entries separated by "^", and
# name/amount separated by a broken bar. The old parser split on the character class
# [Â|^|¦], which also ate literal pipes and the mojibake "Â" of a mis-decoded ¦.
ENTRY_SEP = "^"
AMOUNT_SEP = "¦"

_PARENTHETICAL_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_args(args: str | None) -> list[tuple[str, int]]:
    if not args:
        return []

    parsed: list[tuple[str, int]] = []
    for entry in args.split(ENTRY_SEP):
        entry = entry.strip()
        if not entry:
            continue
        name, _, amount = entry.partition(AMOUNT_SEP)
        # Ingredient names carry wiki display directives such as "Iron Bar#i:old", which
        # select an alternate sprite and are not part of the item name.
        name = name.split("#", 1)[0].strip()
        if not name:
            continue
        try:
            quantity = int(amount.strip() or 1)
        except ValueError:
            quantity = 1
        parsed.append((name, quantity))
    return parsed


def _resolve_ingredient(
    name: str,
    items_by_name: dict[str, int],
    groups: dict[str, list[int]],
) -> list[int]:
    """Every item id that can fill this ingredient slot."""
    if name in groups:
        return list(groups[name])
    if name in items_by_name:
        return [items_by_name[name]]

    if "/" in name:
        ids = _resolve_either_or(name, items_by_name)
        if ids:
            return ids

    # Others carry the wiki's disambiguation suffix, e.g. "Blue Jellyfish (bait)".
    base = _PARENTHETICAL_RE.sub("", name).strip()
    if base != name and base in items_by_name:
        return [items_by_name[base]]

    return []


def _resolve_either_or(name: str, items_by_name: dict[str, int]) -> list[int]:
    """Expand an inline either/or slot such as "Adamantite/Titanium Bar".

    Only the last alternative is written out in full, so the earlier ones have to borrow
    its trailing noun. Resolving them independently yields "Adamantite" (no such item) and
    "Titanium Bar", which would wrongly claim the recipe accepts titanium only.
    """
    parts = [part.strip() for part in name.split("/") if part.strip()]
    if len(parts) < 2:
        return []

    suffix = parts[-1].rsplit(" ", 1)[-1] if " " in parts[-1] else ""

    ids: list[int] = []
    for part in parts:
        if part in items_by_name:
            candidate = items_by_name[part]
        elif suffix and f"{part} {suffix}" in items_by_name:
            candidate = items_by_name[f"{part} {suffix}"]
        else:
            # Half an answer is worse than none: it would understate what the recipe takes.
            return []
        if candidate not in ids:
            ids.append(candidate)

    return ids


def _station_ids(
    station: str | None,
    items_by_name: dict[str, int],
    unresolved: set[str],
) -> list[int]:
    """Map a station name to ids, inventing nothing.

    Stations that are ordinary furniture resolve to their item id; the environmental and
    combination ones come from the curated table. Anything else is reported rather than
    silently dropped, which is how the previous data ended up with string station ids
    sitting next to integers.
    """
    if not station:
        return [SPECIAL_STATIONS["By Hand"][0]]

    name = station.strip()
    name = STATION_ALIASES.get(name, name)
    if name in SPECIAL_STATIONS:
        return [SPECIAL_STATIONS[name][0]]
    if name in items_by_name:
        return [items_by_name[name]]

    unresolved.add(name)
    return []


def fetch_recipes(
    client: CargoClient,
    items: dict[str, dict],
    groups: dict[str, list[int]],
) -> tuple[list[dict], dict[int, dict]]:
    """Return ``(recipes, stations)`` built from the wiki's Recipes table."""
    items_by_name: dict[str, int] = {}
    for raw in items.values():
        # Keep the lowest id when two pages share a name; ids are stable, page titles are not.
        items_by_name.setdefault(raw["name"], raw["id"])

    recipes: list[dict] = []
    unresolved_stations: set[str] = set()
    unresolved_ingredients: set[str] = set()
    station_usage: dict[int, list[int]] = {}

    for row in client.query("Recipes", FIELDS, order_by="result ASC"):
        try:
            result_id = int(str(row.get("resultid")).strip())
        except (TypeError, ValueError):
            continue

        ingredients = []
        for name, amount in _parse_args(row.get("args")):
            ids = _resolve_ingredient(name, items_by_name, groups)
            if not ids:
                unresolved_ingredients.add(name)
            ingredients.append({"name": name, "ids": ids, "amount": amount})

        station_ids = _station_ids(row.get("station"), items_by_name, unresolved_stations)

        recipes.append(
            {
                "id": result_id,
                "name": (row.get("result") or "").strip(),
                "stationIds": station_ids,
                "ingredients": ingredients,
            }
        )

        for station_id in station_ids:
            crafted = station_usage.setdefault(station_id, [])
            if result_id not in crafted:
                crafted.append(result_id)

    stations = _build_stations(station_usage, items)

    logger.info("recipes: %d across %d stations", len(recipes), len(stations))
    if unresolved_stations:
        logger.warning(
            "%d crafting station(s) could not be resolved — add them to SPECIAL_STATIONS: %s",
            len(unresolved_stations),
            ", ".join(sorted(unresolved_stations)),
        )
    if unresolved_ingredients:
        logger.warning(
            "%d ingredient name(s) matched no item or group (first few: %s)",
            len(unresolved_ingredients),
            ", ".join(sorted(unresolved_ingredients)[:8]),
        )

    return recipes, stations


def _build_stations(station_usage: dict[int, list[int]], items: dict[str, dict]) -> dict[int, dict]:
    special_by_id = {station_id: (name, image) for name, (station_id, image) in SPECIAL_STATIONS.items()}
    stations: dict[int, dict] = {}

    for station_id, craftables in station_usage.items():
        if station_id in special_by_id:
            name, image_file = special_by_id[station_id]
            image_urls = [image_url(image_file)]
        else:
            item = items.get(str(station_id))
            if item is None:
                continue
            name = item["name"]
            image_urls = [item["imageUrl"]]

        stations[station_id] = {
            "id": station_id,
            "name": name,
            "imageUrls": image_urls,
            "craftableIds": sorted(craftables),
        }

    return stations
