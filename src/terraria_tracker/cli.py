from __future__ import annotations

import argparse
import platform
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from terraria_tracker import __version__
from terraria_tracker.config import Settings
from terraria_tracker.locate import SAVE_SUBDIRS, autodetect_player, discover_players, save_roots
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
    parser.add_argument("--doctor", action="store_true", help="print diagnostics for a failed start and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _report_no_characters(logger) -> None:
    """Say where we looked. "Not found" without that is not something a user can act on."""
    logger.error("no Terraria character files found")
    print("\nSearched these locations:", file=sys.stderr)
    for root in save_roots():
        for subdir in SAVE_SUBDIRS:
            directory = root / subdir
            mark = "exists" if directory.is_dir() else "missing"
            print(f"  [{mark:>7}] {directory}", file=sys.stderr)
    print(
        "\nIf your character lives somewhere else, pass the file directly:\n"
        '    terraria-journey-tracker "C:\\path\\to\\Character.plr"\n',
        file=sys.stderr,
    )


def _resolve_player_file(settings: Settings, logger) -> Path | None:
    if settings.player_file is not None:
        path = settings.player_file.expanduser()
        if not path.is_file():
            logger.error("character file not found: %s", path)
            return None
        return path.resolve()

    detected = autodetect_player()
    if detected is None:
        _report_no_characters(logger)
    return detected


def run_doctor() -> int:
    """Print everything needed to diagnose a failed start, in one paste-able block."""
    print(f"terraria-journey-tracker {__version__}")
    print(f"python      {sys.version.split()[0]} ({platform.python_implementation()})")
    print(f"platform    {platform.platform()}")
    print(f"executable  {sys.executable}")

    web_dir = Path(__file__).resolve().parent / "web"
    bundled = (web_dir / "index.html").is_file()
    print(f"web client  {'bundled' if bundled else 'MISSING — the UI will not load'} ({web_dir})")

    try:
        from terraria_tracker.gamedata import data_dir, load_game_data

        data = load_game_data()
        print(f"game data   Terraria {data.game_version}: {len(data.items)} items, {len(data.recipes)} recipes")
        print(f"            {len(data.drops)} items with drop sources")
        print(f"            {data_dir()}")
    except Exception as exc:
        # Reporting a broken install is the whole job here, so nothing is re-raised.
        print(f"game data   FAILED TO LOAD: {exc}")

    print("\nsave locations:")
    for root in save_roots():
        for subdir in SAVE_SUBDIRS:
            directory = root / subdir
            print(f"  [{'exists' if directory.is_dir() else 'missing':>7}] {directory}")

    found = discover_players()
    print(f"\ncharacters found: {len(found)}")
    for player in found:
        size_kb = player.path.stat().st_size / 1024 if player.path.is_file() else 0
        print(f"  {player.name:<24} {size_kb:>7.0f} KB  {player.path}")

    return 0


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

    if args.doctor:
        return run_doctor()

    if args.list:
        found = discover_players()
        if not found:
            _report_no_characters(logger)
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
