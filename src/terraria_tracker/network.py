"""Reaching the tracker from another device on the same network.

Journey mode is played on a PC while a phone sits next to it, and the phone is a better
place for a checklist than a second window. The tracker binds to loopback by default, so
this is opt-in: nothing is exposed to the network unless asked for.
"""

from __future__ import annotations

import socket


def lan_address() -> str | None:
    """The address other devices on this network can reach us on.

    Opening a UDP socket towards a public address makes the OS pick the interface it would
    actually route through, which is more reliable than reading the hostname — that often
    resolves to 127.0.0.1. No packets are sent.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        address = probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()

    return None if address.startswith("127.") else address


def qr_lines(url: str) -> list[str]:
    """A scannable QR for the URL, or nothing if segno is unavailable."""
    try:
        import io

        import segno
    except ImportError:
        return []

    buffer = io.StringIO()
    segno.make(url, error="m").terminal(out=buffer, compact=True)
    return buffer.getvalue().rstrip("\n").split("\n")
