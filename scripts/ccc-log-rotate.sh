#!/bin/bash
# ccc-log-rotate.sh — Phase 3.5: newsyslog 风格日志轮转注册
#
# 给 launchd 常驻服务（ccc-engine / chat-server / board-server / agent-sidecar）
# 的 stdout/stderr 日志加 5MB rotate + 保留 3 份。macOS 用 newsyslog -nr 注册。
#
# 用法：
#   bash scripts/ccc-log-rotate.sh            # 注册 + 立即轮转一次
#   bash scripts/ccc-log-rotate.sh --check     # 仅打印当前日志大小
#
# 不依赖 root（用户级日志）；newsyslog.conf.d 需要 root，本脚本走用户级 cron 替代。
set -euo pipefail

CCC_HOME="${CCC_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
CCC_LOG_DIR="${HOME}/.ccc/logs"
LOGS_DIR="${HOME}/Library/Logs/CCC"
MAX_BYTES=$((5 * 1024 * 1024))  # 5MB
BACKUP_COUNT=3

mkdir -p "$CCC_LOG_DIR" "$LOGS_DIR"

# 监控的日志文件清单
read -r -d '' LOG_FILES <<'EOF' || true
~/.ccc/logs/ccc-engine.out.log
~/.ccc/logs/ccc-engine.err.log
~/.ccc/logs/ccc-chat-server.out.log
~/.ccc/logs/ccc-chat-server.err.log
~/.ccc/logs/ccc-board.out.log
~/.ccc/logs/ccc-board.err.log
~/Library/Logs/CCC/agent-sidecar.out.log
~/Library/Logs/CCC/agent-sidecar.err.log
EOF

expand_log() { echo "${1/#\~/$HOME}"; }

rotate_one() {
  local f="$1"
  f="$(expand_log "$f")"
  if [[ ! -f "$f" ]]; then return 0; fi
  local size
  size=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if (( size < MAX_BYTES )); then
    echo "  ok    ${f} ($(( size / 1024 ))KB < $(( MAX_BYTES / 1024 ))KB)"
    return 0
  fi
  # 轮转：.3 删除，.2 → .3，.1 → .2，原 → .1
  for i in $(seq $((BACKUP_COUNT - 1)) -1 1); do
    if [[ -f "${f}.${i}" ]]; then
      mv -f "${f}.${i}" "${f}.$((i + 1))"
    fi
  done
  mv -f "$f" "${f}.1"
  : > "$f"
  echo "  rotated ${f} ($(( size / 1024 ))KB → ${f}.1)"
}

check_only() {
  echo "== CCC 日志大小检查 =="
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    f="$(expand_log "$f")"
    if [[ -f "$f" ]]; then
      size=$(stat -f%z "$f" 2>/dev/null || echo 0)
      flag="ok"
      (( size >= MAX_BYTES )) && flag="OVER"
      printf "  %-7s %s (%dKB)\n" "$flag" "$f" "$((size / 1024))"
    fi
  done <<< "$LOG_FILES"
}

register_cron() {
  # macOS 用户级 cron：每小时检查一次（不依赖 root / newsyslog.conf.d）
  local crontab_marker="# CCC-log-rotate (auto)"
  local cmd="bash ${CCC_HOME}/scripts/ccc-log-rotate.sh >/dev/null 2>&1"
  local existing
  existing=$(crontab -l 2>/dev/null || true)
  if echo "$existing" | grep -q "CCC-log-rotate"; then
    echo "✓ cron 已注册（每小时轮转检查）"
    return 0
  fi
  local new_crontab
  new_crontab="${existing}${existing:+$'\n'}0 * * * * ${cmd} ${crontab_marker}"
  echo "$new_crontab" | crontab -
  echo "✓ cron 已注册：每小时检查日志大小，超 5MB 即轮转（保留 ${BACKUP_COUNT} 份）"
}

main() {
  if [[ "${1:-}" == "--check" ]]; then
    check_only
    return 0
  fi
  echo "== CCC 日志轮转 =="
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    rotate_one "$f"
  done <<< "$LOG_FILES"
  register_cron
  echo "  上限：$(( MAX_BYTES / 1024 / 1024 ))MB · 保留 ${BACKUP_COUNT} 份"
  echo "  手动检查：bash ${CCC_HOME}/scripts/ccc-log-rotate.sh --check"
}

main "$@"
