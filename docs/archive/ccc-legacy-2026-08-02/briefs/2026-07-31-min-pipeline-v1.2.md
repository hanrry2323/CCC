# 最小可跑通 v1.2（产线硬化）

> 前置：v1.1 已收口（`v0.66.0`）。本文件 = 现行 5 步方案；旧 [`2026-07-31-min-pipeline-next.md`](2026-07-31-min-pipeline-next.md) 缺口表 **已完成（史）**。

## 步骤

1. **fanout 探针保真** — done（`8b6a59e`）
2. **二次瘦身** — done（`62e1d41`）
3. **verify 一扇门** — done（`a965e72`）
4. **权威对齐** — done（`5b454f3`）
5. **2017 复验 + qb 交接** — done（见 golden「v1.2 复验」）

## qb 开程（平台停损后）

- 域门：[`2026-07-27-qb-domain-ship-gate.md`](2026-07-27-qb-domain-ship-gate.md)（B4.2 实盘人确认 + B5 回测可视化）
- 平台：仅修挡 qb 的硬 bug；不重开 L3b/stress/Ops 主路径

## 不做

删旧列名大迁移 / 重开 L3b·stress·Ops / QuantHive 并轨 / force push
