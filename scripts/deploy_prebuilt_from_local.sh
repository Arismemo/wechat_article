#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVER="${SERVER:-liukun@100.112.123.6}"
REMOTE_DIR="${REMOTE_DIR:-/home/liukun/j/code/wechat_artical}"
PLATFORM="${PLATFORM:-linux/amd64}"
BASE_IMAGE="${BASE_IMAGE:-wechat_artical-prebuilt:amd64}"
SERVICES="${SERVICES:-api phase2_worker phase3_worker phase4_worker}"
CURRENT_BRANCH="${CURRENT_BRANCH:-$(git -C "${PROJECT_DIR}" branch --show-current)}"

declare -A SERVICE_IMAGES=(
  [api]="wechat_artical-api"
  [phase2_worker]="wechat_artical-phase2_worker"
  [phase3_worker]="wechat_artical-phase3_worker"
  [phase4_worker]="wechat_artical-phase4_worker"
)

declare -A SELECTED_IMAGES=()
REMOTE_SERVICES=()

SELECTED_IMAGES["${SERVICE_IMAGES[api]}"]=1

for service in ${SERVICES}; do
  if [[ -z "${SERVICE_IMAGES[$service]:-}" ]]; then
    echo "Unsupported service: ${service}" >&2
    exit 1
  fi
  SELECTED_IMAGES["${SERVICE_IMAGES[$service]}"]=1
  REMOTE_SERVICES+=("${service}")
done

cd "${PROJECT_DIR}"

docker build --platform "${PLATFORM}" -t "${BASE_IMAGE}" .

for image in "${!SELECTED_IMAGES[@]}"; do
  docker tag "${BASE_IMAGE}" "${image}"
done

docker save "${!SELECTED_IMAGES[@]}" | ssh "${SERVER}" docker load

REMOTE_SERVICE_ARGS="${REMOTE_SERVICES[*]}"

ssh "${SERVER}" /bin/bash <<EOF
set -euo pipefail

cd "${REMOTE_DIR}"
git pull --ff-only origin "${CURRENT_BRANCH}"
docker compose up -d --no-build api
docker compose run --rm api alembic upgrade head
docker compose up -d --no-build ${REMOTE_SERVICE_ARGS}
docker compose ps api ${REMOTE_SERVICE_ARGS}
EOF
