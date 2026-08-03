import pytest
from fastapi.testclient import TestClient

from plr_fixture import build_plr
from terraria_tracker.api import create_app
from terraria_tracker.config import Settings


@pytest.fixture
def player_file(tmp_path, sample_research):
    path = tmp_path / "Enzo.plr"
    path.write_bytes(build_plr(name="Enzo", research=sample_research))
    return path


@pytest.fixture
def client(player_file):
    settings = Settings(player_file=player_file, open_browser=False)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_status_reports_the_bundled_data(client):
    body = client.get("/api/status").json()

    assert body["itemCount"] > 6000
    assert body["gameVersion"] == "1.4.5.6"
    assert body["playerFileName"] == "Enzo.plr"


def test_progress_reflects_the_character_file(client, sample_research):
    body = client.get("/api/progress").json()

    assert body["player"]["name"] == "Enzo"
    assert body["player"]["isJourney"] is True
    assert len(body["sacrificed"]) == len(sample_research)
    assert body["researchVerified"] is True


def test_catalogue_endpoints(client):
    assert len(client.get("/api/items").json()["items"]) > 6000
    assert len(client.get("/api/recipes").json()["recipes"]) > 4000
    assert len(client.get("/api/stations").json()["stations"]) > 50


def test_unknown_api_route_is_a_404(client):
    assert client.get("/api/nope").status_code == 404


def test_selecting_a_missing_file_is_rejected(client, tmp_path):
    response = client.post("/api/players/select", json={"path": str(tmp_path / "ghost.plr")})
    assert response.status_code == 404


def test_selecting_a_non_plr_is_rejected(client, tmp_path):
    other = tmp_path / "world.wld"
    other.write_bytes(b"nope")

    response = client.post("/api/players/select", json={"path": str(other)})

    assert response.status_code == 400


def test_websocket_pushes_the_current_state(client):
    with client.websocket_connect("/api/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "status"

        second = ws.receive_json()
        assert second["type"] == "progress"
        assert second["data"]["player"]["name"] == "Enzo"


def test_websocket_broadcasts_when_the_file_changes(client, player_file, sample_research):
    """A save in-game must reach the browser without a refresh."""
    with client.websocket_connect("/api/ws") as ws:
        ws.receive_json()  # status
        ws.receive_json()  # initial progress

        trimmed = dict(list(sample_research.items())[:20])
        player_file.write_bytes(build_plr(name="Enzo", research=trimmed))
        client.portal.call(client.app.state.tracker.refresh_and_broadcast)

        message = ws.receive_json()
        assert message["type"] == "progress"
        assert len(message["data"]["sacrificed"]) == len(trimmed)


class TestCaching:
    """A stale cache looks exactly like an update that never happened.

    The bundled client is replaced wholesale on every release, so index.html must always be
    revalidated while the content-hashed assets beside it can be kept forever.
    """

    def test_api_responses_are_never_stored(self, client):
        assert client.get("/api/status").headers["cache-control"] == "no-store"
        assert client.get("/api/items").headers["cache-control"] == "no-store"

    def test_progress_is_never_stored(self, client):
        assert client.get("/api/progress").headers["cache-control"] == "no-store"
