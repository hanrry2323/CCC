#!/usr/bin/env bash
# ── CCC 自动归档脚本：移入关闭超过 6 个月的任务卡（手动触发与定时触发） ──
#
# 自动寻找 python3 并运行 server.board.archive 模块。
#
# 用法：
#   scripts/archive-cards.sh [选项]
#
# 选项：
#   --dispatch-dir <目录>     任务卡目录（默认 docs/dispatch）
#   --today <YYYY-MM-DD>     模拟今天日期（测试用）
#   -h|--help                显示帮助并退出

set -euo pipefail

# ccc088：索引口径兜底——裸 shell（无 CCC_DATA_DIR）下 server.board.archive 的
# 初载（archive.py:180）与归档后无条件重建（:276）经 loader 回落写
# <repo>/data/cards/cards.index.jsonl（陈旧副本），与生产看板双写分裂。
# 仅认 CCC_DATA_DIR 口径（loader 另支持 DATA_DIR，此处不启用），与生产看板同源。
export CCC_DATA_DIR="${CCC_DATA_DIR:-$HOME/.ccc/data}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 默认值 ──
DISPATCH_DIR="docs/dispatch"
TODAY=""
PYTHON_BIN=""

usage() {
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dispatch-dir) DISPATCH_DIR="$2"; shift 2 ;;
    --today) TODAY="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] 未知参数: $1" >&2; usage; exit 2 ;;
  esac
done

# 解析 python 解释器
if [[ -z "$PYTHON_BIN" ]]; then
  for cand in /usr/local/bin/python3 python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
  done
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] 未找到 python3" >&2
  exit 2
fi

# 调用归档 CLI
ARGS=()
if [[ -n "$DISPATCH_DIR" ]]; then
  ARGS+=( "--dispatch-dir" "$DISPATCH_DIR" )
fi
if [[ -n "$TODAY" ]]; then
  ARGS+=( "--today" "$TODAY" )
fi

( cd "$PROJECT_ROOT" && "$PYTHON_BIN" -m server.board.archive "${ARGS[@]}" )
