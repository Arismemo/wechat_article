#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

echo "[deploy_from_git] Docker-first deploy path is deprecated." >&2
echo "[deploy_from_git] Switching to host-local deploy via scripts/deploy_local_from_git.sh." >&2
exec /bin/bash "${PROJECT_DIR}/scripts/deploy_local_from_git.sh" "$@"
