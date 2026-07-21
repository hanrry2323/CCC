#!/usr/bin/env bash
# F1 backlog 失败计数器 + quarantine 路径回归（F2-1 联跑常态化）
# 薄封装：转发到 tests/e2e/test_f1_backlog_failover.sh
# 用法：bash scripts/smoke-f1-backlog-failover.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== smoke-f1-backlog-failover → e2e =="
bash "$ROOT/tests/e2e/test_f1_backlog_failover.sh"
echo "== smoke-f1-backlog-failover PASS =="
