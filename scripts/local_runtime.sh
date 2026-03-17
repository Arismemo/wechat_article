#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
RUN_DIR="${RUN_DIR:-${PROJECT_DIR}/run}"
PID_DIR="${PID_DIR:-${RUN_DIR}/pids}"
LOG_DIR="${LOG_DIR:-${RUN_DIR}/logs}"

SERVICES=(api phase2_worker phase3_worker phase4_worker feedback_worker topic_fetch_worker)

service_command() {
  case "$1" in
    api) echo "${PROJECT_DIR}/scripts/run_local_api.sh" ;;
    phase2_worker) echo "${PROJECT_DIR}/scripts/run_local_worker.sh phase2_worker" ;;
    phase3_worker) echo "${PROJECT_DIR}/scripts/run_local_worker.sh phase3_worker" ;;
    phase4_worker) echo "${PROJECT_DIR}/scripts/run_local_worker.sh phase4_worker" ;;
    feedback_worker) echo "${PROJECT_DIR}/scripts/run_local_worker.sh feedback_worker" ;;
    topic_fetch_worker) echo "${PROJECT_DIR}/scripts/run_local_worker.sh topic_fetch_worker" ;;
    *)
      return 1
      ;;
  esac
}

pid_file() {
  echo "${PID_DIR}/$1.pid"
}

log_file() {
  echo "${LOG_DIR}/$1.log"
}

is_running() {
  local service="$1"
  local pid_path
  pid_path="$(pid_file "${service}")"
  [[ -f "${pid_path}" ]] || return 1
  local pid
  pid="$(cat "${pid_path}")"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

start_service() {
  local service="$1"
  if is_running "${service}"; then
    echo "${service} is already running."
    return 0
  fi
  mkdir -p "${PID_DIR}" "${LOG_DIR}"
  local command
  if ! command="$(service_command "${service}")"; then
    echo "Unknown service: ${service}" >&2
    return 1
  fi
  nohup /bin/bash -lc "cd '${PROJECT_DIR}' && exec ${command}" >>"$(log_file "${service}")" 2>&1 &
  echo $! >"$(pid_file "${service}")"
  echo "started ${service} pid=$(cat "$(pid_file "${service}")")"
}

stop_service() {
  local service="$1"
  if ! is_running "${service}"; then
    rm -f "$(pid_file "${service}")"
    echo "${service} is not running."
    return 0
  fi
  local pid
  pid="$(cat "$(pid_file "${service}")")"
  kill "${pid}"
  rm -f "$(pid_file "${service}")"
  echo "stopped ${service}"
}

status_service() {
  local service="$1"
  if is_running "${service}"; then
    echo "${service}: running pid=$(cat "$(pid_file "${service}")") log=$(log_file "${service}")"
  else
    echo "${service}: stopped"
  fi
}

migrate() {
  cd "${PROJECT_DIR}"
  "${PROJECT_DIR}/.venv/bin/alembic" upgrade head
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/local_runtime.sh migrate
  bash scripts/local_runtime.sh start <service>
  bash scripts/local_runtime.sh stop <service>
  bash scripts/local_runtime.sh restart <service>
  bash scripts/local_runtime.sh status
  bash scripts/local_runtime.sh start-all
  bash scripts/local_runtime.sh stop-all

Services:
  api
  phase2_worker
  phase3_worker
  phase4_worker
  feedback_worker
  topic_fetch_worker
EOF
}

main() {
  local action="${1:-}"
  local target="${2:-}"

  case "${action}" in
    migrate)
      migrate
      ;;
    start)
      [[ -n "${target}" ]] || { usage >&2; exit 1; }
      start_service "${target}"
      ;;
    stop)
      [[ -n "${target}" ]] || { usage >&2; exit 1; }
      stop_service "${target}"
      ;;
    restart)
      [[ -n "${target}" ]] || { usage >&2; exit 1; }
      stop_service "${target}" || true
      start_service "${target}"
      ;;
    status)
      for service in "${SERVICES[@]}"; do
        status_service "${service}"
      done
      ;;
    start-all)
      for service in "${SERVICES[@]}"; do
        start_service "${service}"
      done
      ;;
    stop-all)
      for service in "${SERVICES[@]}"; do
        stop_service "${service}" || true
      done
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
