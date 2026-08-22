#!/bin/bash
# ── scripts/dsh-executor.sh ──
# DSH 开发执行体包装（S3 · CCC×DSH 整合）
# 用 `dsh --profile headless` 执行开发链（读卡→实现→自测→回写），替代 engine spawn OpenCode。
#
# 用法：
#   scripts/dsh-executor.sh <card_path> <work_id> <worktree> [role]
#
# 退出码：0=DSH 完成（含自报成功/打回）；非0=执行失败。
# 说明：DSH headless 一次性执行并打印结果退出；engine 按退出码 + 输出判定。
# 前置：2017 已配 OPENCODE_GO_API_KEY（com.ccc.engine.plist env）+ DSH 0.1.1-rc.2。

set -euo pipefail

CARD_PATH="${1:?缺 card_path}"
WORK_ID="${2:?缺 work_id}"
WORKTREE="${3:-}"
ROLE="${4:-开发执行体}"

# 若给了 worktree，切进去工作
if [ -n "$WORKTREE" ] && [ -d "$WORKTREE" ]; then
  cd "$WORKTREE"
fi

# DSH headless 可能超时（免费模型慢），包一层后台+wait 兜底
PROMPT="你是 CCC 开发执行体（角色：${ROLE}）。
任务卡：${CARD_PATH}（work ${WORK_ID}）。
严格执行：
1. 先 Read 任务卡全文，理解目标/验收标准/红线/范围白名单。
2. 只改任务卡允许范围内的文件（白名单）；禁止改无关文件、禁止碰运行面/密钥。
3. 若卡含「## 人工批注」（老板最高开发指令），必须先按批注修订目标/步骤。
4. 实现后必须自测（跑测试/冒烟/验证命令），确保能跑。
5. 完成后 git add/commit 改动到当前分支（勿直推 main），并在任务卡里更新状态为已回写、填回写区。
6. 禁止自置已关闭、禁止写验收区/机审区（机审由 DSH 审计插件另做）。
7. 重要：卡红线「只改 <文件清单>」指**代码文件**；**任务卡自身的状态回写（状态→已回写、填回写区）是流程动作，不属代码改动**——完成后必须回写卡状态（S8 冒烟 2026-08-22 修正）。
8. 完成时报告：改了什么文件、自测结果、commit hash、卡回写结果。若遇原则性障碍（范围外/缺依赖），明确报告无法完成及原因。
工作目录：$(pwd)"

# 后台执行 + 最长等待（免费模型慢；engine 侧另有全局超时）
# R1 修复（2026-08-22）：DSH 退出码必须传播——engine 收单按退出码判已回写/打回，
# 不能吞掉失败（否则失败卡也被标已回写）。
dsh --profile headless "$PROMPT" &
PID=$!
wait "$PID"
DSH_RC=$?

echo "[dsh-executor] work=${WORK_ID} 执行结束 rc=${DSH_RC}"
exit "$DSH_RC"
