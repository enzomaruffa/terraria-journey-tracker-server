"""Turn a parsed character file into the numbers the UI shows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from terraria_tracker.gamedata import GameData
from terraria_tracker.logging_setup import logger
from terraria_tracker.plr import PlayerSave


@dataclass(frozen=True, slots=True)
class Overview:
    items_total: int
    items_researched: int
    items_partial: int
    items_untouched: int
    percent_items: float
    sacrifices_done: int
    sacrifices_total: int
    percent_sacrifices: float
    craftable_now: int


@dataclass(slots=True)
class Progress:
    player_name: str
    difficulty: str
    is_journey: bool
    file_version: int
    overview: Overview
    #: item id -> how many have been sacrificed. Only non-zero entries, so a fresh
    #: character sends a handful of bytes instead of every item in the game.
    sacrificed: dict[int, int] = field(default_factory=dict)
    #: Not yet researched, but every ingredient of some recipe already is.
    craftable: list[int] = field(default_factory=list)
    unknown_internal_names: list[str] = field(default_factory=list)
    research_found: bool = True
    research_verified: bool = False
    updated_at: str = ""

    def to_payload(self) -> dict:
        return {
            "player": {
                "name": self.player_name,
                "difficulty": self.difficulty,
                "isJourney": self.is_journey,
                "fileVersion": self.file_version,
            },
            "overview": {
                "itemsTotal": self.overview.items_total,
                "itemsResearched": self.overview.items_researched,
                "itemsPartial": self.overview.items_partial,
                "itemsUntouched": self.overview.items_untouched,
                "percentItems": self.overview.percent_items,
                "sacrificesDone": self.overview.sacrifices_done,
                "sacrificesTotal": self.overview.sacrifices_total,
                "percentSacrifices": self.overview.percent_sacrifices,
                "craftableNow": self.overview.craftable_now,
            },
            "sacrificed": {str(k): v for k, v in self.sacrificed.items()},
            "craftable": self.craftable,
            "researchFound": self.research_found,
            "researchVerified": self.research_verified,
            "unknownInternalNames": self.unknown_internal_names,
            "updatedAt": self.updated_at,
        }


def _percent(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100 * part / whole, 2)


def find_craftable(data: GameData, researched: set[int]) -> list[int]:
    """Items you could research next using only ingredients you already unlocked.

    In Journey mode a researched item can be duplicated for free, so a recipe whose every
    ingredient is researched is effectively free to craft — that is the whole point of the
    "what should I do next" list.
    """
    craftable: set[int] = set()

    for recipe in data.recipes:
        if recipe.id in researched or recipe.id in craftable:
            continue
        if not recipe.ingredients:
            continue
        if all(ing.ids and any(i in researched for i in ing.ids) for ing in recipe.ingredients):
            craftable.add(recipe.id)

    return sorted(craftable)


def build_progress(save: PlayerSave, data: GameData) -> Progress:
    sacrificed: dict[int, int] = {}
    unknown: list[str] = []

    for internal_name, count in save.research.items():
        item = data.by_internal_name(internal_name)
        if item is None:
            unknown.append(internal_name)
            continue
        if count > 0:
            sacrificed[item.id] = count

    if unknown:
        logger.warning(
            "%d researched item(s) are not in the bundled data — run `uv run terraria-tracker-refresh` "
            "to pick up a newer Terraria version (first few: %s)",
            len(unknown),
            ", ".join(sorted(unknown)[:5]),
        )

    researched: set[int] = set()
    partial = 0
    done_units = 0

    for item_id, count in sacrificed.items():
        item = data.item(item_id)
        if item is None:
            continue
        done_units += min(count, item.research)
        if count >= item.research:
            researched.add(item_id)
        else:
            partial += 1

    craftable = find_craftable(data, researched)
    total_items = len(data.items)
    total_units = data.total_research_required

    overview = Overview(
        items_total=total_items,
        items_researched=len(researched),
        items_partial=partial,
        items_untouched=total_items - len(researched) - partial,
        percent_items=_percent(len(researched), total_items),
        sacrifices_done=done_units,
        sacrifices_total=total_units,
        percent_sacrifices=_percent(done_units, total_units),
        craftable_now=len(craftable),
    )

    return Progress(
        player_name=save.name,
        difficulty=save.difficulty_name,
        is_journey=save.is_journey,
        file_version=save.file_version,
        overview=overview,
        sacrificed=sacrificed,
        craftable=craftable,
        unknown_internal_names=sorted(unknown)[:50],
        research_found=save.research_found,
        research_verified=save.research_verified,
        updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


__all__ = ["Overview", "Progress", "build_progress", "find_craftable"]
