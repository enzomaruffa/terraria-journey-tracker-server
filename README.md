# Terraria Journey Tracker — Server

Watches your Terraria **Journey mode** character file and streams research progress to a
browser as you play. Sacrifice an item in-game, and the page updates a moment later without
a refresh.

Bundled data covers **Terraria 1.4.5.6 "Bigger & Boulder"** — 6,022 researchable items,
4,209 recipes, 58 crafting stations.

The companion UI lives in
[terraria-journey-tracker-web-client](https://github.com/enzomaruffa/terraria-journey-tracker-web-client).

## Quick start

Nothing needs to be installed first — no Python, Node, Git or a copy of this repository.

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/enzomaruffa/terraria-journey-tracker-server/main/install.ps1 | iex
```

**macOS / Linux**:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx --from https://github.com/enzomaruffa/terraria-journey-tracker-server/archive/refs/heads/main.zip terraria-journey-tracker
```

Either way it installs [uv](https://docs.astral.sh/uv/) if missing, finds your most recently
played character, starts watching it, serves the UI and opens
<http://127.0.0.1:4777>. The built web client ships inside the package, so there is no
separate frontend to build or run.

Windows users who would rather not touch PowerShell can download the repository as a ZIP and
double-click `run-windows.bat`. Full walkthrough and troubleshooting:
**[WINDOWS.md](WINDOWS.md)**.

From a checkout, the equivalent is:

```sh
uv run terraria-journey-tracker
uv run terraria-journey-tracker "path/to/Character.plr"
uv run terraria-journey-tracker --list      # show every character it can find
```

### Where character files are found

Auto-detection covers the usual locations, newest character first:

| Platform | Location |
| --- | --- |
| Windows | `Documents\My Games\Terraria\Players` — including a OneDrive-redirected Documents, read from the registry |
| macOS | `~/Library/Application Support/Terraria/Players` |
| Linux | `~/.local/share/Terraria/Players`, plus the Proton prefix for app 105600 |

tModLoader subfolders are picked up on every platform.

## Options

| Flag | Environment variable | Default |
| --- | --- | --- |
| `--host` | `TERRARIA_HOST` | `127.0.0.1` |
| `--port` | `TERRARIA_PORT` | `4777` |
| `--no-browser` | `TERRARIA_OPEN_BROWSER` | opens a browser |
| `-v`, `--verbose` | `TERRARIA_VERBOSE` | off |
| positional path | `TERRARIA_PLAYER_FILE` | auto-detected |
| — | `TERRARIA_POLL` | off (on in Docker) |

All of them are optional; a `.env` file is read if present.

## API

| Route | Purpose |
| --- | --- |
| `GET /api/status` | which character is loaded, which data version is bundled |
| `GET /api/progress` | overview counters, per-item sacrifice counts, craftable ids |
| `GET /api/items` | item catalogue |
| `GET /api/recipes` | recipes with resolved ingredient ids |
| `GET /api/stations` | crafting stations and what each one makes |
| `GET /api/players` | every character file found on this machine |
| `POST /api/players/select` | switch the watched character |
| `WS /api/ws` | `status`, `progress` and `error` messages, pushed on every save |

`GET /api/progress` sends only items with a non-zero sacrifice count, so a fresh character
is a few hundred bytes rather than the whole catalogue.

## Serving the UI from this process

The tracker serves a built client from its own port when one is bundled, which is what makes
the single-command setup possible:

```sh
cd ../terraria-journey-tracker-web-client && npm install && npm run build
cd ../terraria-journey-tracker-server
uv run python scripts/bundle-web.py ../terraria-journey-tracker-web-client/build
```

Without a bundled build the API still runs on its own, and you can develop the client
against it with `npm run dev` on port 5173 (already allowed through CORS).

## Refreshing the game data

When Terraria updates, rebuild the item, recipe and station snapshots from
[terraria.wiki.gg](https://terraria.wiki.gg):

```sh
uv run --extra scrape terraria-tracker-refresh --game-version 1.4.6.0
```

This takes a couple of minutes and rewrites `data/*.json`. It reports anything it could not
resolve rather than dropping it silently. The current snapshot leaves 12 ingredient names
unresolved across 32 of 4,209 recipes — all items removed from Desktop Terraria (Soul of
Blight, the Key Molds, Purple/White Thread), which cannot be researched anyway.

## How the character file is read

`.plr` files are AES-128-CBC encrypted under a key Terraria ships in its own binary, then
laid out as a dense `BinaryWriter` blob whose field order shifts with most content patches.

Rather than walking to the research table with hardcoded offsets — which is why this project
broke on every Terraria update — the parser *searches* for it. Each entry is a
length-prefixed string followed by an `int32`, and every string must be an item internal
name the game actually ships. A run of a dozen of those in a row is a fingerprint nothing
else in the file produces, so the table is found without knowing what precedes it, and the
entry count Terraria stores just ahead of the table confirms the match.

In practice: a new Terraria version changes the data, not the code.

## Development

```sh
uv sync --extra scrape
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Docker

Worth using if you already run Docker; it is not the easy path on a machine with nothing
installed, since Docker Desktop is a far larger install than the tracker itself.

Once the publish workflow has run once, a released image can be pulled directly:

```sh
docker run -p 4777:4777 \
  -e TERRARIA_PLAYER_FILE=/players/Enzo.plr \
  -v "$HOME/Documents/My Games/Terraria/Players:/players:ro" \
  ghcr.io/enzomaruffa/terraria-journey-tracker-server:latest
```

To build it yourself instead: the image builds the web client too, so the container serves
the UI and the API together. Check out both repositories side by side, then:

```sh
export TERRARIA_PLAYERS_DIR="$HOME/Documents/My Games/Terraria/Players"
export TERRARIA_CHARACTER=Enzo.plr

docker compose up
```

Open <http://localhost:4777>. Compose variables:

| Variable | Meaning |
| --- | --- |
| `TERRARIA_PLAYERS_DIR` | your Terraria `Players` folder (required) |
| `TERRARIA_CHARACTER` | the `.plr` inside it to watch (required) |
| `TERRARIA_PORT` | host port, default `4777` |
| `WEB_CLIENT_PATH` | client checkout, default `../terraria-journey-tracker-web-client` |

Two things the compose file handles that are easy to get wrong by hand:

- **The whole `Players` directory is mounted, not the single `.plr`.** Terraria replaces the
  file when it saves, and a bind mount of one file keeps pointing at the old, deleted inode,
  so progress would freeze after the first save.
- **`TERRARIA_POLL` is on.** Filesystem events do not cross a bind mount on Docker Desktop,
  so the container checks the file on a timer instead of waiting to be notified.

To build without compose, pass the client as a named build context:

```sh
docker build --build-context webclient=../terraria-journey-tracker-web-client -t terraria-tracker .
```

## License

[MIT](https://choosealicense.com/licenses/mit/)
