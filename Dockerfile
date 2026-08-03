FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install dependencies from the lockfile first so code edits do not bust the layer cache.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY data ./data
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    TERRARIA_HOST=0.0.0.0 \
    TERRARIA_OPEN_BROWSER=false \
    TERRARIA_PLAYER_FILE=/data/player.plr

EXPOSE 4777

# Mount the character file read-only, e.g.
#   docker run -p 4777:4777 -v "$HOME/.local/share/Terraria/Players/Enzo.plr:/data/player.plr:ro" tracker
ENTRYPOINT ["terraria-journey-tracker"]
