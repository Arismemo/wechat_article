#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVER="${SERVER:-liukun@100.112.123.6}"
REMOTE_DIR="${REMOTE_DIR:-/home/liukun/j/code/wechat_artical}"
PLATFORM="${PLATFORM:-linux/amd64}"
BASE_IMAGE="${BASE_IMAGE:-wechat_artical-prebuilt:amd64}"
SERVICES="${SERVICES:-api phase2_worker phase3_worker phase4_worker feedback_worker}"
CURRENT_BRANCH="${CURRENT_BRANCH:-$(git -C "${PROJECT_DIR}" branch --show-current)}"
SKIP_LOCAL_BUILD="${SKIP_LOCAL_BUILD:-0}"

platform_parts=(${PLATFORM//\// })
TARGET_OS="${platform_parts[0]}"
TARGET_ARCH="${platform_parts[1]}"

service_image() {
  case "$1" in
    api) echo "wechat_artical-api" ;;
    phase2_worker) echo "wechat_artical-phase2_worker" ;;
    phase3_worker) echo "wechat_artical-phase3_worker" ;;
    phase4_worker) echo "wechat_artical-phase4_worker" ;;
    feedback_worker) echo "wechat_artical-feedback_worker" ;;
    *)
      echo "Unsupported service: $1" >&2
      return 1
      ;;
  esac
}

SELECTED_IMAGES=("$(service_image api)")
REMOTE_SERVICES=()

for service in ${SERVICES}; do
  image="$(service_image "${service}")"
  if [[ ! " ${SELECTED_IMAGES[*]} " =~ " ${image} " ]]; then
    SELECTED_IMAGES+=("${image}")
  fi
  REMOTE_SERVICES+=("${service}")
done

cd "${PROJECT_DIR}"

if [[ "${SKIP_LOCAL_BUILD}" == "1" ]]; then
  if ! docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1; then
    echo "Base image not found: ${BASE_IMAGE}" >&2
    echo "Build it first or set SKIP_LOCAL_BUILD=0." >&2
    exit 1
  fi
else
  docker build --platform "${PLATFORM}" -t "${BASE_IMAGE}" .
fi

IMAGE_OS="$(docker image inspect "${BASE_IMAGE}" --format '{{.Os}}')"
IMAGE_ARCH="$(docker image inspect "${BASE_IMAGE}" --format '{{.Architecture}}')"
if [[ "${IMAGE_OS}" != "${TARGET_OS}" || "${IMAGE_ARCH}" != "${TARGET_ARCH}" ]]; then
  echo "Base image platform mismatch: expected ${TARGET_OS}/${TARGET_ARCH}, got ${IMAGE_OS}/${IMAGE_ARCH}" >&2
  exit 1
fi

for image in "${SELECTED_IMAGES[@]}"; do
  docker tag "${BASE_IMAGE}" "${image}"
done

docker save "${SELECTED_IMAGES[@]}" | ssh "${SERVER}" docker load

REMOTE_SERVICE_ARGS="${REMOTE_SERVICES[*]}"

ssh "${SERVER}" /bin/bash <<EOF
set -euo pipefail

cd "${REMOTE_DIR}"
git pull --ff-only origin "${CURRENT_BRANCH}"
docker compose up -d --no-build --force-recreate api
docker compose run --rm api alembic upgrade head
docker compose up -d --no-build --force-recreate ${REMOTE_SERVICE_ARGS}
docker compose ps api ${REMOTE_SERVICE_ARGS}
EOF
