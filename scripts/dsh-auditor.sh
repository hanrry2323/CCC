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

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-验收席}"
BIZ_WORKTREE="${5:-}"

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
OVERLAY="$(mktemp /tmp/dsh-auditor-overlay-XXXXXX.yml)"
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

PROMPT="任务卡：${CARD_PATH}（work ${WORK_ID}，验收席角色：${ROLE}）已回写，待机审。
按你的机审席心智执行 v4 对抗式审查（范围核对→找茬→severity 三级→分流→维护区核对→写机审区）。
授权声明：本次运行授权读写任务卡文件、在 worktree $(pwd) 内就地修复并 git add/commit/push。
工作目录：$(pwd)"

dsh --profile headless --patch "$OVERLAY" "$PROMPT"
rc=$?
rm -f "$OVERLAY"
exit $rc
