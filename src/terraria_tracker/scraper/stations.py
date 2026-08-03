"""Crafting station identities.

Most stations are ordinary items, so their id is just the item id and the scraper resolves
them by name. The rest are environmental or combination stations ("Water", "Work Bench and
Ecto Mist") that have no item behind them, so they get stable negative ids from the table
below. Ids 0 to -20 match the previous data release; -21 and beyond are the stations
Terraria 1.4.5 added.
"""

from __future__ import annotations

BY_HAND = 0

#: name -> (id, image file on the wiki)
SPECIAL_STATIONS: dict[str, tuple[int, str]] = {
    "By Hand": (0, "Hand Of Creation.png"),
    "Demon Altar": (-1, "Demon Altar.png"),
    "Honey": (-2, "Honey.png"),
    "Lava": (-3, "Flame.png"),
    "Living Wood": (-4, "Living Wood (placed).png"),
    "Placed Bottle": (-5, "Bottle (crafting station).png"),
    "Shimmer": (-6, "Shimmer.gif"),
    "Water": (-7, "Water.png"),
    "Table and Chair": (-8, "Wooden Table (placed).png"),
    "Work Bench and Chair": (-9, "Work Bench.png"),
    "Bone Welder and Ecto Mist": (-10, "Bone Welder (placed).gif"),
    "Heavy Work Bench and Ecto Mist": (-11, "Heavy Work Bench (placed).png"),
    "Iron Anvil and Ecto Mist": (-12, "Iron Anvil.png"),
    "Loom and Ecto Mist": (-13, "Loom (placed).png"),
    "Tinkerer's Workshop and Ecto Mist": (-14, "Tinkerer's Workshop (placed).png"),
    "Work Bench and Ecto Mist": (-15, "Work Bench.png"),
    "Crystal Ball and Honey": (-16, "Crystal Ball (placed).png"),
    "Crystal Ball and Lava": (-17, "Crystal Ball (placed).png"),
    "Crystal Ball and Water": (-18, "Crystal Ball (placed).png"),
    "Sky Mill and Snow Biome": (-19, "Sky Mill (placed).gif"),
    "Sky Mill and Water": (-20, "Sky Mill (placed).gif"),
    "Sky Mill and Lava": (-21, "Sky Mill (placed).gif"),
    "Work Bench and Water": (-22, "Work Bench.png"),
    "Heavy Assembler and Ecto Mist": (-23, "Heavy Assembler (placed).png"),
    "Placed Bottle only": (-24, "Bottle (crafting station).png"),
}

#: Recipe rows still name stations Terraria has since renamed. The item id is unchanged,
#: so mapping the old display name onto the new one keeps those recipes attached.
STATION_ALIASES = {
    "Heavy Work Bench": "Heavy Assembler",
}
