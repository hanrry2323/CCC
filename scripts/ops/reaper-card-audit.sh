#!/usr/bin/env bash
# ── scripts/ops/reaper-card-audit.sh ──
# CCC reaper 每日三方对账：卡 / 看板 / 分支（v2.0 P4.2）。
#
# 对账矩阵（详见 docs/notes/2026-09-07-reaper-report.md §2）：
#   card_missing_on_board / board_orphan / state_drift_disk_vs_board /
#   branch_orphan / branch_missing / branch_merged_uncleaned / branch_card_state_conflict
# 差异落 audit ledger（action=reaper_diff）+ ~/.ccc/logs/reaper-diffs.jsonl，
# 当前活跃差异快照写 ~/.ccc/logs/reaper-active.jsonl（看板标黄输入）。
#
# launchd PATH 极简（/usr/bin:/bin:/usr/sbin:/sbin）——不依赖 PATH 里的任何
# 工具，只用 python3 绝对路径（.venv-hub 优先，回退 /usr/bin/python3）。
#
# 部署（launchd）：server/deploy/com.ccc.reaper.plist + scripts/ops/install-reaper-plist.sh

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${CCC_REAPER_LOG_DIR:-${HOME}/.ccc/logs}"
PYTHON_BIN="${CCC_REAPER_PYTHON:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  for cand in "${PROJECT_ROOT}/.venv-hub/bin/python3" /usr/bin/python3; do
    if [[ -x "$cand" ]]; then PYTHON_BIN="$cand"; break; fi
  done
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "reaper: no python3 found (launchd minimal PATH)" >&2
  exit 3
fi

mkdir -p "${LOG_DIR}"

# reaper.py 自带退出码语义：看板不可达/差异非空 → 非零（fail-closed）。
"${PYTHON_BIN}" -m server.ops.reaper \
  --repo-root "${PROJECT_ROOT}" \
  --dispatch "${PROJECT_ROOT}/docs/dispatch" \
  --log-dir "${LOG_DIR}"
rc=$?

# 触发的差异分类计数（供报告/告警摘要）。
if [[ -f "${LOG_DIR}/reaper-active.jsonl" ]]; then
  echo "[reaper] active diffs: $(wc -l < "${LOG_DIR}/reaper-active.jsonl" | tr -d ' ')"
fi

exit "$rc"
