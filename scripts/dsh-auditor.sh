#!/bin/bash
# ── scripts/dsh-auditor.sh ──
# DSH 机审执行体（S4 · CCC×DSH 整合；2026-08-23 指令A 入编改造）
# 心智来自预设 ~/.dsh/.agent-presets/dsh-auditor（--patch 直挂 headless，v4 指令自含于预设），
# 本 wrapper 只传「卡指针 + 运行参数 + 授权声明」。
#
# 用法：
#   scripts/dsh-auditor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]
#
# 新契约（2026-09-04）：审计目标为主仓卡（只读），不依赖业务 worktree；
# verdict 写入 $EXECUTOR_LOG_DIR/<work_id>-audit-verdict.md。
#   通过 → 工件写整行「机审：通过」，退出 0
#   不通过 → 工件写整行「机审：不通过（原因）」，退出 2
# 前置：2017 已配 OPENCODE_GO_API_KEY；inject_hint=false（Engine 不注入，v4 预设自含）。

set -euo pipefail
# P1-d/rebuild-phase2 + P0-1：密钥单源 + 三态预检（非 0 一律阻断，保留真实退出码）
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"
# shellcheck source=scripts/dsh-key.sh
source "$_SELF/dsh-key.sh" 2>/dev/null || true
_KC_RC=0
"$_SELF/dsh-key-check.sh" --quiet || _KC_RC=$?
if [[ $_KC_RC -ne 0 ]]; then
  echo "[FATAL] DSH 网关预检未通过（code=$_KC_RC）—— 见 ledger dsh_quota_alert/日志；本次不执行" >&2
  exit "$_KC_RC"
fi

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-验收席}"
BIZ_WORKTREE="${5:-}"
# build_command uses a sentinel to preserve empty optional argv positions.
[[ "$WORKTREE" == "__CCC_EMPTY__" ]] && WORKTREE=""
[[ "$BIZ_WORKTREE" == "__CCC_EMPTY__" ]] && BIZ_WORKTREE=""

# R-2026-08-23 P0-2：launchd 下 Engine PATH 极简，裸 `dsh` 会 127（同 dsh-executor.sh）。
# P0-2b 补充：/usr/local/bin（node，dsh 运行时入口）一并兜底。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-auditor] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }
command -v node >/dev/null 2>&1 || { echo "[dsh-auditor] ERROR: node 不在 PATH（DSH 运行时需要，已尝试 /usr/local/bin）" >&2; exit 127; }

# R-2026-08-23 P0-3：就地修复需在 worktree commit/push，git 元数据在主仓 .git
# （cwd 之外）→ 默认 workspace-write 沙箱拒绝且 headless 无审批通道。
export DSH_PERMISSION_MODE="${DSH_PERMISSION_MODE:-danger-full-access}"

# 预设心智（入编）：缺失即明确失败
PRESET="$HOME/.dsh/.agent-presets/dsh-auditor/agent.cordis.yml"
[ -f "$PRESET" ] || { echo "[dsh-auditor] ERROR: 机审席预设缺失: $PRESET" >&2; exit 3; }

# 从预设提取 persona → 生成 headless system-prompt 槽位 overlay（--patch 槽位语义，见 executor）
OVL_DIR="$(mktemp -d)"
OVERLAY="$OVL_DIR/overlay.yml"
python3 - "$PRESET" "$OVERLAY" <<'PY'
import sys, yaml
rows = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
persona = next(r["config"]["text"] for r in rows if r.get("id") == "persona")
yaml.safe_dump(
    [{"id": "system-prompt", "config": {"persona": persona}}],
    open(sys.argv[2], "w", encoding="utf-8"),
    allow_unicode=True,
)
PY

