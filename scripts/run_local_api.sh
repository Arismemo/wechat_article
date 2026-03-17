#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"

if [[ ! -x "${VENV_DIR}/bin/uvicorn" ]]; then
  echo "[run_local_api] virtualenv not found: ${VENV_DIR}" >&2
  echo "[run_local_api] run bash scripts/setup_local_host.sh first" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[run_local_api] env file not found: ${ENV_FILE}" >&2
  echo "[run_local_api] create it from .env.example first" >&2
  exit 1
fi

export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

cd "${PROJECT_DIR}"

exec "${VENV_DIR}/bin/uvicorn" app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
