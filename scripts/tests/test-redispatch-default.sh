#!/usr/bin/env bash
# 静态契约测试：重派脚本默认使用 LAN 看板地址，并允许 CCC_BOARD_URL 覆盖。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/../redispatch-card.sh"

bash -n "$SCRIPT"
grep -Fq 'BOARD_URL="${CCC_BOARD_URL:-http://192.168.3.116:7788}"' "$SCRIPT" \
  || { echo "FAIL: 重派脚本默认地址或覆盖变量不符合契约" >&2; exit 1; }

# 仅验证静态来源，不访问看板服务。
echo "redispatch 默认地址静态契约通过"
