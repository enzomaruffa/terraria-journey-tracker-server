from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from terraria_tracker import __version__
from terraria_tracker.api.routes import router
from terraria_tracker.config import Settings
from terraria_tracker.logging_setup import logger
from terraria_tracker.state import TrackerState
from terraria_tracker.watcher import PlayerFileWatcher

WEB_DIR = Path(__file__).resolve().parents[1] / "web"


def _mount_web_client(app: FastAPI) -> None:
    """Serve the built Svelte client from the same port as the API.

    This is what removes the second terminal: with the build present, there is one process
    to start and one URL to open.
    """
    if not (WEB_DIR / "index.html").is_file():
        logger.info("no bundled web client found — run the client separately with `npm run dev`")

        @app.get("/", include_in_schema=False)
        async def _no_client() -> JSONResponse:
            return JSONResponse(
                {
                    "message": "API is running, but no web client is bundled.",
                    "hint": "Start the client with `npm run dev`, or bundle a build with scripts/bundle-web.py.",
                    "api": "/api/status",
                }
            )

        return

    def _serve(path: Path) -> FileResponse:
        """Serve a build file with cache headers that match how it is named.

        Without this the browser applies heuristic freshness and can keep serving a previous
        build after an update, which looks exactly like the update not having happened. Files
        under ``_app/immutable`` carry a content hash in their name, so they can be cached
        forever; everything else — index.html above all — must be revalidated every time.
        """
        immutable = "_app/immutable/" in path.as_posix()
        cache = "public, max-age=31536000, immutable" if immutable else "no-cache, must-revalidate"
        return FileResponse(path, headers={"Cache-Control": cache})

    @app.get("/", include_in_schema=False)
    async def _index() -> FileResponse:
        return _serve(WEB_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa(path: str) -> Response:
        # No build layout is assumed here: whatever the bundled client contains is served,
        # and anything else falls through to index.html for client-side routing.
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        candidate = (WEB_DIR / path).resolve()
        # Reject anything that escapes the build directory before touching the filesystem.
        if candidate.is_relative_to(WEB_DIR) and candidate.is_file():
            return _serve(candidate)
        return _serve(WEB_DIR / "index.html")

    logger.info("serving the web client from %s", WEB_DIR)


def create_app(settings: Settings, state: TrackerState | None = None) -> FastAPI:
    tracker = state or TrackerState(settings.player_file)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        app.state.watcher = None

        def restart_watcher() -> None:
            if app.state.watcher is not None:
                app.state.watcher.stop()
                app.state.watcher = None
            if tracker.player_file is None:
                return
            watcher = PlayerFileWatcher(
                tracker.player_file,
                loop,
                tracker.refresh_and_broadcast,
                debounce_seconds=settings.debounce_seconds,
                poll=settings.poll,
                poll_seconds=settings.poll_seconds,
            )
            try:
                watcher.start()
            except OSError as exc:
                logger.error("could not watch %s: %s", tracker.player_file, exc)
                return
            app.state.watcher = watcher

        app.state.restart_watcher = restart_watcher
        restart_watcher()
        await tracker.refresh_and_broadcast()

        try:
            yield
        finally:
            if app.state.watcher is not None:
                app.state.watcher.stop()

    app = FastAPI(
        title="Terraria Journey Tracker",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.tracker = tracker

    @app.middleware("http")
    async def _no_stale_api(request, call_next):
        """Keep the browser from holding on to API responses.

        Progress changes as you play and the catalogue changes when the data is refreshed, so
        there is no version of these worth reusing. Without an explicit directive a browser is
        free to apply heuristic freshness, which shows up as an update that "did not happen".
        """
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(router)
    _mount_web_client(app)
    return app
