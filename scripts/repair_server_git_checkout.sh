#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SERVER="${SERVER:-liukun@100.112.123.6}"
REMOTE_DIR="${REMOTE_DIR:-/home/liukun/j/code/wechat_artical}"
REMOTE_URL="${REMOTE_URL:-$(git -C "${PROJECT_DIR}" remote get-url origin)}"
BRANCH="${BRANCH:-$(git -C "${PROJECT_DIR}" branch --show-current)}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BROKEN_GIT_DIR="${BROKEN_GIT_DIR:-${REMOTE_DIR}.git.broken-${TIMESTAMP}}"

ssh "${SERVER}" /bin/bash <<EOF
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR}"
REMOTE_URL="${REMOTE_URL}"
BRANCH="${BRANCH}"
TIMESTAMP="${TIMESTAMP}"
BROKEN_GIT_DIR="${BROKEN_GIT_DIR}"

if [[ ! -d "\${REMOTE_DIR}" ]]; then
  echo "Remote directory not found: \${REMOTE_DIR}" >&2
  exit 1
fi

if [[ -d "\${REMOTE_DIR}/.git" ]]; then
  mv "\${REMOTE_DIR}/.git" "\${BROKEN_GIT_DIR}"
fi

cd "\${REMOTE_DIR}"
git init -b "\${BRANCH}"

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "\${REMOTE_URL}"
else
  git remote add origin "\${REMOTE_URL}"
fi

git fetch --depth=1 origin "\${BRANCH}"
git reset --hard "origin/\${BRANCH}"
git branch --set-upstream-to="origin/\${BRANCH}" "\${BRANCH}"
git status --short
git rev-parse --short HEAD
EOF
