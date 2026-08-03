"""Build synthetic .plr files so the parser can be tested without shipping a real save."""

from __future__ import annotations

import random
import struct

from terraria_tracker.plr.crypto import encrypt_player_file

MAGIC = b"relogic"
FILE_TYPE_PLAYER = 3


def write_7bit_encoded_int(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def write_string(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return write_7bit_encoded_int(len(encoded)) + encoded


def build_plr(
    name: str = "Testerino",
    difficulty: int = 3,
    file_version: int = 279,
    research: dict[str, int] | None = None,
    filler_before: int = 3000,
    filler_after: int = 500,
    seed: int = 1234,
    include_count: bool = True,
    encrypt: bool = True,
) -> bytes:
    """Assemble a character file with the research table buried in random filler.

    The filler stands in for the thousands of version-specific bytes (appearance,
    inventory, buffs, ...) the tracker deliberately does not parse.
    """
    rng = random.Random(seed)
    research = research if research is not None else {}

    body = bytearray()
    body += struct.pack("<I", file_version)
    body += MAGIC
    body += bytes([FILE_TYPE_PLAYER])
    body += struct.pack("<I", 0)  # revision
    body += struct.pack("<Q", 0)  # favourite
    body += write_string(name)
    body += bytes([difficulty])

    body += bytes(rng.randrange(256) for _ in range(filler_before))

    if include_count:
        body += struct.pack("<i", len(research))
    for internal_name, count in research.items():
        body += write_string(internal_name)
        body += struct.pack("<i", count)

    body += bytes(rng.randrange(256) for _ in range(filler_after))

    return encrypt_player_file(bytes(body)) if encrypt else bytes(body)
