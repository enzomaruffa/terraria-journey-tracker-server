"""Where items come from.

This answers "how do I actually get this?", and it is also what makes the research-first
planner honest: an item with no drop source cannot be gathered, so the planner must reach it
through a recipe rather than offering to go and find it.

Sources here are not only enemies — crates, chests and bags all appear as drop sources.
"""

from __future__ import annotations

import re

from terraria_tracker.logging_setup import logger
from terraria_tracker.scraper.wiki import CargoClient, sort_value_float, strip_html

FIELDS = "_pageName,item,quantity,rate,expert,master"

# Rates arrive in three shapes: a plain "0.4%", a rendered fraction carrying a sort value
# ("1/36 (2.78%)"), and a base rate followed by a wikitext link to the difficulty-specific
# one ("1%[[Expert Mode|1.99%]]").
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_PERCENT_RE = re.compile(r"([\d.]+)\s*%")


def _clean_rate(raw: str | None) -> str:
    """Readable drop rate text."""

    def replace(match: re.Match[str]) -> str:
        target, label = match.group(1), match.group(2) or match.group(1)
        for mode in ("Expert", "Master"):
            if mode in target:
                return f" ({mode}: {label})"
        return label

    return _WIKILINK_RE.sub(replace, strip_html(raw)).strip()


def _rate_percent(raw: str | None, cleaned: str) -> float | None:
    """The base drop chance as a number, for sorting and filtering.

    Prefers the wiki's own sort value where present, and otherwise takes the first
    percentage in the text — which is the normal-mode rate, the Expert one following it.
    """
    value = sort_value_float(raw)
    if value is not None:
        return value

    match = _PERCENT_RE.search(cleaned)
    return float(match.group(1)) if match else None


def fetch_drops(client: CargoClient, items: dict[str, dict]) -> dict[str, list[dict]]:
    """Return ``{itemId: [{source, quantity, rate, ratePercent, expert, master}]}``.

    The table keys items by display name, so it is joined through the same name index the
    recipe scraper builds.
    """
    items_by_name: dict[str, int] = {}
    for raw in items.values():
        items_by_name.setdefault(raw["name"], raw["id"])

    drops: dict[str, list[dict]] = {}
    unresolved: set[str] = set()
    rows = 0

    for row in client.query("Drops", FIELDS, order_by="_pageName ASC"):
        rows += 1

        name = (row.get("item") or "").strip()
        item_id = items_by_name.get(name)
        if item_id is None:
            unresolved.add(name)
            continue

        source = (row.get("_pageName") or "").strip()
        if not source:
            continue

        rate = _clean_rate(row.get("rate"))
        entry = {
            "source": source,
            "quantity": strip_html(row.get("quantity")) or "1",
            "rate": rate,
            "ratePercent": _rate_percent(row.get("rate"), rate),
            "expert": bool(str(row.get("expert") or "").strip()),
            "master": bool(str(row.get("master") or "").strip()),
        }

        # The table carries a row per difficulty variant, so the same source can appear more
        # than once with identical numbers.
        bucket = drops.setdefault(str(item_id), [])
        if not any(e["source"] == source and e["rate"] == rate and e["quantity"] == entry["quantity"] for e in bucket):
            bucket.append(entry)

    logger.info("drops: %d sources across %d items (from %d rows)", sum(map(len, drops.values())), len(drops), rows)
    if unresolved:
        logger.warning(
            "%d dropped item name(s) matched no researchable item (first few: %s)",
            len(unresolved),
            ", ".join(sorted(unresolved)[:8]),
        )

    return drops
