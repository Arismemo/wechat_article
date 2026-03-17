#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WITH_DEV="${WITH_DEV:-0}"
PLAYWRIGHT_INSTALL_DEPS="${PLAYWRIGHT_INSTALL_DEPS:-0}"
INSTALL_PLAYWRIGHT_BROWSER="${INSTALL_PLAYWRIGHT_BROWSER:-auto}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

cd "${PROJECT_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel

if [[ "${WITH_DEV}" == "1" ]]; then
  "${VENV_DIR}/bin/pip" install -e ".[dev]"
else
  "${VENV_DIR}/bin/pip" install -e .
fi

if [[ "${PLAYWRIGHT_INSTALL_DEPS}" == "1" ]]; then
  run_root "${VENV_DIR}/bin/python" -m playwright install-deps chromium
fi

has_system_browser=0
if command -v google-chrome >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1; then
  has_system_browser=1
fi

if [[ "${INSTALL_PLAYWRIGHT_BROWSER}" == "1" ]] || [[ "${INSTALL_PLAYWRIGHT_BROWSER}" == "auto" && "${has_system_browser}" != "1" ]]; then
  "${VENV_DIR}/bin/python" -m playwright install --no-shell chromium
fi

echo "Local host runtime is ready at ${VENV_DIR}."
