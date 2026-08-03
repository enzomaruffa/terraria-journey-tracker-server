import logging
import os
import sys

LEVEL_COLOURS = {
    logging.DEBUG: "\x1b[38;5;245m",
    logging.INFO: "\x1b[34;1m",
    logging.WARNING: "\x1b[33;1m",
    logging.ERROR: "\x1b[31;1m",
    logging.CRITICAL: "\x1b[41m",
}
RESET = "\x1b[0m"


def _supports_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    # Windows terminals only understand ANSI once virtual terminal processing is on,
    # which Python enables for us on Windows 10+ when the stream is a real console.
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


class ColourFormatter(logging.Formatter):
    def __init__(self, colour: bool) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(message)s", "%H:%M:%S")
        self.colour = colour

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not self.colour:
            return text
        return f"{LEVEL_COLOURS.get(record.levelno, '')}{text}{RESET}"


def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("terraria_tracker")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ColourFormatter(_supports_colour()))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = logging.getLogger("terraria_tracker")
