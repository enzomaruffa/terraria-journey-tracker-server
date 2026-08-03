"""Shared tracker state plus the fan-out to connected WebSocket clients."""

from __future__ import annotations

import asyncio
from pathlib import Path

from terraria_tracker.gamedata import GameData, load_game_data
from terraria_tracker.logging_setup import logger
from terraria_tracker.plr import PlayerFileError, read_player_file
from terraria_tracker.progress import Progress, build_progress


class TrackerState:
    def __init__(self, player_file: Path | None = None) -> None:
        self.data: GameData = load_game_data()
        self.player_file = player_file
        self.progress: Progress | None = None
        self.error: str | None = None

        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ reading

    def reload(self) -> Progress | None:
        """Re-read the character file. Safe to call from a worker thread."""
        if self.player_file is None:
            self.error = "no character file selected"
            return None

        try:
            save = read_player_file(self.player_file, known_names=self.data.internal_names)
        except PlayerFileError as exc:
            # A read landing mid-save is normal; the watcher will call us again.
            self.error = str(exc)
            logger.debug("could not read %s: %s", self.player_file, exc)
            return None

        if not save.research_found:
            logger.warning(
                "no research table found in %s — is %s a Journey mode character?",
                self.player_file.name,
                save.name or "this character",
            )

        self.error = None
        self.progress = build_progress(save, self.data)
        return self.progress

    def set_player_file(self, path: Path) -> None:
        self.player_file = path
        self.progress = None

    # -------------------------------------------------------------- broadcasting

    def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=8)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        self._subscribers.discard(queue)

    async def broadcast(self, message: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # A client that cannot keep up gets the next update instead; dropping is
                # correct here because every message is a full snapshot.
                logger.debug("dropping update for a slow websocket client")

    async def refresh_and_broadcast(self) -> None:
        async with self._lock:
            progress = await asyncio.to_thread(self.reload)

        if progress is None:
            if self.error:
                await self.broadcast({"type": "error", "message": self.error})
            return

        await self.broadcast({"type": "progress", "data": progress.to_payload()})

    # -------------------------------------------------------------------- output

    def status_payload(self) -> dict:
        return {
            "playerFile": str(self.player_file) if self.player_file else None,
            "playerFileName": self.player_file.name if self.player_file else None,
            "gameVersion": self.data.game_version,
            "dataGeneratedAt": self.data.meta.get("generatedAt"),
            "itemCount": len(self.data.items),
            "recipeCount": len(self.data.recipes),
            "stationCount": len(self.data.stations),
            "droppedItemCount": len(self.data.drops),
            "error": self.error,
            "hasProgress": self.progress is not None,
        }
