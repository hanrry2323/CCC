#!/bin/bash
# ── scripts/dsh-executor.sh ──
# DSH 开发执行体包装（S3 · CCC×DSH 整合；2026-08-23 指令A 入编改造）
# 心智来自预设 ~/.dsh/.agent-presets/dsh-executor（--patch 直挂 headless），
# 本 wrapper 只传「卡指针 + 运行参数 + 授权声明」——预设管心智，卡管任务。
#
# 用法：
#   scripts/dsh-executor.sh <card_path> <work_id> <worktree> [role] [biz_worktree]
#
# biz_worktree（P1-b 2026-08-23）：业务仓型任务每卡独立 worktree；非业务仓任务传空，
# 此时忽略。业务仓型任务 cwd 切 biz_worktree（业务仓内改动），card_path 仍为绝对路径。
#
# 退出码：0=DSH 完成（含自报成功/打回）；非0=执行失败。engine 按退出码+输出判定。
# 前置：2017 已配 OPENCODE_GO_API_KEY（com.ccc.engine.plist env）+ DSH 0.1.1-rc.2。

set -euo pipefail
# P1-d/rebuild-phase2 + P0-1：密钥单源 + 三态预检（非 0 一律阻断，保留真实退出码）
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/dsh-key.sh
source "$_SELF/dsh-key.sh" 2>/dev/null || true
_KC_RC=0
"$_SELF/dsh-key-check.sh" --quiet || _KC_RC=$?
if [[ $_KC_RC -ne 0 ]]; then
  echo "[FATAL] DSH 网关预检未通过（code=$_KC_RC）见 ledger dsh_quota_alert/日志；本次不执行" >&2
  exit "$_KC_RC"
fi

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-开发执行体}"
BIZ_WORKTREE="${5:-}"

# R-2026-08-23 P0-2：launchd 下 Engine PATH 极简（/usr/bin:/bin:/usr/sbin:/sbin），
# 裸 `dsh` 会 127。兜底补 npm 全局 bin（dsh 本体）+ /usr/local/bin（node，dsh 运行时入口），
# 仍找不到就明确报错（不静默）。P0-2b 补充：仅补 dsh 目录不够，node 缺失同样 rc=127。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*:*":/usr/local/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:/usr/local/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-executor] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }
command -v node >/dev/null 2>&1 || { echo "[dsh-executor] ERROR: node 不在 PATH（DSH 运行时需要，已尝试 /usr/local/bin）" >&2; exit 127; }

# R-2026-08-23 P0-3：worktree 的 git 元数据在主仓 .git（cwd 之外），默认
# workspace-write 沙箱会拒绝 commit 且 headless 无审批通道 → 执行体无法收口。
# 与生产 harness 同款语义：danger-full-access + approval never。
export DSH_PERMISSION_MODE="${DSH_PERMISSION_MODE:-danger-full-access}"

# 预设心智（入编）：缺失即明确失败，不静默降级为无心智裸跑
PRESET="$HOME/.dsh/.agent-presets/dsh-executor/agent.cordis.yml"
[ -f "$PRESET" ] || { echo "[dsh-executor] ERROR: 执行体预设缺失: $PRESET" >&2; exit 3; }

# 从预设提取 persona → 生成 headless system-prompt 槽位 overlay
# （--patch 的 id 是组合树槽位；预设文件本身是插件行列表，需派生而非直挂）
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

# 切工作目录：业务仓型任务优先 biz_worktree（业务仓内改动），否则 worktree（含卡副本）
# P1-b 2026-08-23：biz_worktree 存在时业务仓为唯一工作区，cwd 必须落在其中。
if [ -n "$BIZ_WORKTREE" ] && [ -d "$BIZ_WORKTREE" ]; then
  cd "$BIZ_WORKTREE"
  WORKDIR_LABEL="biz_worktree"
