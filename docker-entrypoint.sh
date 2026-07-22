#!/bin/sh
set -e

# Apply database migrations (needs AGENT_DATABASE_URL set in the environment).
echo "Applying database migrations..."
alembic upgrade head

# Serve the app. Render provides $PORT; default to 8001 for local runs.
echo "Starting server on port ${PORT:-8001}..."
exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8001}"
