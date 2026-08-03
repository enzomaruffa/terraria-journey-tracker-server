from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from terraria_tracker.gamedata import GameData
from terraria_tracker.locate import discover_players
from terraria_tracker.logging_setup import logger
from terraria_tracker.state import TrackerState

router = APIRouter(prefix="/api")


def _state(request: Request) -> TrackerState:
    return request.app.state.tracker


def _items_payload(data: GameData) -> dict:
    return {
        "meta": data.meta,
        "items": {
            str(item.id): {
                "id": item.id,
                "name": item.name,
                "internalName": item.internal_name,
                "research": item.research,
                "imageUrl": item.image_url,
                "wikiUrl": item.wiki_url,
                "categories": list(item.categories),
                "rarity": item.rarity,
            }
            for item in data.items.values()
        },
    }


def _recipes_payload(data: GameData) -> dict:
    return {
        "meta": data.meta,
        "recipes": [
            {
                "id": recipe.id,
                "name": recipe.name,
                "stationIds": list(recipe.station_ids),
                "ingredients": [
                    {"name": ing.name, "ids": list(ing.ids), "amount": ing.amount} for ing in recipe.ingredients
                ],
            }
            for recipe in data.recipes
        ],
    }


def _stations_payload(data: GameData) -> dict:
    return {
        "meta": data.meta,
        "stations": {
            str(station.id): {
                "id": station.id,
                "name": station.name,
                "imageUrls": list(station.image_urls),
                "craftableIds": list(station.craftable_ids),
            }
            for station in data.stations.values()
        },
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request) -> dict:
    return _state(request).status_payload()


@router.get("/items")
async def items(request: Request) -> dict:
    return _items_payload(_state(request).data)


@router.get("/recipes")
async def recipes(request: Request) -> dict:
    return _recipes_payload(_state(request).data)


@router.get("/stations")
async def stations(request: Request) -> dict:
    return _stations_payload(_state(request).data)


@router.get("/progress")
async def progress(request: Request) -> dict:
    state = _state(request)
    if state.progress is None:
        await state.refresh_and_broadcast()
    if state.progress is None:
        raise HTTPException(status_code=503, detail=state.error or "no character file loaded yet")
    return state.progress.to_payload()


@router.get("/players")
async def players(request: Request) -> dict:
    state = _state(request)
    found = discover_players()
    return {
        "active": str(state.player_file) if state.player_file else None,
        "players": [{"name": p.name, "path": str(p.path), "modified": p.modified} for p in found],
    }


class SelectPlayer(BaseModel):
    path: str


@router.post("/players/select")
async def select_player(request: Request, body: SelectPlayer) -> dict:
    state = _state(request)
    path = Path(body.path).expanduser()

    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no such file: {path}")
    if path.suffix.lower() != ".plr":
        raise HTTPException(status_code=400, detail="expected a .plr character file")

    state.set_player_file(path.resolve())
    request.app.state.restart_watcher()
    await state.refresh_and_broadcast()

    if state.progress is None:
        raise HTTPException(status_code=422, detail=state.error or "could not read that character file")
    return state.progress.to_payload()


@router.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    state: TrackerState = ws.app.state.tracker
    await ws.accept()

    queue = state.subscribe()
    try:
        await ws.send_json({"type": "status", "data": state.status_payload()})
        if state.progress is not None:
            await ws.send_json({"type": "progress", "data": state.progress.to_payload()})

        while True:
            message = await queue.get()
            await ws.send_json(message)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug("websocket closed: %s", exc)
    finally:
        state.unsubscribe(queue)
