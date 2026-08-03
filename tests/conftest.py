import pytest

from terraria_tracker.gamedata import load_game_data


@pytest.fixture(scope="session")
def game_data():
    return load_game_data()


@pytest.fixture(scope="session")
def sample_research(game_data) -> dict[str, int]:
    """A believable research table drawn from the real bundled item list."""
    picked: dict[str, int] = {}
    for item in sorted(game_data.items.values(), key=lambda i: i.id):
        if len(picked) >= 40:
            break
        # Mix fully researched items with partial ones.
        picked[item.internal_name] = item.research if len(picked) % 3 else max(1, item.research // 2)
    return picked
