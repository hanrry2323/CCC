#!/bin/bash
# ── scripts/dsh-auditor.sh ──
# DSH 机审执行体（S4 · CCC×DSH 整合；2026-08-23 指令A 入编改造）
# 心智来自预设 ~/.dsh/.agent-presets/dsh-auditor（--patch 直挂 headless，v4 指令自含于预设），
# 本 wrapper 只传「卡指针 + 运行参数 + 授权声明」。
#
# 用法：
#   scripts/dsh-auditor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]
#
# biz_worktree（P1-b 2026-08-23）：业务仓型任务每卡独立 worktree；机审复用开发产物，
# 优先切 biz_worktree 核验（卡文件 + 业务改动都在其中）；非业务仓任务传空，忽略。
#
# 输出契约（engine 机审收集用）：
#   通过 → 写「## 机审区」+「机审：通过」到 worktree 卡文件，退出 0
#   不通过 → 输出「机审：不通过（原因）」，退出非 0
# 前置：2017 已配 OPENCODE_GO_API_KEY；inject_hint=false（Engine 不注入，v4 预设自含）。

set -euo pipefail
# P1-d/rebuild-phase2 + P0-1：密钥单源 + 三态预检（非 0 一律阻断，保留真实退出码）
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

# 切工作目录：业务仓型任务优先 biz_worktree（复用开发产物），否则 worktree（含卡副本）
# P1-b 2026-08-23：机审在开发产物所在仓核验，cwd 必须落在其中。
if [ -n "$BIZ_WORKTREE" ] && [ -d "$BIZ_WORKTREE" ]; then
  cd "$BIZ_WORKTREE"
elif [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
fi

# R-2026-08-23 P1-b 修复卡（机审维护区假断言）：机械前置门禁——维护区四问未完成/占位
# 直接打回，不跑 DSH（docgate verify_maintenance 与 approve-merge 完成钩子同一实现，
# 杜绝 DSH 对占位维护区误判「通过」。红线：门禁不削弱，仅前置化）。
# P0-1b-fix（2026-08-24 tst003 误打回归因）：机审对象必须是被审分支的卡副本，不能回退主仓。
# docs 类卡 biz_worktree 不含卡文件；回写与引擎信封都落在 WORKTREE 分支副本。
# A4 加固（2026-09-03）：WORKTREE 缺失/卡副本缺失直接失败，禁止主仓 fallback，防止污染 main。
if [ -z "$WORKTREE" ] || [ ! -d "$WORKTREE" ]; then
  echo "[dsh-auditor] 机审失败：worktree 缺失，无法审计: ${WORKTREE:-<空>}" >&2
  exit 64
fi
REL_CARD="${CARD_PATH#/Users/fan/program/CCC/}"
if [ "$REL_CARD" = "$CARD_PATH" ] || [ ! -f "$WORKTREE/$REL_CARD" ]; then
  echo "[dsh-auditor] 机审失败：worktree 卡副本缺失，无法审计: $WORKTREE/$REL_CARD" >&2
  exit 64
fi
AUDIT_CARD="$WORKTREE/$REL_CARD"
echo "[dsh-auditor] 审查对象=worktree 分支副本: $AUDIT_CARD" >&2

# R-2026-08-23 P1-b 修复卡（机审维护区假断言）：机械前置门禁——维护区四问未完成/占位
# 直接打回，不跑 DSH（docgate verify_maintenance 与 approve-merge 完成钩子同一实现，
# 杜绝 DSH 对占位维护区误判「通过」。红线：门禁不削弱，仅前置化）。
if [ -n "$AUDIT_CARD" ] && [ -f "$AUDIT_CARD" ]; then
  MG_PROBLEMS="$(python3 - "$AUDIT_CARD" "$(pwd)" <<'PY'
import sys
sys.path.insert(0, "/Users/fan/program/CCC")
try:
    from server.board.docgate import verify_maintenance
    ok, problems = verify_maintenance(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 2)
except Exception as exc:  # 机械门禁自身异常：不静默放行，打回由 DSH 兜底
    print(f"维护区机械校验异常: {exc}")
    sys.exit(3)
PY
)" || MG_RC=$?
  if [ "${MG_RC:-0}" = "2" ]; then
    echo "[dsh-auditor] 机械门禁：维护区未完成 → 机审打回（不跑 DSH）" >&2
    echo "机审：不通过（维护区未完成）" >&2
    rm -f "$OVERLAY"
    exit 2
  fi
  unset MG_RC
fi

# P0-1b 测试真实性机械截获（2026-08-23）：在 DSH 之外独立跑卡门禁测试，失败硬打回不跑机审。
# 日志落 $EXECUTOR_LOG_DIR/<work_id>.test-evidence.log（与 Engine EXECUTOR_LOG_DIR 同源）。
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG="${CCC_CONFIG_ENV:-/Users/fan/program/CCC/server/config/config.env}"
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
  if bash /Users/fan/program/CCC/scripts/test-evidence.sh "$AUDIT_CARD" "$_TE_WORKDIR" "$_TE_EVIDENCE_LOG"; then
    : # 测试通过或无声明 → 放行进 DSH 机审
  else
    _TE_RC=$?
    echo "[dsh-auditor] 机械门禁：卡声明测试真实失败（exit=${_TE_RC}，证据 log=${_TE_EVIDENCE_LOG}）→ 机审打回（不跑 DSH）" >&2
    echo "机审：不通过（测试真实失败：见 ${_TE_EVIDENCE_LOG}）" >&2
    rm -f "$OVERLAY"
    exit 2
  fi
fi

PROMPT="任务卡（被审分支副本）：${AUDIT_CARD}（work ${WORK_ID}，验收席角色：${ROLE}）已回写，待机审。
注意：主仓 ${CARD_PATH} 是 main 版占位卡（未含回写），勿据其下结论、勿写入。
按你的机审席心智执行 v4 对抗式审查（范围核对→找茬→severity 三级→分流→维护区核对→写机审区）。
授权声明：本次运行授权读写任务卡文件、在 worktree $(pwd) 内就地修复并 git add/commit/push。
工作目录：$(pwd)"

dsh --profile headless --patch "$OVERLAY" "$PROMPT"
rc=$?
rm -f "$OVERLAY"
exit $rc
