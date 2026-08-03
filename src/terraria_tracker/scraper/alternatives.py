"""Resolve "Any Wood"-style ingredient groups to the items that satisfy them.

Recipes refer to these groups by name, so without them roughly a fifth of all recipes have
an ingredient that maps to no item at all and the "what can I craft next" list under-reports.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from terraria_tracker.logging_setup import logger
from terraria_tracker.scraper.wiki import CargoClient

PAGE = "Alternative_crafting_ingredients"
_ITEM_ID_RE = re.compile(r"Item ID\s*:\s*(\d+)")


def fetch_ingredient_groups(client: CargoClient) -> dict[str, list[int]]:
    """Return ``{"Any Wood": [9, 619, ...], ...}``.

    Each group heading is followed by an ``itemlist`` whose entries carry their internal
    item id in a ``span.id``. The previous scraper looked for the literal text
    "Internal Item ID:", which the wiki now splits across a link, so it silently matched
    nothing.
    """
    soup = BeautifulSoup(client.get_html(PAGE), "lxml")
    groups: dict[str, list[int]] = {}

    for headline in soup.select("span.mw-headline"):
        name = headline.get_text(strip=True)
        if not name.startswith("Any"):
            continue

        heading = headline.parent
        if not isinstance(heading, Tag):
            continue

        itemlist = heading.find_next("div", class_="itemlist")
        if not isinstance(itemlist, Tag):
            continue

        ids: list[int] = []
        for span in itemlist.select("span.id"):
            match = _ITEM_ID_RE.search(span.get_text(" ", strip=True))
            if match:
                item_id = int(match.group(1))
                if item_id not in ids:
                    ids.append(item_id)

        if ids:
            groups[name] = ids

    logger.info("ingredient groups: %d resolved (e.g. %s)", len(groups), ", ".join(list(groups)[:3]))
    if not groups:
        logger.warning("no ingredient groups found — the wiki markup for %s may have changed again", PAGE)
    return groups
