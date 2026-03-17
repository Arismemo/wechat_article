#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
CURRENT_BRANCH="${CURRENT_BRANCH:-$(git -C "${PROJECT_DIR}" rev-parse --abbrev-ref HEAD)}"
SERVICES="${SERVICES:-api phase2_worker phase3_worker phase4_worker feedback_worker topic_fetch_worker}"
SKIP_SETUP="${SKIP_SETUP:-0}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

unit_name() {
  case "$1" in
    api) echo "wechat_artical-api.service" ;;
    phase2_worker) echo "wechat_artical-worker@phase2_worker.service" ;;
    phase3_worker) echo "wechat_artical-worker@phase3_worker.service" ;;
    phase4_worker) echo "wechat_artical-worker@phase4_worker.service" ;;
    feedback_worker) echo "wechat_artical-worker@feedback_worker.service" ;;
    topic_fetch_worker) echo "wechat_artical-worker@topic_fetch_worker.service" ;;
    *)
      echo "Unsupported service: $1" >&2
      return 1
      ;;
  esac
}

cd "${PROJECT_DIR}"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Current checkout does not have a valid HEAD." >&2
  exit 1
fi

git pull --ff-only origin "${CURRENT_BRANCH}"

if [[ "${SKIP_SETUP}" != "1" ]]; then
  bash "${PROJECT_DIR}/scripts/setup_local_host.sh"
fi

if [[ "${RUN_MIGRATIONS}" == "1" ]]; then
  bash "${PROJECT_DIR}/scripts/local_runtime.sh" migrate
fi

UNITS=()
for service in ${SERVICES}; do
  UNITS+=("$(unit_name "${service}")")
done

run_root systemctl restart "${UNITS[@]}"
run_root systemctl --no-pager --full --lines=20 status "${UNITS[@]}" || true

if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error "${HEALTHCHECK_URL}"
  echo
fi
