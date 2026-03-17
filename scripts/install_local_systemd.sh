#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
TEMPLATE_DIR="${TEMPLATE_DIR:-${PROJECT_DIR}/deploy/systemd}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
RUN_USER="${RUN_USER:-$(id -un)}"
START_SERVICES="${START_SERVICES:-0}"
RUN_SYSTEMCTL="${RUN_SYSTEMCTL:-1}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

write_target() {
  local destination="$1"
  if [[ -w "${UNIT_DIR}" ]]; then
    tee "${destination}" >/dev/null
  else
    run_root tee "${destination}" >/dev/null
  fi
}

UNITS=(
  wechat_artical-api.service
  wechat_artical-worker@phase2_worker.service
  wechat_artical-worker@phase3_worker.service
  wechat_artical-worker@phase4_worker.service
  wechat_artical-worker@feedback_worker.service
  wechat_artical-worker@topic_fetch_worker.service
)

render_template() {
  local template_path="$1"
  sed \
    -e "s#__PROJECT_DIR__#${PROJECT_DIR}#g" \
    -e "s#__RUN_USER__#${RUN_USER}#g" \
    "${template_path}"
}

render_template "${TEMPLATE_DIR}/wechat_artical-api.service.template" | write_target "${UNIT_DIR}/wechat_artical-api.service"
render_template "${TEMPLATE_DIR}/wechat_artical-worker@.service.template" | write_target "${UNIT_DIR}/wechat_artical-worker@.service"

if [[ "${RUN_SYSTEMCTL}" == "1" ]]; then
  run_root systemctl daemon-reload
  run_root systemctl enable "${UNITS[@]}"

  if [[ "${START_SERVICES}" == "1" ]]; then
    run_root systemctl restart "${UNITS[@]}"
  fi

  run_root systemctl --no-pager --full status "${UNITS[@]}" || true
fi
