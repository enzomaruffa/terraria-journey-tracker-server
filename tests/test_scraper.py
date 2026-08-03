from terraria_tracker.scraper.recipes import _parse_args, _resolve_ingredient, _station_ids
from terraria_tracker.scraper.stations import SPECIAL_STATIONS
from terraria_tracker.scraper.wiki import image_url

ITEMS_BY_NAME = {
    "Iron Bar": 22,
    "Lead Bar": 704,
    "Blue Jellyfish": 2019,
    "Adamantite Bar": 391,
    "Titanium Bar": 1198,
    "Work Bench": 36,
}
GROUPS = {"Any Iron Bar": [22, 704]}


class TestParseArgs:
    def test_splits_entries_and_amounts(self):
        assert _parse_args("Actuator¦50^Any Iron Bar¦10^Wire¦10") == [
            ("Actuator", 50),
            ("Any Iron Bar", 10),
            ("Wire", 10),
        ]

    def test_strips_wiki_display_directives(self):
        """ "Iron Bar#i:old" selects an old-gen sprite; it is not part of the item name."""
        assert _parse_args("Iron Bar#i:old¦3") == [("Iron Bar", 3)]

    def test_defaults_a_missing_amount_to_one(self):
        assert _parse_args("Wire") == [("Wire", 1)]

    def test_handles_empty_input(self):
        assert _parse_args(None) == []
        assert _parse_args("") == []


class TestResolveIngredient:
    def test_plain_item(self):
        assert _resolve_ingredient("Iron Bar", ITEMS_BY_NAME, GROUPS) == [22]

    def test_group_expands_to_every_member(self):
        assert _resolve_ingredient("Any Iron Bar", ITEMS_BY_NAME, GROUPS) == [22, 704]

    def test_inline_either_or_borrows_the_shared_noun(self):
        """Only the last alternative is spelled out; "Adamantite" means "Adamantite Bar"."""
        assert _resolve_ingredient("Adamantite/Titanium Bar", ITEMS_BY_NAME, GROUPS) == [391, 1198]

    def test_either_or_resolves_all_or_nothing(self):
        items = {"Titanium Bar": 1198}
        assert _resolve_ingredient("Adamantite/Titanium Bar", items, GROUPS) == []

    def test_disambiguation_suffix_is_stripped(self):
        assert _resolve_ingredient("Blue Jellyfish (bait)", ITEMS_BY_NAME, GROUPS) == [2019]

    def test_unknown_name_resolves_to_nothing(self):
        assert _resolve_ingredient("Soul of Blight", ITEMS_BY_NAME, GROUPS) == []


class TestStations:
    def test_environmental_station_uses_its_curated_id(self):
        assert _station_ids("Shimmer", ITEMS_BY_NAME, set()) == [-6]

    def test_furniture_station_uses_its_item_id(self):
        assert _station_ids("Work Bench", ITEMS_BY_NAME, set()) == [36]

    def test_renamed_station_follows_its_alias(self):
        """1.4.5 renamed Heavy Work Bench to Heavy Assembler; old recipe rows still say the former."""
        items = {"Heavy Assembler": 2172}
        assert _station_ids("Heavy Work Bench", items, set()) == [2172]

    def test_missing_station_is_reported_not_invented(self):
        unresolved: set[str] = set()
        assert _station_ids("Nonexistent Bench", ITEMS_BY_NAME, unresolved) == []
        assert unresolved == {"Nonexistent Bench"}

    def test_no_station_means_by_hand(self):
        assert _station_ids(None, ITEMS_BY_NAME, set()) == [SPECIAL_STATIONS["By Hand"][0]]


class TestImageUrl:
    def test_uses_the_flat_upload_path(self):
        assert image_url("Iron Pickaxe.png") == "https://terraria.wiki.gg/images/Iron_Pickaxe.png"

    def test_escapes_characters_that_break_urls(self):
        assert image_url("Tinkerer's Workshop (placed).png").endswith("Tinkerer%27s_Workshop_%28placed%29.png")

    def test_empty_file_yields_empty_url(self):
        assert image_url("") == ""
