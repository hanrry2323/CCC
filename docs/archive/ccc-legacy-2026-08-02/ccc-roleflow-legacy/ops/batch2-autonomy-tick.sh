#!/usr/bin/env bash
# Durable Batch2 / clawmed autonomy tick — DISABLED (v0.42.4)
# 原逻辑会 hourly wake Engine + 扫 backlog，易与 invent/自动投入叠加吃爆内存。
# 保留脚本以免 launchd 报 missing；实际 no-op。
set -euo pipefail
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] batch2-autonomy DISABLED (auto-inject hard-ban)" \
  >>"$LOG_DIR/batch2-autonomy-tick.log"
exit 0
