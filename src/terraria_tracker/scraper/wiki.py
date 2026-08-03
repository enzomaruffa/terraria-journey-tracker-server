from __future__ import annotations

import html
import re
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import httpx

from terraria_tracker.logging_setup import logger

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_SORT_VALUE_RE = re.compile(r'data-sort-value="([\d.]+)"')

WIKI = "https://terraria.wiki.gg"
API = f"{WIKI}/api.php"
USER_AGENT = "terraria-journey-tracker/2.0 (+https://github.com/enzomaruffa/terraria-journey-tracker-server)"

# The cargo API refuses anything above this.
PAGE_SIZE = 500


class CargoClient:
    def __init__(self, timeout: float = 60.0, pause: float = 0.1, retries: int = 4) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        self.pause = pause
        self.retries = retries

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with backoff. A full refresh is ~30 requests against a public wiki, so a
        single blip should not throw away several minutes of work."""
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                delay = 2**attempt
                logger.warning("request failed (%s); retrying in %ds", exc, delay)
                time.sleep(delay)
        raise RuntimeError(f"giving up on {url} after {self.retries} attempts") from last

    def __enter__(self) -> CargoClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.client.close()

    def query(
        self,
        table: str,
        fields: str,
        where: str | None = None,
        order_by: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Page through a cargo table.

        The offset advances by the number of rows actually returned. The old scraper
        advanced by a hardcoded 49 or 50 against a 500-row page, which quietly skipped
        most of the table.
        """
        offset = 0
        while True:
            params: dict[str, Any] = {
                "action": "cargoquery",
                "format": "json",
                "tables": table,
                "fields": fields,
                "limit": PAGE_SIZE,
                "offset": offset,
            }
            if where:
                params["where"] = where
            if order_by:
                params["order_by"] = order_by

            payload = self._get(API, params).json()

            if "error" in payload:
                raise RuntimeError(f"wiki API error querying {table}: {payload['error']}")

            rows = payload.get("cargoquery", [])
            if not rows:
                return

            for row in rows:
                yield row["title"]

            offset += len(rows)
            logger.debug("%s: fetched %d rows", table, offset)
            if len(rows) < PAGE_SIZE:
                return
            time.sleep(self.pause)

    def get_html(self, page: str) -> str:
        return self._get(f"{WIKI}/wiki/{page}").text


def image_url(image_file: str) -> str:
    """Build the direct upload URL for a wiki image.

    wiki.gg serves uploads from a flat ``/images/<File_Name>`` path. The md5-sharded
    layout the previous scraper computed now answers with a 301 to this one.
    """
    if not image_file:
        return ""
    name = image_file.replace(" ", "_")
    return f"{WIKI}/images/{quote(name[:1].upper() + name[1:])}"


def wiki_url(page_name: str) -> str:
    return f"{WIKI}/wiki/{page_name.replace(' ', '_')}"


def strip_html(value: str | None) -> str:
    """Plain text from a cargo field.

    Fields arrive either as real markup or as escaped entities depending on the query, so
    unescaping happens first and then again after tag removal.
    """
    if not value:
        return ""
    text = html.unescape(value)
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def text_lines(value: str | None) -> list[str]:
    """Split a tooltip into its display lines.

    Tooltips look like ``<span class="gameText">line one<br/>line two</span>``.
    """
    if not value:
        return []
    parts = _BREAK_RE.split(html.unescape(value))
    return [line for line in (strip_html(part) for part in parts) if line]


def sort_value_float(value: str | None) -> float | None:
    """Read the numeric ``data-sort-value`` the wiki attaches to rendered values.

    Coin amounts and drop rates render as markup but carry a plain number as a sort key,
    which is far more usable than parsing "90 Silver Coins" or "1/36 (2.78%)" back out.
    """
    if not value:
        return None
    match = _SORT_VALUE_RE.search(value)
    if match:
        return float(match.group(1))

    # Some rows are already a bare number.
    text = strip_html(value).replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def sort_value(value: str | None) -> int | None:
    """Integer form of :func:`sort_value_float`, for coin values which are whole coppers."""
    number = sort_value_float(value)
    return None if number is None else int(number)
