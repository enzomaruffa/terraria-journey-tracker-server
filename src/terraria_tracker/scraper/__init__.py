"""Rebuild the bundled game data from the official Terraria wiki.

The previous version of these scripts had every network call commented out, so they could
only reshuffle JSON that was already on disk — there was no way to pick up a new Terraria
version without rewriting them first.
"""

from terraria_tracker.scraper.wiki import CargoClient

__all__ = ["CargoClient"]
