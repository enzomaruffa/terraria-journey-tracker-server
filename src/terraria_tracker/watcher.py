"""Watch the character file and nudge the event loop when Terraria saves.

Terraria does not write the file once. It writes, flushes, renames and touches a backup,
which fires several filesystem events for a single in-game save. Everything here exists to
collapse that burst into one reload.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from terraria_tracker.logging_setup import logger


class _SaveHandler(FileSystemEventHandler):
    def __init__(self, filename: str, notify: Callable[[], None]) -> None:
        self.filename = filename.lower()
        self.notify = notify

    def _matches(self, event: FileSystemEvent) -> bool:
        if event.is_directory:
            return False
        paths = [event.src_path, getattr(event, "dest_path", None)]
        return any(p and Path(str(p)).name.lower() == self.filename for p in paths)

    def on_any_event(self, event: FileSystemEvent) -> None:
        # `on_modified` alone misses saves on Windows, where Terraria writes to a temp file
        # and renames it over the original — that arrives as a move, not a modify.
        if event.event_type in {"modified", "created", "moved"} and self._matches(event):
            self.notify()


class PlayerFileWatcher:
    def __init__(
        self,
        path: Path,
        loop: asyncio.AbstractEventLoop,
        on_change: Callable[[], object],
        debounce_seconds: float = 0.4,
    ) -> None:
        self.path = path
        self.loop = loop
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds

        self._observer: BaseObserver | None = None
        self._timer: threading.Timer | None = None
        self._timer_lock = threading.Lock()

    def _fire(self) -> None:
        asyncio.run_coroutine_threadsafe(self._run_callback(), self.loop)

    async def _run_callback(self) -> None:
        result = self.on_change()
        if asyncio.iscoroutine(result):
            await result

    def _schedule(self) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def start(self) -> None:
        directory = self.path.parent
        if not directory.is_dir():
            raise FileNotFoundError(f"cannot watch {directory}: directory does not exist")

        handler = _SaveHandler(self.path.name, self._schedule)
        self._observer = Observer()
        self._observer.schedule(handler, str(directory), recursive=False)
        self._observer.start()
        logger.info("watching %s", self.path)

    def stop(self) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
