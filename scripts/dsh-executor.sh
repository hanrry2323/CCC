#!/bin/bash
# ── scripts/dsh-executor.sh ──
# DSH 开发执行体包装（S3 · CCC×DSH 整合；2026-08-23 指令A 入编改造）
# 心智来自预设 ~/.dsh/.agent-presets/dsh-executor（--patch 直挂 headless），
# 本 wrapper 只传「卡指针 + 运行参数 + 授权声明」——预设管心智，卡管任务。
#
# 用法：
#   scripts/dsh-executor.sh <card_path> <work_id> <worktree> [role]
#
# 退出码：0=DSH 完成（含自报成功/打回）；非0=执行失败。engine 按退出码+输出判定。
# 前置：2017 已配 OPENCODE_GO_API_KEY（com.ccc.engine.plist env）+ DSH 0.1.1-rc.2。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-开发执行体}"

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
OVERLAY="$(mktemp /tmp/dsh-executor-overlay-XXXXXX.yml)"
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

# 若给了 worktree，切进去工作
if [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
fi

PROMPT="任务卡：${CARD_PATH}（work ${WORK_ID}，角色：${ROLE}）。
按你的开发执行体心智执行本卡全流程（读卡→白名单实现→自测→commit+push→回写已回写与维护区四问→停手）。
授权声明：本次运行授权在 worktree $(pwd) 内读写卡白名单文件并执行 git add/commit/push（限卡白名单范围）。
工作目录：$(pwd)"

# 后台执行 + wait 传播退出码（R1）；engine 侧另有全局超时
dsh --profile headless --patch "$OVERLAY" "$PROMPT" &
PID=$!
DSH_RC=0
wait "$PID" || DSH_RC=$?
rm -f "$OVERLAY"

echo "[dsh-executor] work=${WORK_ID} 执行结束 rc=${DSH_RC}"
exit "$DSH_RC"
