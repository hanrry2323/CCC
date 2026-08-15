#!/usr/bin/env bash
# HP 知识库回滚脚本（2026-08-16 流程改造 P5 交付承接，参照 mx deploy-rollback.sh）
# ⚠️ 状态：可执行参照——待 HP 子项目交付时固化到 hp 业务仓 scripts/ 并实测。
# 用法:
#   scripts/deploy-rollback.sh                    # 回滚到最近一份备份
#   scripts/deploy-rollback.sh list               # 列出可用备份
#   scripts/deploy-rollback.sh restore <timestamp> # 恢复指定时间戳版本
set -euo pipefail

NODE="hp@192.168.3.131"
DEPLOY_DIR="/data/knowledge"
BACKUP_DIR="${DEPLOY_DIR}/backups"

cmd="${1:-rollback}"

case "$cmd" in
  list)
    echo "=== 可用备份 on ${NODE} ==="
    ssh "${NODE}" "ls -lht ${BACKUP_DIR}/hp-code.*.tar.gz 2>/dev/null || echo '(no backups)'"
    ;;
  restore)
    ts="${2:-}"
    if [ -z "$ts" ]; then
      echo "ERROR: missing timestamp. Usage: $0 restore <YYYYMMDDTHHMMSSZ>" >&2
      exit 1
    fi
    backup="${BACKUP_DIR}/hp-code.${ts}.tar.gz"
    echo "=== 恢复 ${backup} on ${NODE} ==="
    ssh "${NODE}" "test -f ${backup} || { echo 'Backup not found: ${backup}' >&2; exit 1; }"
    ssh "${NODE}" "cd /data && tar xzf ${backup} --overwrite"
    echo "=== 已恢复 ${ts}。重启 MCP/memory-store 后验证（健康探活 8083/8082/5432）。 ==="
    ;;
  rollback|"")
    echo "=== 回滚到最近一份备份 on ${NODE} ==="
    latest="$(ssh "${NODE}" "ls -t ${BACKUP_DIR}/hp-code.*.tar.gz 2>/dev/null | head -1")"
    if [ -z "$latest" ]; then
      echo "ERROR: no backups found in ${BACKUP_DIR}" >&2
      exit 1
    fi
    ts="$(basename "${latest}" | sed 's/hp-code\.\(.*\)\.tar\.gz/\1/')"
    echo "Latest backup: $(basename "${latest}")"
    "$0" restore "${ts}"
    ;;
  *)
    echo "Usage: $0 [list|restore <timestamp>|rollback]" >&2
    exit 1
    ;;
esac
