from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    name: str
    internal_name: str
    research: int
    image_url: str
    wiki_url: str
    categories: tuple[str, ...] = ()
    rarity: int = 0
    tooltip: tuple[str, ...] = ()
    #: Coin values, in copper.
    sell: int | None = None
    buy: int | None = None
    damage: int | None = None
    defense: int | None = None
    max_stack: int | None = None
    placeable: bool = False
    hardmode: bool = False
    consumable: bool = False


@dataclass(frozen=True, slots=True)
class Drop:
    """One way an item can be obtained. Sources include crates and chests, not just enemies."""

    source: str
    quantity: str
    rate: str
    rate_percent: float | None
    expert: bool = False
    master: bool = False


@dataclass(frozen=True, slots=True)
class Ingredient:
    """One slot in a recipe.

    ``ids`` holds every item that can fill the slot, so "any Wood" and "Iron Bar" are the
    same shape. The old data mixed ints, strings and lists in one field and every consumer
    had to re-discover that.
    """

    name: str
    ids: tuple[int, ...]
    amount: int


@dataclass(frozen=True, slots=True)
class Recipe:
    id: int
    name: str
    station_ids: tuple[int, ...]
    ingredients: tuple[Ingredient, ...]
    #: How many items one craft produces — Torch is 1 Gel + 1 Wood for three Torches.
    yields: int = 1


@dataclass(frozen=True, slots=True)
class Station:
    id: int
    name: str
    image_urls: tuple[str, ...]
    craftable_ids: tuple[int, ...]


@dataclass(slots=True)
class GameData:
    meta: dict
    items: dict[int, Item]
    recipes: list[Recipe]
    stations: dict[int, Station]
    drops: dict[int, tuple[Drop, ...]] = field(default_factory=dict)

    _by_internal_name: dict[str, Item] = field(default_factory=dict, repr=False)
    _recipes_by_result: dict[int, list[Recipe]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # The old code did a full linear scan of every item for each of the ~5000 research
        # entries in a save, on every file change.
        self._by_internal_name = {item.internal_name: item for item in self.items.values()}
        for recipe in self.recipes:
            self._recipes_by_result.setdefault(recipe.id, []).append(recipe)

    @property
    def internal_names(self) -> set[str]:
        return set(self._by_internal_name)

    def item(self, item_id: int) -> Item | None:
        return self.items.get(item_id)

    def by_internal_name(self, internal_name: str) -> Item | None:
        return self._by_internal_name.get(internal_name)

    def recipes_for(self, item_id: int) -> list[Recipe]:
        return self._recipes_by_result.get(item_id, [])

    def drops_for(self, item_id: int) -> tuple[Drop, ...]:
        return self.drops.get(item_id, ())

    def is_gatherable(self, item_id: int) -> bool:
        """Whether the item can be obtained in-world rather than only crafted.

        The planner needs this: offering to "go find" a craft-only item is nonsense.
        """
        return item_id in self.drops

    @property
    def total_research_required(self) -> int:
        return sum(item.research for item in self.items.values())

    @property
    def game_version(self) -> str:
        return str(self.meta.get("gameVersion", "unknown"))
