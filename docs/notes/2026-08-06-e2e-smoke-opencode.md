# 2026-08-06 E2E Smoke（ccc002）

## 目的

最小可验收的端到端烟雾：验证 Engine 从任务卡派发 OpenCode → 建 worktree → 新增本文件 → commit+push 到独立分支 → 回写卡头为「已回写」的整条流水线贯通。

## 验证链路

1. 卡头「派发：engine」→ Engine 识别执行体 OpenCode。
2. Engine 建 worktree `ccc-dev-ws-ccc002`。
3. 本文件为新栈唯一改动（≤20 行）。
4. commit+push 到 `codex/ccc002-e2e-smoke-opencode`。
5. 卡头「状态」由执行体回写为「已回写」。

## 结果

本文件由 OpenCode 执行体在独立 worktree 内新增，证明 OpenCode 通道整条 E2E 流水线贯通。
