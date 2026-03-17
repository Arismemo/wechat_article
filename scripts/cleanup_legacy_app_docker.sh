#!/usr/bin/env bash

set -euo pipefail

LEGACY_CONTAINERS=(
  wechat_artical_api
  wechat_artical_phase2_worker
  wechat_artical_phase3_worker
  wechat_artical_phase4_worker
  wechat_artical_feedback_worker
)

FOUND_CONTAINER=0
for name in "${LEGACY_CONTAINERS[@]}"; do
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${name}"; then
    FOUND_CONTAINER=1
    break
  fi
done

if [[ "${FOUND_CONTAINER}" == "1" ]]; then
  echo "[cleanup_legacy_app_docker] removing stopped legacy app containers"
  docker rm -f "${LEGACY_CONTAINERS[@]}" >/dev/null 2>&1 || true
else
  echo "[cleanup_legacy_app_docker] no legacy app containers found"
fi

while IFS= read -r image_ref; do
  [[ -n "${image_ref}" ]] || continue
  echo "[cleanup_legacy_app_docker] removing image ${image_ref}"
  docker image rm -f "${image_ref}" >/dev/null 2>&1 || true
done < <(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^wechat_artical([:_-].*|:.*)?$' || true)

echo "[cleanup_legacy_app_docker] remaining wechat_artical docker resources:"
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep wechat_artical || true
