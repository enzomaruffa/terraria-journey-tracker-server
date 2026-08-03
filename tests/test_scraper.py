from terraria_tracker.scraper.drops import _clean_rate, _rate_percent
from terraria_tracker.scraper.recipes import _parse_args, _parse_yield, _resolve_ingredient, _station_ids
from terraria_tracker.scraper.stations import SPECIAL_STATIONS
from terraria_tracker.scraper.wiki import image_url, sort_value, text_lines

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


class TestYield:
    def test_reads_the_craft_yield(self):
        """Torch is 1 Gel + 1 Wood for three Torches; treating it as one overstates gathering."""
        assert _parse_yield("3") == 3

    def test_defaults_to_one_when_absent(self):
        assert _parse_yield(None) == 1
        assert _parse_yield("") == 1

    def test_never_returns_zero(self):
        # A zero yield would make "how many crafts" divide by zero downstream.
        assert _parse_yield("0") == 1


class TestTooltips:
    def test_splits_on_line_breaks(self):
        raw = '<span class="gameText">Increases maximum mana by 40<br/>6% increased magic crit</span>'
        assert text_lines(raw) == ["Increases maximum mana by 40", "6% increased magic crit"]

    def test_handles_escaped_markup(self):
        assert text_lines("&lt;span&gt;Provides light&lt;/span&gt;") == ["Provides light"]

    def test_empty_tooltip_is_no_lines(self):
        assert text_lines(None) == []
        assert text_lines("") == []


class TestCoinValues:
    def test_reads_the_sort_value_in_copper(self):
        raw = '<span class="coin" title="90 Silver Coins" data-sort-value="9000">90 SC</span>'
        assert sort_value(raw) == 9000

    def test_missing_value_is_none(self):
        assert sort_value("") is None


class TestDropRates:
    def test_plain_percentage(self):
        assert _rate_percent("0.4%", _clean_rate("0.4%")) == 0.4

    def test_rendered_fraction_uses_the_sort_value(self):
        raw = '<span class="chance" data-sort-value="2.78">1/36 (2.78%)</span>'
        assert _rate_percent(raw, _clean_rate(raw)) == 2.78

    def test_sort_value_keeps_its_precision(self):
        """Read as an int, a 2.78% drop chance would round to 2."""
        raw = '<span class="chance" data-sort-value="2.78">1/36</span>'
        assert isinstance(_rate_percent(raw, _clean_rate(raw)), float)

    def test_difficulty_link_becomes_readable(self):
        assert _clean_rate("1%[[Expert Mode|1.99%]]") == "1% (Expert: 1.99%)"

    def test_difficulty_link_reports_the_base_rate(self):
        raw = "1%[[Expert Mode|1.99%]]"
        assert _rate_percent(raw, _clean_rate(raw)) == 1.0

    def test_plain_wikilink_keeps_its_label(self):
        assert _clean_rate("[[Gel]]") == "Gel"

    def test_unparseable_rate_is_none_not_zero(self):
        assert _rate_percent("varies", _clean_rate("varies")) is None


class TestImageUrl:
    def test_uses_the_flat_upload_path(self):
        assert image_url("Iron Pickaxe.png") == "https://terraria.wiki.gg/images/Iron_Pickaxe.png"

    def test_escapes_characters_that_break_urls(self):
        assert image_url("Tinkerer's Workshop (placed).png").endswith("Tinkerer%27s_Workshop_%28placed%29.png")

    def test_empty_file_yields_empty_url(self):
        assert image_url("") == ""
