#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Starting backend stack via Docker Compose..."
docker compose up -d db redis backend celery celery-beat

echo "Starting frontend dev server..."
cd frontend
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev
