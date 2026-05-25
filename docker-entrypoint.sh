#!/bin/sh
set -e
exec uvicorn backend.main:app --host "${API_HOST:-0.0.0.0}" --port "${PORT:-8000}"