# 新机审契约（2026-09-04）：审计目标是主仓卡（只读），业务 worktree 退出机审链路。
# WORKTREE/BIZ_WORKTREE 仅为兼容旧调用保留，空值不再失败；cwd 固定 CCC 主仓。
REPO_ROOT="$(cd "$_SELF/.." && pwd -P)"
cd "$REPO_ROOT"
AUDIT_CARD="$CARD_PATH"
LOG_DIR="${EXECUTOR_LOG_DIR:-${LOG_DIR:-$HOME/.ccc/logs/exec}}"
mkdir -p "$LOG_DIR"
VERDICT_FILE="$LOG_DIR/${WORK_ID}-audit-verdict.md"
TMP_OUTPUT="$(mktemp)"
trap 'rm -f "$OVERLAY" "$TMP_OUTPUT"' EXIT

echo "[dsh-auditor] 审查对象=主仓卡（只读）: $AUDIT_CARD" >&2

# 机械门禁仍保留，但只读取主仓卡；失败必须产出 REJECT verdict 工件。
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
    echo "[dsh-auditor] 机械门禁不通过，已写 verdict: $VERDICT_FILE" >&2
    exit 2
  elif [ "${MG_RC:-0}" != "0" ]; then
    echo "[dsh-auditor] 机械门禁异常" >&2
    exit 3
  fi
  unset MG_RC
fi

# 主仓卡作为唯一输入，禁止 DSH 会话写入任何卡文件。

# P0-1b 测试真实性机械截获（2026-08-23）：在 DSH 之外独立跑卡门禁测试，失败硬打回不跑机审。
# 日志落 $EXECUTOR_LOG_DIR/<work_id>.test-evidence.log（与 Engine EXECUTOR_LOG_DIR 同源）。
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
_TE_WORKDIR="$(pwd)"
# 仅当卡文件可读且 workdir 存在时才截获；无测试声明（no_test_declared）视为无可验放行
if [[ -f "$AUDIT_CARD" && -d "$_TE_WORKDIR" ]]; then
  if bash "$_CCC_ROOT/scripts/test-evidence.sh" "$AUDIT_CARD" "$_TE_WORKDIR" "$_TE_EVIDENCE_LOG"; then
    : # 测试通过或无声明 → 放行进 DSH 机审
  else
    _TE_RC=$?
    echo "[dsh-auditor] 机械门禁：卡声明测试真实失败（exit=${_TE_RC}，证据 log=${_TE_EVIDENCE_LOG}）→ 机审打回（不跑 DSH）" >&2
    printf '机审：不通过（测试真实失败：见 %s）\n' "$_TE_EVIDENCE_LOG" > "$VERDICT_FILE"
    exit 2
  fi
fi

PROMPT="任务卡（主仓只读）：${AUDIT_CARD}（work ${WORK_ID}，验收席角色：${ROLE}）已回写，待机审。
按你的机审席心智执行 v4 对抗式审查（范围核对→找茬→severity 三级→分流→维护区核对）。
主仓卡是唯一输入；禁止写入任何卡文件、禁止修改业务 worktree。
审计结束必须将整行‘机审：通过’或‘机审：不通过（原因）’写入 ${VERDICT_FILE}，不得只输出到 stdout。
工作目录：$(pwd)"

set +e
dsh --profile headless --patch "$OVERLAY" "$PROMPT" > "$TMP_OUTPUT" 2>&1
rc=$?
set -e
cat "$TMP_OUTPUT"
if [ ! -s "$VERDICT_FILE" ]; then
  if grep -Eq '^机审：通过([[:space:]]|$)' "$TMP_OUTPUT"; then
    printf '机审：通过\n' > "$VERDICT_FILE"
  elif grep -Eq '^机审：不通过' "$TMP_OUTPUT"; then
    grep -E '^机审：不通过' "$TMP_OUTPUT" | tail -1 > "$VERDICT_FILE"
  fi
fi
if [ "$rc" -eq 2 ] && [ ! -s "$VERDICT_FILE" ]; then
  printf '机审：不通过（auditor exit 2，未产出结论）\n' > "$VERDICT_FILE"
fi
exit "$rc"
