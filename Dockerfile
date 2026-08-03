# Builds the Svelte client and the Python tracker into one image, so the container serves
# the UI and the API on a single port.
#
# The client lives in a separate repository and is supplied as a named build context:
#   docker build --build-context webclient=../terraria-journey-tracker-web-client -t terraria-tracker .
# `docker compose up` wires that up for you.

FROM node:24-alpine AS web
WORKDIR /client
COPY --from=webclient package.json package-lock.json ./
RUN npm ci
COPY --from=webclient . .
RUN npm run build


FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS runtime
WORKDIR /app

# Install dependencies from the lockfile first so code edits do not bust the layer cache.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY data ./data
COPY src ./src
COPY --from=web /client/build ./src/terraria_tracker/web
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    TERRARIA_HOST=0.0.0.0 \
    TERRARIA_OPEN_BROWSER=false \
    # Filesystem events do not cross a bind mount, so watch by polling in a container.
    TERRARIA_POLL=true

EXPOSE 4777

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:4777/api/health')"

ENTRYPOINT ["terraria-journey-tracker"]
