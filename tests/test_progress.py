from terraria_tracker.gamedata.models import GameData, Ingredient, Item, Recipe
from terraria_tracker.plr.player import PlayerSave
from terraria_tracker.progress import build_progress, find_craftable


def _item(item_id: int, name: str, research: int = 1) -> Item:
    return Item(
        id=item_id,
        name=name,
        internal_name=name.replace(" ", ""),
        research=research,
        image_url="",
        wiki_url="",
    )


def _data() -> GameData:
    items = {
        1: _item(1, "Wood", research=100),
        2: _item(2, "Ebonwood", research=100),
        3: _item(3, "Iron Bar", research=25),
        4: _item(4, "Chest", research=1),
        5: _item(5, "Zenith", research=1),
    }
    recipes = [
        Recipe(
            id=4,
            name="Chest",
            station_ids=(1,),
            ingredients=(
                Ingredient(name="Any Wood", ids=(1, 2), amount=8),
                Ingredient(name="Iron Bar", ids=(3,), amount=2),
            ),
        ),
        Recipe(
            id=5,
            name="Zenith",
            station_ids=(1,),
            ingredients=(Ingredient(name="Missing Item", ids=(), amount=1),),
        ),
    ]
    return GameData(meta={"gameVersion": "1.4.5.6"}, items=items, recipes=recipes, stations={})


class TestFindCraftable:
    def test_needs_every_ingredient_slot_filled(self):
        assert find_craftable(_data(), researched={1}) == []

    def test_one_member_of_a_group_is_enough(self):
        """ "Any Wood" is satisfied by Ebonwood alone."""
        assert find_craftable(_data(), researched={2, 3}) == [4]

    def test_already_researched_items_are_not_suggested(self):
        assert find_craftable(_data(), researched={1, 3, 4}) == []

    def test_recipe_with_an_unresolved_ingredient_is_never_craftable(self):
        """12 ingredient names have no item behind them; they must not fake a suggestion."""
        assert 5 not in find_craftable(_data(), researched={1, 2, 3})


class TestBuildProgress:
    def test_counts_researched_partial_and_untouched(self):
        data = _data()
        save = PlayerSave(
            name="Enzo",
            difficulty=3,
            file_version=279,
            research={"Wood": 100, "IronBar": 10},
            research_found=True,
        )

        progress = build_progress(save, data)

        assert progress.overview.items_total == 5
        assert progress.overview.items_researched == 1
        assert progress.overview.items_partial == 1
        assert progress.overview.items_untouched == 3
        assert progress.sacrificed == {1: 100, 3: 10}

    def test_sacrifice_totals_do_not_exceed_the_requirement(self):
        data = _data()
        save = PlayerSave(name="E", difficulty=3, file_version=279, research={"Wood": 999})

        progress = build_progress(save, data)

        assert progress.overview.sacrifices_done == 100

    def test_reports_items_missing_from_the_bundled_data(self):
        """This is the signal that the data snapshot predates the installed Terraria."""
        data = _data()
        save = PlayerSave(name="E", difficulty=3, file_version=279, research={"SomeNewItem": 3})

        progress = build_progress(save, data)

        assert progress.unknown_internal_names == ["SomeNewItem"]
        assert progress.sacrificed == {}

    def test_payload_is_json_shaped(self):
        data = _data()
        save = PlayerSave(name="E", difficulty=3, file_version=279, research={"Wood": 100})

        payload = build_progress(save, data).to_payload()

        assert payload["player"]["isJourney"] is True
        assert payload["sacrificed"] == {"1": 100}
        assert "percentItems" in payload["overview"]
