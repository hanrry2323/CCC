#!/usr/bin/env bash
# ── scripts/spot-check.sh ──
# 环节②抽验（P0-1d · 2026-08-23）
#
# 执行方：环节②（Claude Code / 管理席），不由 DSH 抽验自己。
# 抽样：每批合入 ≥1 张 + 每 5 张抽 1 张（20% 随机），每次合入时执行（approve-merge 批次循环）。
# 本脚本封装单卡四步复核（机械助手，人审签核仍由环节②判定）：
#   1) 测试真实性复核（evidence log 真实退出码）
#   2) 范围复核（scope-check.sh）
#   3) git 真实性复核（git-truth-check.sh）
#   4) ledger↔信封一致性（ledger 有 pass + 分支信封机审通过 + pin 在分支上）
#
# 用法：scripts/spot-check.sh <card_id>
# 退出码：0=抽验通过；非0=抽验发现问题→打回（带 文件:行号 唯一最佳动作）

set -uo pipefail

CARD_ID="${1:?缺 card_id}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${CCC_PYTHON_BIN:-python3}"
# ccc088：索引口径兜底——裸 shell（无 CCC_DATA_DIR）下 loader 读回落
# <repo>/data/cards/cards.index.jsonl 陈旧副本；注入后与生产看板同源（~/.ccc/data）。
export CCC_DATA_DIR="${CCC_DATA_DIR:-$HOME/.ccc/data}"
cd "$PROJECT_ROOT"

# 解析卡路径与分支
CARD_PATH="$(bash "$SCRIPT_DIR/lib/card-resolve.sh" 2>/dev/null || true)"
# fallback: 用 board loader 解析
if ! CARD_PATH="$(python3 - "$CARD_ID" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, ".")
from pathlib import Path
try:
    from server.board.loader import load_dispatch_cards
    items = load_dispatch_cards(Path("docs/dispatch"))
    for it in items:
        if it.id == sys.argv[1]:
            # 从索引取 path
            from server.board.loader import load_index_file
            idx = load_index_file(Path("docs/dispatch"))
            e = idx.get(it.id) or {}
            print(e.get("path",""))
            break
except Exception:
    pass
PY
)"; then
  CARD_PATH=""
fi
# 直接用 resolve_card 函数（lib/card-resolve.sh 提供的 resolve_card）
if [[ -z "$CARD_PATH" ]]; then
  # shellcheck source=lib/card-resolve.sh
  source "$SCRIPT_DIR/lib/card-resolve.sh" 2>/dev/null || true
  if declare -f resolve_card >/dev/null 2>&1; then
    CARD_PATH="$(resolve_card "$CARD_ID" 2>/dev/null || true)"
  fi
fi
if [[ -z "$CARD_PATH" || ! -f "$CARD_PATH" ]]; then
  echo "[ERROR] spot-check: 找不到卡 ${CARD_ID} 的文件路径" >&2
  exit 2
fi
STEM="$(basename "$CARD_PATH" .md)"
BRANCH="codex/${STEM}"
HAS_BRANCH=false
if git rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
  HAS_BRANCH=true
fi

FAIL=0

echo "== spot-check ${CARD_ID}（环节②抽验 · 20% 批次） =="
echo "   card=${CARD_PATH} branch=${BRANCH} has_branch=${HAS_BRANCH}"

# 1) 测试真实性（evidence log）
#    无测试声明 → 放行；有声明但缺日志/失败 → 抽验不通过
LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$LOG_DIR" ]]; then
  CFG="${CCC_CONFIG_ENV:-/Users/fan/program/CCC/server/config/config.env}"
  if [[ -f "$CFG" ]]; then
    LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs 2>/dev/null || true)"
  fi
fi
if [[ -z "$LOG_DIR" ]]; then LOG_DIR="$HOME/.ccc/logs/exec"; fi
EVIDENCE_CAND="${LOG_DIR}/${CARD_ID}.test-evidence.log"
EVIDENCE_CAND_LC="${LOG_DIR}/$(echo "$CARD_ID" | tr '[:upper:]' '[:lower:]').test-evidence.log"
EVIDENCE=""
for cand in "$EVIDENCE_CAND" "$EVIDENCE_CAND_LC"; do
  if [[ -f "$cand" ]]; then EVIDENCE="$cand"; break; fi
