#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "${PROJECT_DIR}"

git pull --ff-only
docker compose build api phase2_worker
docker compose up -d api
docker compose run --rm api alembic upgrade head
docker compose up -d phase2_worker
docker compose ps
