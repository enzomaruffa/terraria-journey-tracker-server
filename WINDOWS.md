# Running on Windows with nothing installed

You do not need Python, Node, Git, Docker or a copy of this repository.

## The one line

Open **PowerShell** (press `Win`, type `powershell`, press Enter) and paste:

```powershell
irm https://raw.githubusercontent.com/enzomaruffa/terraria-journey-tracker-server/main/install.ps1 | iex
```

That is the whole setup. It will:

1. install [uv](https://docs.astral.sh/uv/) if you do not have it — one self-contained
   `uv.exe`, no system Python involved
2. download the tracker straight from GitHub
3. find your most recently played Terraria character
4. open <http://127.0.0.1:4777> in your browser

Leave the PowerShell window open while you play. Sacrifice something in-game and the page
updates on its own a moment later. Press `Ctrl+C` in that window to stop.

Running the same line again later starts it again, and picks up any newer version.

## What actually gets put on your machine

Three things, all inside your user profile:

- `uv.exe` in `%USERPROFILE%\.local\bin` — a single ~40 MB binary
- a private Python, roughly 60 MB, that uv downloads for itself
- the tracker and its dependencies, under 100 MB

uv will tell you the exact locations on your machine:

```powershell
uv python dir
uv tool dir
uv cache dir
```

Nothing touches a system Python, the registry, or Program Files. Your character file is only
ever opened for reading.

To remove all of it:

```powershell
uv cache clean
Remove-Item -Recurse -Force (uv python dir), (uv tool dir)
Remove-Item -Force "$env:USERPROFILE\.local\bin\uv.exe"
```

## Where it looks for your character

Automatically, newest first:

- `Documents\My Games\Terraria\Players`
- the same path inside OneDrive, if OneDrive has taken over your Documents folder — the real
  location is read from the registry rather than guessed
- the `tModLoader` subfolder of either

To list what it found, or to pick one yourself:

```powershell
$uv = "$env:USERPROFILE\.local\bin\uv.exe"
$zip = "https://github.com/enzomaruffa/terraria-journey-tracker-server/archive/refs/heads/main.zip"

& $uv tool run --from $zip terraria-journey-tracker --list
& $uv tool run --from $zip terraria-journey-tracker "C:\Users\you\Documents\My Games\Terraria\Players\Enzo.plr"
```

## If something goes wrong

**"running scripts is disabled on this system"** — allow it for this window only:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then paste the install line again. This resets when you close the window.

**"uv is not recognised"** right after installing — the new `uv.exe` is not on your `PATH`
until you open a new shell. Close PowerShell, open it again, and re-run the line.

**"no Terraria character files found"** — pass the path yourself using the command above.
The file ends in `.plr`; `.plr.bak` is a backup and will not work.

**Nothing happens when I research something in-game** — Terraria only writes the character
file when it saves, which is on exiting to the menu, on a manual save, and periodically. It
is not instant.

**Windows Firewall prompt** — you can decline it. The tracker binds to `127.0.0.1`, so it is
reachable only from your own machine and never needs to accept an outside connection.

**Antivirus flags `uv.exe`** — it is a well-known open-source tool from Astral, but if your
scanner objects, use the Docker route below instead.

## Alternative: no PowerShell at all

1. Open <https://github.com/enzomaruffa/terraria-journey-tracker-server>
2. **Code → Download ZIP**, then right-click the file → **Extract All**
3. Double-click **`run-windows.bat`** in the extracted folder

It installs uv on first run and starts the tracker the same way. You can also drag a `.plr`
file onto `run-windows.bat` to open that character specifically.

## Alternative: Docker

Only worth it if you already run Docker Desktop. On a machine with nothing installed it is
considerably more work than the one-liner — Docker Desktop is a multi-gigabyte install that
needs WSL 2 and a reboot, to run a tool that is otherwise about 150 MB.

If you do have it, see the Docker section of [README.md](README.md).

## Playing on Steam Deck, macOS or Linux instead

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx --from https://github.com/enzomaruffa/terraria-journey-tracker-server/archive/refs/heads/main.zip terraria-journey-tracker
```

Save locations for those platforms are in [README.md](README.md).