done
HAS_TEST="$(python3 - "$CARD_PATH" <<'PY' 2>/dev/null
import sys
from pathlib import Path
t=Path(sys.argv[1]).read_text(encoding="utf-8")
in_gate=False
for ln in t.splitlines():
    s=ln.strip()
    if s.startswith("## 门禁"):
        in_gate=True; continue
    if in_gate:
        if s.startswith("## ") or s.startswith("---"): break
        if s.startswith("测试") and (":" in s or "：" in s):
            cmd=s.split(":",1)[1].strip() if ":" in s else s.split("：",1)[1].strip()
            cmd=cmd.strip(chr(96)).strip()
            if cmd:
                print("yes"); sys.exit(0)
print("no")
PY
)"
if [[ "$HAS_TEST" == "yes" ]]; then
  if [[ -z "$EVIDENCE" ]]; then
    echo "[FAIL] spot-check 1/4 测试真实性：缺 evidence log（${EVIDENCE_CAND}）→ 打回（证据缺失）" >&2
    FAIL=1
  elif grep -q "no_test_declared" "$EVIDENCE" 2>/dev/null; then
    echo "[OK] spot-check 1/4 测试真实性：no_test_declared → 通过"
  elif ! grep -q "exit_code=0" "$EVIDENCE" 2>/dev/null; then
    RC="$(grep -oE 'exit_code=[0-9]+' "$EVIDENCE" 2>/dev/null | tail -1 || echo "exit_code=?")"
    echo "[FAIL] spot-check 1/4 测试真实性：${RC}（${EVIDENCE}）→ 打回" >&2
    tail -10 "$EVIDENCE" 2>/dev/null | sed 's/^/  | /' >&2 || true
    FAIL=1
  else
    echo "[OK] spot-check 1/4 测试真实性：exit_code=0 → 通过"
  fi
else
  echo "[OK] spot-check 1/4 测试真实性：卡无测试声明 → 跳过"
fi

# 2) 范围复核
if $HAS_BRANCH; then
  if bash scripts/scope-check.sh "$CARD_PATH" "$BRANCH" 2>&1 | sed 's/^/  | /'; then
    echo "[OK] spot-check 2/4 范围：通过"
  else
    echo "[FAIL] spot-check 2/4 范围：未通过 → 打回" >&2
    FAIL=1
  fi
else
  echo "[SKIP] spot-check 2/4 范围：无分支（close-only），跳过"
fi

# 3) git 真实性复核
if $HAS_BRANCH; then
  if bash scripts/git-truth-check.sh "$CARD_PATH" "$BRANCH" 2>&1 | sed 's/^/  | /'; then
    echo "[OK] spot-check 3/4 git 真实性：通过"
  else
    echo "[FAIL] spot-check 3/4 git 真实性：未通过 → 打回" >&2
    FAIL=1
  fi
else
  echo "[SKIP] spot-check 3/4 git 真实性：无分支，跳过"
fi

# 4) ledger↔信封一致性
LEDGER_OK=false
if "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.audit_ledger import has_action, _machine_audit_pass_ids
if not _machine_audit_pass_ids():
    sys.exit(0)
sys.exit(0 if has_action('machine_audit_pass', sys.argv[1]) else 1)
" "$CARD_ID" 2>/dev/null; then
  LEDGER_OK=true
fi
ENVELOPE_OK=false
if $HAS_BRANCH; then
  if git show "origin/${BRANCH}:${CARD_PATH}" 2>/dev/null | "$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '.')
from server.board.models import machine_audit_passed_text
sys.exit(0 if machine_audit_passed_text(sys.stdin.read()) else 1)
" 2>/dev/null; then
    ENVELOPE_OK=true
  fi
else
  # 无分支时信封不可得，ledger 为主
  ENVELOPE_OK=true
fi
if $LEDGER_OK && $ENVELOPE_OK; then
  echo "[OK] spot-check 4/4 ledger↔信封：ledger 有记录且信封机审通过 → 通过"
else
  if ! $LEDGER_OK; then
    echo "[FAIL] spot-check 4/4 ledger：缺 machine_audit_pass（${CARD_ID}）→ 打回" >&2
    FAIL=1
  fi
  if ! $ENVELOPE_OK; then
    echo "[FAIL] spot-check 4/4 信封：分支信封无机审通过 → 打回" >&2
    FAIL=1
  fi
fi

if [[ "$FAIL" != "0" ]]; then
  echo "[FAIL] spot-check ${CARD_ID} 抽验结论：不通过 → 打回（按四问仅选唯一最佳动作：打回重做）" >&2
  exit 1
fi
echo "[OK] spot-check ${CARD_ID} 抽验结论：通过（环节②抽验完成）"
exit 0
