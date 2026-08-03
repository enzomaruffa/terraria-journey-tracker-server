from __future__ import annotations

from typing import Any

from terraria_tracker.logging_setup import logger
from terraria_tracker.scraper.wiki import CargoClient, image_url, wiki_url

FIELDS = "itemid,name,internalname,imagefile,research,type,rare"

# Terraria ships a handful of items whose wiki internal name has never matched the one in
# save files. Without this the tracker reports them as "unknown item" forever.
INTERNAL_NAME_FIXUPS = {
    "EldMelter": "ElfMelter",
}


def _categories(raw_type: str | None) -> list[str]:
    if not raw_type:
        return []
    return sorted({part.strip().lower() for part in raw_type.split("^") if part.strip()})


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def fetch_items(client: CargoClient) -> dict[str, dict]:
    """Every researchable item, keyed by item id.

    Items with no research value (Hearts, Stars, and other pickups) cannot be researched
    at all, so they are excluded rather than counted against the player's total.
    """
    items: dict[str, dict] = {}
    skipped_no_research = 0
    duplicates = 0

    rows = client.query(
        "Items",
        FIELDS,
        where="itemid IS NOT NULL AND internalname IS NOT NULL",
        order_by="itemid ASC",
    )

    for row in rows:
        item_id = _as_int(row.get("itemid"), default=-1)
        if item_id < 0:
            continue

        research = _as_int(row.get("research"), default=0)
        if research <= 0:
            skipped_no_research += 1
            continue

        key = str(item_id)
        if key in items:
            duplicates += 1
            continue

        name = (row.get("name") or "").strip()
        internal = (row.get("internalname") or "").strip()
        internal = INTERNAL_NAME_FIXUPS.get(internal, internal)
        if not internal or internal == "None":
            continue

        items[key] = {
            "id": item_id,
            "name": name,
            "internalName": internal,
            "research": research,
            "imageUrl": image_url(row.get("imagefile") or ""),
            "wikiUrl": wiki_url(name),
            "categories": _categories(row.get("type")),
            "rarity": _as_int(row.get("rare")),
        }

    logger.info(
        "items: %d researchable (%d without a research value, %d duplicate rows)",
        len(items),
        skipped_no_research,
        duplicates,
    )
    return items
