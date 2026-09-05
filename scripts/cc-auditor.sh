#!/bin/bash
# ── scripts/cc-auditor.sh ──
# 后段验收席执行体（Claude Code CLI wrapper · 2026-09-04 重构批E）
# 心智：v4 对抗式审查（范围内核→找茬→severity 三级→分流→维护区核对）；
# 自称「后段验收席（Claude Code CLI）」；主仓卡只读，禁止写卡/写仓。
#
# 用法（argv 签名与 dsh-auditor.sh 完全一致，保持注册表参数模板不变）：
#   scripts/cc-auditor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]
#
# 契约 v2（与 dsh-auditor 现行契约对齐）：
#   - 审计输入 = 主仓卡全文 + $EXECUTOR_LOG_DIR/<work_id>-ccc-result.md 结果工件；
#   - 输出 = verdict 写 $EXECUTOR_LOG_DIR/<work_id>-audit-verdict.md，
#     含整行「机审：通过」或「机审：不通过（原因）」+ 证据四段；
#   - exit 0 = verdict 已产出；exit 2 = 机械前置不通过（同时写「机审：不通过（…）」工件）；
#     其他 = 基础设施失败。
# 环境：ANTHROPIC_BASE_URL/ANTHROPIC_MODEL/ANTHROPIC_API_KEY 指向本机 3456 中转（Code）；
# EXECUTOR_LOG_DIR 继承（phase2 注入），未设则回落 config.env。

set -uo pipefail
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-验收席}"
BIZ_WORKTREE="${5:-}"
# build_command 用哨兵保留空可选位置参数（与 dsh-auditor 同口径）。
[[ "$WORKTREE" == "__CCC_EMPTY__" ]] && WORKTREE=""
[[ "$BIZ_WORKTREE" == "__CCC_EMPTY__" ]] && BIZ_WORKTREE=""

# launchd 下 PATH 极简，claude（npm 全局）与 node 运行时需兜底。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
CLAUDE_BIN="${CCC_BRAIN_CLAUDE_BIN:-claude}"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || { echo "[cc-auditor] ERROR: claude CLI 不在 PATH（已尝试 \$HOME/.npm-global/bin 与 \$CCC_BRAIN_CLAUDE_BIN）" >&2; exit 127; }

# ── 环境：Claude CLI 出口（3456 中转不校验 key；2026-09-03 实证）──
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:3456}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-Code}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-dummy-placeholder}"

# 主仓只读 cwd；审计目标是主仓卡，机械测试证据在业务 worktree 执行。
REPO_ROOT="$(cd "$_SELF/.." && pwd -P)"
cd "$REPO_ROOT"
AUDIT_CARD="$CARD_PATH"
TEST_WORKDIR="${BIZ_WORKTREE:-${WORKTREE:-$REPO_ROOT}}"
if [[ ! -d "$TEST_WORKDIR" ]]; then
  echo "[cc-auditor] WARN: test_workdir 不存在，回落主仓: ${TEST_WORKDIR} -> ${REPO_ROOT}" >&2
  TEST_WORKDIR="$REPO_ROOT"
fi
LOG_DIR="${EXECUTOR_LOG_DIR:-${LOG_DIR:-$HOME/.ccc/logs/exec}}"
mkdir -p "$LOG_DIR"
VERDICT_FILE="$LOG_DIR/${WORK_ID}-audit-verdict.md"
RESULT_FILE="$LOG_DIR/${WORK_ID}-ccc-result.md"
TMP_OUTPUT="$(mktemp)"
trap 'rm -f "$TMP_OUTPUT"' EXIT

echo "[cc-auditor] 审查对象=主仓卡（只读）: ${AUDIT_CARD}（work ${WORK_ID}，角色 ${ROLE}）" >&2
echo "[cc-auditor] test_workdir: ${TEST_WORKDIR}" >&2
echo "[cc-auditor] verdict 工件: $VERDICT_FILE" >&2

# ── 机械门禁一：维护区四问（docgate.verify_maintenance）──
# 失败必须产出 REJECT verdict 工件，exit 2（与 dsh-auditor 同口径）。
if [ -f "$AUDIT_CARD" ]; then
  MG_PROBLEMS="$(python3 - "$AUDIT_CARD" "$(pwd)" <<'PY'
import sys
sys.path.insert(0, "$_CCC_ROOT")
try:
    from server.board.docgate import verify_maintenance
    ok, problems = verify_maintenance(sys.argv[1], sys.argv[2])
    if not ok:
        print("；".join(problems) or "维护区未完成")
    sys.exit(0 if ok else 2)
except Exception as exc:
    print(f"维护区机械校验异常: {exc}")
    sys.exit(3)
PY
)" || MG_RC=$?
  if [ "${MG_RC:-0}" = "2" ]; then
    printf '机审：不通过（维护区未完成：%s）\n' "${MG_PROBLEMS:-未知原因}" > "$VERDICT_FILE"
    echo "[cc-auditor] 机械门禁（维护区）不通过，已写 verdict: $VERDICT_FILE" >&2
    exit 2
  elif [ "${MG_RC:-0}" != "0" ]; then
    echo "[cc-auditor] 机械门禁（维护区）异常" >&2
    exit 3
  fi
  unset MG_RC
