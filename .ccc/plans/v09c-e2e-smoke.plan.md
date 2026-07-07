# v0.9c e2e smoke: 验 v0.8/v0.9a 链路

## 目标
验 CCC 端到端链路可用：plan → opencode exec 跑 phase → 写 report

## Phase
1. **Phase 1**: 跑一个简单 opencode exec, prompt = "回 ok 即可"
   - 验 launcher 完整链路（watchdog → hook → exec → hook）
   - 验 loop/flash 模型调用（v0.9a 修复）
   - 验必杀 + pid 清理（红线 X2）

## 只改文件
- `.ccc/plans/v09c-e2e-smoke.plan.md` (本文件)
- `.ccc/reports/v09c-e2e-smoke.report.md` (Executor 写)
- `/tmp/v09c_prompt.txt` (临时 prompt)

## Commit 计划
1 个 commit: `test(v0.9c): e2e smoke 验 v0.8/v0.9a 链路`
