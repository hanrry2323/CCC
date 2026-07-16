# Batch2 自主巡检剧本（用户授权 2026-07-17 05:14）

## 目标任务（5）

`cla-b1--qx--1-vded` · `cla-b1-1-migrate` · `cla-obs1-commit` · `cla-obs2-pytest` · `cla-obs5-marker`

## 用户约束

1. 允许中转站埋点；智能分流（免费池破瓶颈、task sticky 避中途换模）。
2. 未完全失败 → **不插手**；完全失败 → 可改流程 / 改方案 / 重投。
3. 重投后继续每 1h 巡检，直到完成或判定不可收敛。
4. MiniMax：评估倾向 **兜底而非全局 P0**（见下文决策）。

## 基线（05:14）

- in_progress×3：B1 / B1.1 / OBS1  
- backlog×2：OBS2 / OBS5  
- released：OBS3 / OBS4（批1）  
- abnormal：0  

## 判定

| 状态 | 条件 | 动作 |
|------|------|------|
| 完成 | 5 卡均 verified\|released | 停 loop；写验收摘要；可开工埋点/分流（不挡业务） |
| 进行中 | 有 in_progress\|testing\|planned，或 backlog 排队且 Engine 活 | **不干预**；再睡 1h |
| 软卡死 | Engine 心跳停 / 双槽>90min 无新 commit | kickstart Engine only；仍不改任务文案 |
| 完全失败 | ≥3 abnormal 且无活跃执行，或 2h+ 零进展 | 修门禁/路由埋点；按卡清理 fail 计数；**保留半成品代码**重投 backlog；必要时收窄 B1/B1.1 互抢 scope |

## 重投规则

- title/description **不变**（除非完全失败且证明文案不可执行）。
- 清：`.product-fail-counter` / 坏 `product_fallback` / phases 重置 pending；计划若 lint 烂可删让 product 重拆。
- 工作树：**返工模式**——保留 `src/` 等已有文件，不默认 bootstrap 清空。
- 仅当两卡互相污染到无法收敛 → 才对冲突路径做定向清理（不是整仓回滚）。

## MiniMax 优先级（已定决策草案）

**保持 MiniMax 兜底（非全局 P0）。**  
理由：3 并发约 1–2h 抽干配额 → 后半程仍跌回免费池并中途换模，速度/质量双损。  
正确破瓶颈：免费池 **分流 + task sticky**；MiniMax 留给双冷或高优卡。

## 失败重投与上下文（现状 → 目标）

- 现状：quarantine → abnormal + lessons/ledger；product 重跑会注入近期 lessons；**不会**自动带着完整「上次 diff 失败分析」做外科返工；常见是新一轮 plan/exec。
- 目标（可后续做，非本夜必须）：重开时注入 `last_failure_reason` + 保留 worktree，明确「在现有代码上改」vs「清理重来」。
