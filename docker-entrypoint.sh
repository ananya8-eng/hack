#!/bin/sh
set -e

echo "Starting FastAPI on port ${PORT:-10000}"

exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-10000}"