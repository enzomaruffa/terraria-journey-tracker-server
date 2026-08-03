"""Find Terraria character files without making the user paste a path.

Windows is the awkward one: "Documents" is not always ``%USERPROFILE%\\Documents``. OneDrive
Backup silently redirects it, and the authoritative answer lives in the registry, so we ask
there first and fall back to the obvious spots.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from terraria_tracker.logging_setup import logger

SAVE_SUBDIRS = ("Players", "Player")


@dataclass(frozen=True, slots=True)
class FoundPlayer:
    path: Path
    modified: float

    @property
    def name(self) -> str:
        return self.path.stem


def _windows_documents_dirs() -> list[Path]:
    dirs: list[Path] = []

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "Personal")
            dirs.append(Path(os.path.expandvars(value)))
    except (ImportError, OSError) as exc:  # pragma: no cover - Windows only
        logger.debug("could not read Documents location from the registry: %s", exc)

    home = Path.home()
    dirs.append(home / "Documents")
    dirs.append(home / "OneDrive" / "Documents")

    # Windows sets these in mixed case, and the lookup is case-sensitive off Windows.
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")  # noqa: SIM112
    if onedrive:
        dirs.append(Path(onedrive) / "Documents")

    return dirs


def save_roots() -> list[Path]:
    """Directories Terraria (and tModLoader) keep character files in, most likely first."""
    roots: list[Path] = []
    home = Path.home()

    if sys.platform == "win32":
        for documents in _windows_documents_dirs():
            roots.append(documents / "My Games" / "Terraria")
            roots.append(documents / "My Games" / "Terraria" / "tModLoader")
    elif sys.platform == "darwin":
        support = home / "Library" / "Application Support"
        roots.append(support / "Terraria")
        roots.append(support / "Terraria" / "tModLoader")
        roots.append(support / "tModLoader")
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        roots.append(data_home / "Terraria")
        roots.append(data_home / "Terraria" / "tModLoader")
        # Proton keeps a Windows-shaped tree inside the Steam compat data for app 105600.
        proton = (
            home
            / ".steam"
            / "steam"
            / "steamapps"
            / "compatdata"
            / "105600"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "Documents"
            / "My Games"
            / "Terraria"
        )
        roots.append(proton)

    # De-duplicate while preserving order; the lists above overlap on purpose.
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.add(root)
            unique.append(root)
    return unique


def discover_players(extra_roots: list[Path] | None = None) -> list[FoundPlayer]:
    """Return every .plr found, most recently modified first."""
    found: dict[Path, FoundPlayer] = {}

    for root in list(extra_roots or []) + save_roots():
        for subdir in SAVE_SUBDIRS:
            directory = root / subdir
            if not directory.is_dir():
                continue
            for candidate in directory.glob("*.plr"):
                try:
                    resolved = candidate.resolve()
                    if resolved in found:
                        continue
                    found[resolved] = FoundPlayer(resolved, candidate.stat().st_mtime)
                except OSError as exc:
                    logger.debug("skipping %s: %s", candidate, exc)

    return sorted(found.values(), key=lambda p: p.modified, reverse=True)


def autodetect_player() -> Path | None:
    """Pick the most recently played character, which is nearly always the right one."""
    players = discover_players()
    if not players:
        return None
    logger.info("found %d character file(s); using the most recent: %s", len(players), players[0].path.name)
    return players[0].path
