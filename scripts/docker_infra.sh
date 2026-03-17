#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
TAIL_LINES="${TAIL_LINES:-50}"
COMMAND="${1:-}"

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" | grep -q ":${port}"
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return
  fi
  return 1
}

usage() {
  cat <<'EOF'
Usage:
  bash scripts/docker_infra.sh up
  bash scripts/docker_infra.sh down
  bash scripts/docker_infra.sh restart
  bash scripts/docker_infra.sh status
  bash scripts/docker_infra.sh logs

Managed services:
  postgres
  redis

This helper is only for official infrastructure containers.
It must not be used to start the project application containers.
EOF
}

cd "${PROJECT_DIR}"

case "${COMMAND}" in
  up)
    if port_in_use 5432; then
      echo "[docker_infra] port 5432 is already in use. Do not start docker postgres on this host." >&2
      exit 1
    fi
    if port_in_use 6379; then
      echo "[docker_infra] port 6379 is already in use. Do not start docker redis on this host." >&2
      exit 1
    fi
    docker compose up -d postgres redis
    ;;
  down)
    docker compose stop postgres redis
    ;;
  restart)
    docker compose restart postgres redis
    ;;
  status)
    docker compose ps postgres redis
    ;;
  logs)
    docker compose logs --tail "${TAIL_LINES}" postgres redis
    ;;
  *)
    usage
    exit 1
    ;;
esac
