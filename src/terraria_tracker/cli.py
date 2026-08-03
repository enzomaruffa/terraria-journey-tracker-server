from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from terraria_tracker import __version__
from terraria_tracker.config import Settings
from terraria_tracker.locate import autodetect_player, discover_players
from terraria_tracker.logging_setup import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terraria-journey-tracker",
        description="Watch a Terraria Journey mode character and track research progress in the browser.",
    )
    parser.add_argument(
        "player_file",
        nargs="?",
        type=Path,
        help="path to a .plr file (auto-detected when omitted)",
    )
    parser.add_argument("--host", help="interface to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, help="port to listen on (default 4777)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser on start")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--list", action="store_true", help="list detected character files and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _resolve_player_file(settings: Settings, logger) -> Path | None:
    if settings.player_file is not None:
        path = settings.player_file.expanduser()
        if not path.is_file():
            logger.error("character file not found: %s", path)
            return None
        return path.resolve()

    detected = autodetect_player()
    if detected is None:
        logger.error(
            "no Terraria character files found. Pass one explicitly:\n"
            '    terraria-journey-tracker "path/to/Character.plr"'
        )
    return detected


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    overrides = {}
    if args.host:
        overrides["host"] = args.host
    if args.port:
        overrides["port"] = args.port
    if args.verbose:
        overrides["verbose"] = True
    if args.no_browser:
        overrides["open_browser"] = False
    if args.player_file:
        overrides["player_file"] = args.player_file

    settings = Settings(**overrides)
    logger = setup_logging(settings.verbose)

    if args.list:
        found = discover_players()
        if not found:
            logger.error("no character files found in any known Terraria save location")
            return 1
        for player in found:
            print(f"{player.name:<24} {player.path}")
        return 0

    player_file = _resolve_player_file(settings, logger)
    if player_file is None:
        return 1
    settings.player_file = player_file

    # Imported here so `--list` and `--help` stay fast and do not need the game data.
    from terraria_tracker.api import create_app

    app = create_app(settings)

    url = f"http://{'127.0.0.1' if settings.host in {'0.0.0.0', '::'} else settings.host}:{settings.port}"
    logger.info("tracker running at %s", url)

    if settings.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="debug" if settings.verbose else "warning",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
