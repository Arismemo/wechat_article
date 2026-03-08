#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVICES="${SERVICES:-api phase2_worker phase3_worker phase4_worker feedback_worker}"
SKIP_BUILD="${SKIP_BUILD:-0}"
CURRENT_BRANCH="${CURRENT_BRANCH:-$(git -C "${PROJECT_DIR}" rev-parse --abbrev-ref HEAD)}"

cd "${PROJECT_DIR}"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Current checkout does not have a valid HEAD."
  echo "Run scripts/repair_server_git_checkout.sh first to rebuild the server-side Git metadata."
  exit 1
fi

git pull --ff-only origin "${CURRENT_BRANCH}"

if [[ "${SKIP_BUILD}" != "1" ]]; then
  docker compose build ${SERVICES}
fi

docker compose up -d api
docker compose run --rm api alembic upgrade head
docker compose up -d ${SERVICES}
docker compose ps ${SERVICES}
