#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
SERVICE_NAME="${1:-}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[run_local_worker] virtualenv not found: ${VENV_DIR}" >&2
  echo "[run_local_worker] run bash scripts/setup_local_host.sh first" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[run_local_worker] env file not found: ${ENV_FILE}" >&2
  echo "[run_local_worker] create it from .env.example first" >&2
  exit 1
fi

case "${SERVICE_NAME}" in
  phase2|phase2_worker)
    TARGET_SCRIPT="${PROJECT_DIR}/scripts/run_phase2_worker.py"
    ;;
  phase3|phase3_worker)
    TARGET_SCRIPT="${PROJECT_DIR}/scripts/run_phase3_worker.py"
    ;;
  phase4|phase4_worker)
    TARGET_SCRIPT="${PROJECT_DIR}/scripts/run_phase4_worker.py"
    ;;
  feedback|feedback_worker)
    TARGET_SCRIPT="${PROJECT_DIR}/scripts/run_feedback_worker.py"
    ;;
  topic_fetch|topic_fetch_worker)
    TARGET_SCRIPT="${PROJECT_DIR}/scripts/run_topic_fetch_worker.py"
    ;;
  *)
    echo "[run_local_worker] unsupported worker: ${SERVICE_NAME}" >&2
    echo "[run_local_worker] expected one of: phase2_worker phase3_worker phase4_worker feedback_worker topic_fetch_worker" >&2
    exit 1
    ;;
esac

export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

cd "${PROJECT_DIR}"

exec "${VENV_DIR}/bin/python" "${TARGET_SCRIPT}"
