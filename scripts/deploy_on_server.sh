#!/usr/bin/env bash
# 在宿主机上原地部署最新 main:fetch+reset -> 依赖 -> 迁移 -> 重启服务。
# 幂等、可重复执行。由 GitHub Actions self-hosted runner(在本机)调用,
# 也可手动 `bash scripts/deploy_on_server.sh`。
set -euo pipefail

APP_DIR="${APP_DIR:-/home/liukun/j/code/wechat_artical}"
BRANCH="${DEPLOY_BRANCH:-main}"
VENV="${APP_DIR}/.venv"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/healthz}"
# api + 5 现有 worker + 编委会 worker(单实例)
SERVICES=(api phase2_worker phase3_worker phase4_worker feedback_worker topic_fetch_worker editorial_worker)

run_root() { if [[ "${EUID}" -eq 0 ]]; then "$@"; else sudo "$@"; fi; }
unit_of() { if [[ "$1" == "api" ]]; then echo "wechat_artical-api.service"; else echo "wechat_artical-worker@$1.service"; fi; }

echo "[deploy] === $(date -Is) 部署到 ${APP_DIR}@${BRANCH} ==="
cd "${APP_DIR}"

echo "[deploy] fetch + reset 到 origin/${BRANCH}"
git fetch --quiet origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"
git log --oneline -1

echo "[deploy] 同步运行依赖"
"${VENV}/bin/pip" install -e . -q

echo "[deploy] 数据库迁移"
"${VENV}/bin/alembic" upgrade head

# 清掉可能存在的临时编委会进程(避免与 systemd 单元重复 -> 破坏并发≤3)
run_root systemctl stop wa-editorial.service >/dev/null 2>&1 || true

echo "[deploy] 重启服务"
for svc in "${SERVICES[@]}"; do
  unit="$(unit_of "${svc}")"
  run_root systemctl restart "${unit}"
  echo "  restarted ${unit}"
done
# 编委会 worker 持久化(开机自启)
run_root systemctl enable wechat_artical-worker@editorial_worker.service >/dev/null 2>&1 || true

echo "[deploy] 健康检查"
sleep 4
if curl -fsS -m 10 "${HEALTHCHECK_URL}" >/dev/null; then
  echo "[deploy] OK healthz 通过"
else
  echo "[deploy] !! healthz 失败,请检查 journalctl -u wechat_artical-api" >&2
  exit 1
fi
echo "[deploy] === 完成 ==="
