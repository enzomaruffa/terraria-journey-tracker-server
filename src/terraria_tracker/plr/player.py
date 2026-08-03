"""Extract Journey mode research progress from a Terraria character file.

Terraria writes the research table near the end of a densely packed binary blob whose
layout shifts with almost every content patch. The previous version of this parser walked
to it with hardcoded jumps (``offset += 2460 + 231`` then ``offset += 107``), so each
Terraria update silently produced garbage until someone re-counted the bytes by hand.

This parser instead *locates* the research table by its shape. Every entry is a .NET
length-prefixed string followed by a little-endian int32, and every string has to be an
item internal name the game actually ships. A run of those back to back is a fingerprint
nothing else in the file reproduces, so we can find the table without knowing — or
caring — what Re-Logic added ahead of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from terraria_tracker.plr.crypto import decrypt_player_file
from terraria_tracker.plr.reader import BinaryReader, BinaryReadError

MAGIC = b"relogic"
HEADER_SIZE = 24  # version(4) + "relogic"(7) + filetype(1) + revision(4) + favourite(8)

DIFFICULTY_NAMES = {0: "classic", 1: "mediumcore", 2: "hardcore", 3: "journey"}
JOURNEY_DIFFICULTY = 3

# Internal names are ASCII identifiers ("IronPickaxe", "DD2ElderCrystal", "Zenith").
_INTERNAL_NAME_RE = re.compile(rb"^[A-Za-z][A-Za-z0-9_]*$")
_MIN_NAME_LEN = 2
_MAX_NAME_LEN = 64

# A sacrifice count above this is not a real research entry — the most expensive item in
# the game needs 100. The ceiling only has to be tight enough to reject random bytes.
_MAX_SACRIFICE = 10_000

# How many consecutive well-formed entries we demand before trusting an offset on the
# strength of the run alone. Random data clearing this bar is not a realistic possibility.
_MIN_RUN = 12

# Terraria writes the entry count immediately before the table. When that count matches the
# run exactly, far fewer entries are needed to be sure — which is what lets a freshly made
# Journey character, with only a handful of items researched, still be read.
_MIN_VERIFIED_RUN = 3


class PlayerFileError(Exception):
    pass


@dataclass(slots=True)
class PlayerSave:
    name: str
    difficulty: int
    file_version: int
    research: dict[str, int] = field(default_factory=dict)
    research_found: bool = False
    #: True when the entry count Terraria stores ahead of the table matches what we read,
    #: which upgrades the scan from "very probably right" to "confirmed against the file".
    research_verified: bool = False

    @property
    def difficulty_name(self) -> str:
        return DIFFICULTY_NAMES.get(self.difficulty, "unknown")

    @property
    def is_journey(self) -> bool:
        return self.difficulty == JOURNEY_DIFFICULTY


def _read_header(reader: BinaryReader) -> tuple[int, str, int]:
    """Return ``(file_version, character_name, difficulty)``.

    Only the first few fields are read. Everything after the difficulty byte varies by
    game version and is deliberately left to the scanner.
    """
    file_version = reader.read_uint32()

    magic = reader.read(len(MAGIC))
    if magic != MAGIC:
        raise PlayerFileError(
            "this does not look like a Terraria character file (missing 'relogic' marker) — "
            "check that the path points at a .plr and not a .wld or a backup"
        )

    reader.offset = HEADER_SIZE
    name = reader.read_string()

    difficulty = reader.read_uint8()
    if difficulty not in DIFFICULTY_NAMES:
        difficulty = -1

    return file_version, name, difficulty


def _candidate_entry(buffer: bytes, offset: int) -> tuple[str, int, int] | None:
    """Try to read one ``(name, sacrifices)`` entry at ``offset``.

    Returns ``(name, count, next_offset)`` or ``None`` when the bytes cannot be one.
    Kept allocation-light because it runs once per byte of the file.
    """
    length = buffer[offset]
    # A length byte with the continuation bit set means a string too long to be an
    # internal name, so the single-byte read below is sufficient here.
    if not _MIN_NAME_LEN <= length <= _MAX_NAME_LEN:
        return None

    start = offset + 1
    end = start + length
    if end + 4 > len(buffer):
        return None

    raw = buffer[start:end]
    if not _INTERNAL_NAME_RE.match(raw):
        return None

    count = int.from_bytes(buffer[end : end + 4], "little", signed=True)
    if not 0 <= count <= _MAX_SACRIFICE:
        return None

    return raw.decode("ascii"), count, end + 4


def _scan_research(buffer: bytes, known_names: set[str] | None) -> tuple[dict[str, int], int, bool] | None:
    """Find the research table and return ``(entries, start_offset, count_verified)``.

    ``known_names`` is the set of internal names shipped in the bundled item data. When
    supplied, every entry in a run must be one of them, which is what makes a false match
    effectively impossible.
    """
    best: tuple[dict[str, int], int, bool] | None = None

    offset = HEADER_SIZE
    limit = len(buffer) - 8
    while offset < limit:
        first = _candidate_entry(buffer, offset)
        if first is None:
            offset += 1
            continue

        entries: dict[str, int] = {}
        cursor = offset
        while cursor < limit:
            entry = _candidate_entry(buffer, cursor)
            if entry is None:
                break
            name, count, cursor = entry
            if known_names is not None and name not in known_names:
                break
            if name in entries:  # the table is a dictionary; a repeat means we drifted
                break
            entries[name] = count

        verified = _count_matches(buffer, offset, len(entries))
        long_enough = len(entries) >= _MIN_RUN or (verified and len(entries) >= _MIN_VERIFIED_RUN)

        if long_enough:
            # A run Terraria's own count agrees with always beats a longer unverified one.
            if best is None or (verified, len(entries)) > (best[2], len(best[0])):
                best = (entries, offset, verified)
            # Skip past the run we just consumed rather than re-scanning inside it.
            offset = cursor
            continue

        offset += 1

    return best


def _count_matches(buffer: bytes, start: int, found: int) -> bool:
    """Terraria writes the entry count immediately before the table."""
    if start < 4:
        return False
    declared = int.from_bytes(buffer[start - 4 : start], "little", signed=True)
    return declared == found


def parse_player(raw: bytes, known_names: set[str] | None = None) -> PlayerSave:
    """Parse the bytes of a .plr file into a :class:`PlayerSave`."""
    buffer = decrypt_player_file(raw)
    reader = BinaryReader(buffer)

    try:
        file_version, name, difficulty = _read_header(reader)
    except BinaryReadError as exc:
        raise PlayerFileError(f"could not read the character file header: {exc}") from exc

    save = PlayerSave(name=name, difficulty=difficulty, file_version=file_version)

    match = _scan_research(buffer, known_names)
    if match is not None:
        entries, _start, verified = match
        save.research = entries
        save.research_found = True
        save.research_verified = verified

    return save


def read_player_file(path: str | Path, known_names: set[str] | None = None) -> PlayerSave:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PlayerFileError(f"could not read {path}: {exc}") from exc
    return parse_player(raw, known_names)