elif [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
  WORKDIR_LABEL="worktree"
else
  WORKDIR_LABEL="cwd"
fi

PROMPT="任务卡：${CARD_PATH}（work ${WORK_ID}，角色：${ROLE}）。
按你的开发执行体心智执行本卡全流程（读卡→白名单实现→自测→commit+push→回写已回写与维护区四问→停手）。
授权声明：本次运行授权在 ${WORKDIR_LABEL} $(pwd) 内读写卡白名单文件并执行 git add/commit/push（限卡白名单范围）。
工作目录：$(pwd)"

# ccc073（2026-08-24）：业务仓型任务 cwd 落在 biz_worktree，卡文件不在眼前——
# xy059 首轮实证执行体普遍漏做文档仓侧卡回写。BIZ_WORKTREE 非空时 PROMPT 追加
# 双仓语义提示；WORKTREE 缺失时文案引用空路径会产生误导，故同样不加。
# 仅增补提示文案，其余零逻辑变化。
if [ -n "$BIZ_WORKTREE" ] && [ -n "$WORKTREE" ]; then
  PROMPT+="
双仓提示：本卡文件位于文档仓分支副本 ${WORKTREE}/ 下（相对路径 ${CARD_PATH#/Users/fan/program/CCC/}）。业务改动在当前目录实施；卡文件的状态回写、回写区与维护区四问必须在文档仓 worktree 的卡副本上完成并 commit+push 到同一分支；主仓 ${CARD_PATH} 只读勿动。"
fi

# 后台执行 + wait 传播退出码（R1）；engine 侧另有全局超时
dsh --profile headless --patch "$OVERLAY" "$PROMPT" &
PID=$!
DSH_RC=0
wait "$PID" || DSH_RC=$?
rm -f "$OVERLAY"

# P0-1b 测试真实性机械截获（2026-08-23）：DSH 之外独立跑卡门禁测试并落证据日志。
# 日志落 $EXECUTOR_LOG_DIR/<work_id>.test-evidence.log（与 Engine 同源，不经 DSH 加工）。
_TE_EXEC_LOG_DIR="${EXECUTOR_LOG_DIR:-}"
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_CFG="${CCC_CONFIG_ENV:-/Users/fan/program/CCC/server/config/config.env}"
  if [[ -f "$_TE_CFG" ]]; then
    _TE_EXEC_LOG_DIR="$(grep -E '^\s*EXECUTOR_LOG_DIR\s*=' "$_TE_CFG" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\"' | tr -d "'" | xargs 2>/dev/null || true)"
  fi
fi
if [[ -z "$_TE_EXEC_LOG_DIR" ]]; then
  _TE_EXEC_LOG_DIR="$HOME/.ccc/logs/exec"
fi
_TE_EVIDENCE_LOG="${_TE_EXEC_LOG_DIR}/${WORK_ID}.test-evidence.log"
# 证据 workdir：优先 biz_worktree，其次 worktree，其次当前目录（已 cd 过）
_TE_EVIDENCE_WORKDIR=""
if [[ -n "${BIZ_WORKTREE:-}" && -d "$BIZ_WORKTREE" ]]; then
  _TE_EVIDENCE_WORKDIR="$BIZ_WORKTREE"
elif [[ -n "${WORKTREE:-}" && -d "$WORKTREE" ]]; then
  _TE_EVIDENCE_WORKDIR="$WORKTREE"
else
  _TE_EVIDENCE_WORKDIR="$(pwd)"
fi
if [[ -f "$CARD_PATH" && -d "$_TE_EVIDENCE_WORKDIR" ]]; then
  bash /Users/fan/program/CCC/scripts/test-evidence.sh "$CARD_PATH" "$_TE_EVIDENCE_WORKDIR" "$_TE_EVIDENCE_LOG" || true
  echo "[dsh-executor] 测试证据已截获 → ${_TE_EVIDENCE_LOG}" >&2
fi

echo "[dsh-executor] work=${WORK_ID} 执行结束 rc=${DSH_RC}"
exit "$DSH_RC"