fi

# ── 机械门禁二：测试真实性截获（test-evidence.sh）──
# 与 dsh-auditor 同源：卡声明测试真实失败 → 硬打回，不跑机审。
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG="${CCC_CONFIG_ENV:-$_CCC_ROOT/server/config/config.env}"
  if [[ -f "$_TE_CFG" ]]; then
    _TE_EXEC_LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$_TE_CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'" | xargs 2>/dev/null || true)"
  fi
fi
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_EXEC_LOG_DIR="$HOME/.ccc/logs/exec"
fi
_TE_EVIDENCE_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}.test-evidence.log"
if [[ -f "$AUDIT_CARD" && -d "$TEST_WORKDIR" ]]; then
  if bash "$_CCC_ROOT/scripts/test-evidence.sh" "$AUDIT_CARD" "$TEST_WORKDIR" "$_TE_EVIDENCE_LOG"; then
    : # 测试通过或无声明 → 放行进入机审
  else
    _TE_RC=$?
    echo "[cc-auditor] 机械门禁：卡声明测试真实失败（exit=${_TE_RC}，证据 log=${_TE_EVIDENCE_LOG}）→ 机审打回（不跑 Claude）" >&2
    printf '机审：不通过（测试真实失败：见 %s）\n' "$_TE_EVIDENCE_LOG" > "$VERDICT_FILE"
    exit 2
  fi
fi

# 结果工件缺失 = 机审前置缺失 → 明确失败（不跑 Claude）。
if [[ ! -f "$RESULT_FILE" ]]; then
  echo "[cc-auditor] 前置缺失：执行结果工件不存在 $RESULT_FILE" >&2
  exit 3
fi

# ── Claude CLI 机审（后段验收席）──
# prompt 只给卡路径 + 结果工件路径，由 CLI 自行 Read；verdict 由 CLI Write 到工件。
PROMPT="你是后段验收席（Claude Code CLI）。任务卡（主仓只读）：
${AUDIT_CARD}
执行结果工件：
${RESULT_FILE}
（work ${WORK_ID}，角色：${ROLE}）已回写，待验收。

按 v4 对抗式审查执行：
1. 范围核对：卡目标/红线/验收标准 vs 执行结果工件 vs 主仓卡证据，逐项对账。
2. 对抗式找茬：假设有 P0/P1，找具体可复现问题；0 发现须给风险论证。
3. severity 三级：影响面/改动深度/红线邻近各 1-3 分，合计 3-4=轻 5-7=中 8-9=重；任一维度高→强制重。
4. 分流：可快速修复的轻问题 → 不通过（原因注明可修复项）；原则性红线（业务意图违背/系统性越界）→ 不通过。
5. 维护区核对：维护区四问是否逐项真实回答，证据链是否闭合。

主仓卡是唯一输入；禁止写入任何卡文件、禁止修改主仓仓、禁止运行 Bash/Edit 工具。
审计结束必须用 Write 工具把整行结论写入 ${VERDICT_FILE}：
通过 → 整行『机审：通过』；不通过 → 整行『机审：不通过（原因）』。
再附证据四段：范围核对、风险论证、severity、维护区核对。结论必须落到工件文件，不得只输出到 stdout。
工作目录：$(pwd)"

set +e
"$CLAUDE_BIN" -p "$PROMPT" \
  --output-format text \
  --max-turns "${CC_AUDITOR_MAX_TURNS:-30}" \
  --permission-mode bypassPermissions \
  --allowedTools "Read Write" \
  > "$TMP_OUTPUT" 2>&1
rc=$?
set -e
cat "$TMP_OUTPUT"

# verdict 以工件为准；stdout 仅兜底（CLI 漏写时从 stdout 提取结论行）。
if [ ! -s "$VERDICT_FILE" ]; then
  if grep -Eq '^机审：通过([[:space:]]|$)' "$TMP_OUTPUT"; then
    printf '机审：通过\n' > "$VERDICT_FILE"
  elif grep -Eq '^机审：不通过' "$TMP_OUTPUT"; then
    grep -E '^机审：不通过' "$TMP_OUTPUT" | tail -1 > "$VERDICT_FILE"
  fi
fi

if [ "$rc" -eq 0 ] && [ -s "$VERDICT_FILE" ]; then
  echo "[cc-auditor] verdict 已产出: $VERDICT_FILE" >&2
  exit 0
fi
if [ "$rc" -eq 2 ] && [ ! -s "$VERDICT_FILE" ]; then
  printf '机审：不通过（auditor exit 2，未产出结论）\n' > "$VERDICT_FILE"
fi
echo "[cc-auditor] claude CLI 退出码=${rc}（verdict 工件 ${VERDICT_FILE}）" >&2
exit "$rc"
