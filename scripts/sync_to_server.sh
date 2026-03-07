#!/usr/bin/env bash

set -euo pipefail

SERVER="${SERVER:-liukun@100.112.123.6}"
REMOTE_DIR="${REMOTE_DIR:-/home/liukun/j/code/wechat_artical}"

COPYFILE_DISABLE=1 COPY_EXTENDED_ATTRIBUTES_DISABLE=1 tar \
  --exclude='.env' \
  --exclude='data' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  -cf - . | ssh "${SERVER}" "cd '${REMOTE_DIR}' && tar -xf -"
