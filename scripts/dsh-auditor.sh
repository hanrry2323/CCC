#!/bin/bash
# ── scripts/dsh-auditor.sh ──
# DSH 机审执行体（S4 · CCC×DSH 整合）
# 用 `dsh --profile headless` 做验收/机审（原则性 Code Review + 机械门禁已由引擎裁决）。
# 替代 engine 的 `claude -p "你是 2017 机审席..."`。
#
# 用法：
#   scripts/dsh-auditor.sh <card_path> <work_id> <worktree> [role]
#
# 输出契约（engine 机审收集用）：
#   通过 → 写「## 机审区」+「机审：通过」到 worktree 卡文件，退出 0
#   不通过 → 输出「机审：不通过（原因）」，退出非 0
# 前置：2017 已配 OPENCODE_GO_API_KEY；inject_hint=false（Engine 不注入，v4 指令自含）。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"

# R-2026-08-23 P0-2：launchd 下 Engine PATH 极简，裸 `dsh` 会 127（同 dsh-executor.sh）。
case ":$PATH:" in
  *":$HOME/.npm-global/bin:"*) ;;
  *) export PATH="$HOME/.npm-global/bin:$PATH" ;;
esac
command -v dsh >/dev/null 2>&1 || { echo "[dsh-auditor] ERROR: dsh 不在 PATH（已尝试 \$HOME/.npm-global/bin）" >&2; exit 127; }

# R-2026-08-23 P0-3：就地修复需在 worktree commit/push，git 元数据在主仓 .git
# （cwd 之外）→ 默认 workspace-write 沙箱拒绝且 headless 无审批通道。
export DSH_PERMISSION_MODE="${DSH_PERMISSION_MODE:-danger-full-access}"

if [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
fi

PROMPT="你是 2017 机审席（DSH）。任务卡 ${CARD_PATH}（work ${WORK_ID}）已回写，你以验收席身份独立审查。

【审查原则】
1. 机械门禁（编译/测试/lint/范围）已由引擎裁决，你不再重复检查。
2. 你的职责是原则性 Code Review：代码质量、架构合理性、边界安全、人工批注落实。
3. 发现可修问题（命名/注释/小重构/补充测试）→ 在 worktree ${WORKTREE} 就地修复并 commit+push，修完直接通过。
4. 只有原则性红线问题（业务意图违背/系统性越界/安全漏洞）才打回。

【机审 v4 指令（必须遵循）】
1. 对抗式找茬：假设有 P0/P1，找具体可复现问题；0 发现须给风险论证。
2. 三级判定 severity：影响面/改动深度/红线邻近各 1-3 分，合计 3-4=轻 5-7=中 8-9=重，任一维度高→强制重。
3. 可快速修复的轻问题 → 就地修复并 commit+push（不打回）；原则性红线 → 打回。
4. 结论行必须输出 severity 标记（severity：轻/中/重）并明示结论（通过 / 不通过，不通过须附原因）。

【审查步骤】
1. Read 卡文件，了解任务目标和验收标准。
2. 检查 git log/diff，确认改动在卡声明的范围内。
3. 审查代码质量和架构。
4. 可修问题就地修复；不可修的原则性问题输出「机审：不通过（原因）」并以非零退出。

【通过标准】
通过 → 把「## 机审区」+「机审：通过」+ 审查摘要 写进 worktree 卡文件（${CARD_PATH}）。
授权声明：本次机审任务已显式授权读写任务卡文件与在 worktree 内就地修复 commit/push；headless 只读红线不适用于本授权范围内动作。
禁止改动无关文件、禁止 ## 验收区、禁止已关闭。
工作目录：$(pwd)"

dsh --profile headless "$PROMPT"
