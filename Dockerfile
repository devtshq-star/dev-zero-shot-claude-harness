# syntax=docker/dockerfile:1

# ============================================================================
# Stage 1 — build the Next.js static export (frontend/out, basePath /app)
# ============================================================================
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend

# pnpm via corepack, pinned to the version the repo was built with.
RUN corepack enable && corepack prepare pnpm@11.15.1 --activate

# Install deps first for layer caching, then build.
# --ignore-scripts: skip dependency build scripts (recent pnpm errors on
# unapproved ones, e.g. sharp). The app uses no next/image, so sharp isn't
# needed for the static export.
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY frontend/ ./
RUN pnpm build

# ============================================================================
# Stage 2 — Python runtime (FastAPI + LangGraph), serving the API and the UI
# ============================================================================
FROM python:3.11-slim-bookworm AS runtime

# uv, copied from its official image (pinned major).
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

# Install locked dependencies into /app/.venv (this is where psycopg2-binary
# reliably lands — the whole reason we build in Docker rather than native).
# --no-install-project: the app runs via PYTHONPATH=src, not as an installed pkg.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code, migrations, and the built frontend.
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY --from=frontend /build/frontend/out ./frontend/out

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Informational; Render injects the real port via $PORT.
EXPOSE 8001
CMD ["./docker-entrypoint.sh"]
