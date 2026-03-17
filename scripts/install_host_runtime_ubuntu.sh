#!/usr/bin/env bash

set -euo pipefail

INSTALL_CHROME="${INSTALL_CHROME:-1}"
INSTALL_POSTGRES="${INSTALL_POSTGRES:-0}"
INSTALL_REDIS="${INSTALL_REDIS:-0}"
ENABLE_SERVICES="${ENABLE_SERVICES:-1}"

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This script currently supports Ubuntu/Debian hosts with apt-get." >&2
  exit 1
fi

APT_PACKAGES=(
  python3-venv
  python3-pip
  python3-dev
  build-essential
  libpq-dev
  curl
  ca-certificates
  gnupg
)

if [[ "${INSTALL_POSTGRES}" == "1" ]]; then
  APT_PACKAGES+=(postgresql postgresql-client)
fi

if [[ "${INSTALL_REDIS}" == "1" ]]; then
  APT_PACKAGES+=(redis-server)
fi

run_root apt-get update
run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"

if [[ "${INSTALL_CHROME}" == "1" ]] && ! command -v google-chrome >/dev/null 2>&1; then
  run_root install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | run_root gpg --dearmor --batch --yes -o /etc/apt/keyrings/google-linux.gpg
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-linux.gpg] https://dl.google.com/linux/chrome/deb/ stable main" | run_root tee /etc/apt/sources.list.d/google-chrome.list >/dev/null
  run_root apt-get update
  run_root env DEBIAN_FRONTEND=noninteractive apt-get install -y google-chrome-stable
fi

if [[ "${ENABLE_SERVICES}" == "1" ]] && command -v systemctl >/dev/null 2>&1; then
  if [[ "${INSTALL_POSTGRES}" == "1" ]]; then
    run_root systemctl enable --now postgresql
  fi
  if [[ "${INSTALL_REDIS}" == "1" ]]; then
    run_root systemctl enable --now redis-server
  fi
fi

echo "Host runtime dependencies are ready."
echo "If you keep PostgreSQL/Redis in official Docker containers, run: bash scripts/docker_infra.sh up"
