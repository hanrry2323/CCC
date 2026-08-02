# 任务卡 T7 · 定时任务 + 集群/运维页（P4 · Trae 窗口 B）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（D4 定时任务 / D5 集群状态页）
> 管理席：Claude Code（调度窗口）· 执行体：Trae（窗口 B）· 验收：Claude Code
> 状态：待分派 · 日期：2026-08-02
> 前置：T2/T5（已验收通过）· **并行：T6/P3（worktree trae-a-p3）**
> 工作区：`/Users/apple/program/CCC/.worktrees/trae-b-p4`（分支 `feat/p4-ops-timer`）

## 目标

D4 定时任务：**Engine 承担定时**（到点生成任务卡 → 派发 → 收单回写；巡检类默认只读，变更类走正常任务卡并保留确认）。D5 集群状态页 + 运维页：**采集独立重做**（不依赖 qx-map manifest）。

## 红线（先看）

1. **只改 `server/engine/`、`server/config/`、`server/web/`**（限定时+运维页相关）；**不碰 `server/board/`**（T6 区）。
2. **定时任务默认只读**：巡检只采集不动作；变更类走任务卡保留确认。
3. 集群采集独立实现，不读不写 qx-map / 外脑。
4. **只在 worktree `trae-b-p4` 内工作**，提交到分支 `feat/p4-ops-timer`；不 push main、不 merge main。
5. 零硬编码；验收标准不可自行解释；完成必须提交（分支 commit hash 回写）。

## 范围

- `server/engine/`：定时任务框架（间隔调度、只读巡检、变更类走卡）。
- `server/config/`：定时相关配置键（间隔 / 启用开关，走 loader）。
- `server/web/`：集群状态页 + 运维页（独立采集集群信息展示）。
- `server/tests/`：定时任务 + 集群采集测试。
- **不动**：`server/board/`、`server/relay/`。

## 步骤

1. `server/engine/` 增加定时任务框架（复用 T5 scheduler 思路，扩展为通用定时：只读巡检 + 变更类走卡）。
2. `server/config/` 增加定时配置（间隔 / 开关，走 loader）。
3. `server/web/` 增加集群状态页 + 运维页（独立采集：节点 / 端口 / 服务状态，不依赖 qx-map）。
4. 测试：定时调度 + 采集解析 + 配置加载；既有 83 用例不回归。
5. 硬编码扫描（S1–S4）零字面量；提交分支 `feat/p4-ops-timer`，回写分支 commit hash。

## 验收标准（Claude Code 按此验收）

1. 定时任务框架可跑（只读巡检）；变更类走任务卡保留确认。
2. 集群/运维页显示独立采集的集群状态。
3. 测试全绿（新增 + 既有 83 不回归）；硬编码扫描零字面量。
4. 分支提交真实（`feat/p4-ops-timer` commit hash 回写）；未碰 T6 区文件。

## 回写要求

结果摘要（人话一句）、测试输出、硬编码扫描输出、**分支 commit hash**、验收自检对照表。
**状态同步（契约 §3）**：接单改「执行中」、回写改「已回写」。

## 回写区

（Trae-B 回写）
