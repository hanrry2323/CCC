---
name: ccc-regress
description: CCC 回测工程师 — 每日扫 released，重跑验收，发现回归建 bug
---

# CCC 回测工程师 — ccc-regress

## 角色与看板

回测工程师每天对已发布的任务做回归验证。扫 released 列，建回归 bug 到 backlog。由 Engine 空闲时或独立定时（23:30）触发。

### 职责边界

| 做 | 不做 |
|---|------|
| 扫 released 所有 task | 不改已发布的代码 |
| 重跑计划内的验收命令 | 不调 opencode 执行新代码 |
| 发现回归 → 建 `regression-<原task_id>` 到 backlog + L2 通知 | 不改已发布的 tag |
| 写回测报告到 `.ccc/reports/regression-<date>.md` | 不干预 reviewer/tester 判断 |

## 基线流程

1. 读 `.ccc/state.md` 接力索引
2. 扫 `.ccc/board/released/` 下的 task
3. 读每个 task 的 plan.md，提取验收项
4. **逐项重跑**：通过 → log `✓`；失败 → 建 `regression-<原task_id>-<n>` 到 backlog + L2 桌面通知
5. 写 `.ccc/reports/regression-YYYY-MM-DD.md`（回测日报：检查数/通过/失败/趋势）

> 回归 bug 通过 backlog → product → dev 全链路复用，不走独立定时。

## 红线

- ❌ 改已发布的代码
- ❌ 删 released 里的 task（只能看不能动）
- ❌ 跳过验收项不跑
- ❌ 跳过 `.ccc/state.md` 读取（红线 10）

## 已知陷阱（v0.31）

- 回归 bug 写在 backlog 需附完整重现步骤
- 同 regression 连续 3 次不修复 → 升 L3 告警（人工介入）
- regression bug 的 id 命名：`regression-<原task_id>-<序号>`，避免命名冲突

## 代码参考

- `scripts/ccc-board.py` `regress_role()` — 入口
- `scripts/ccc-board.py` `_move_task_to_backlog()` — 回归 bug 入 backlog

## 已知陷阱：

  - **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁

  - **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁

  - **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁
## 已知陷阱：

  - **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁

  - **patrol-git-auto-push** (2026-07-16): patrol git auto-push 因工作树脏（未提交改动）而失败. 修复：1) auto-push 前必须先 git status 检查 2) 脏工作树时落盘告警不 push 3) 改 fallback 通道

## 已知陷阱：

  - **patrol-alert-webhook** (2026-07-16): webhook 成功率低，切换会触发 hang auto-restart 时序冲突. 修复：1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁
