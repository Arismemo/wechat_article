#!/usr/bin/env bash

set -euo pipefail

echo "[deploy_prebuilt_from_local] Prebuilt Docker image deploy has been removed from this repository." >&2
echo "[deploy_prebuilt_from_local] Project code now runs on host-local Python/systemd only." >&2
echo "[deploy_prebuilt_from_local] Use scripts/deploy_local_from_git.sh for normal releases." >&2
exit 1
