#!/usr/bin/env bash

set -euo pipefail

echo "[deploy_docker_legacy] Application-level Docker deploy has been removed from this repository." >&2
echo "[deploy_docker_legacy] Project code now runs on host-local Python/systemd only." >&2
echo "[deploy_docker_legacy] Keep Docker only for official infrastructure services via scripts/docker_infra.sh." >&2
exit 1
