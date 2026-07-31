# 最小可跑通 v1.2（产线硬化）

> 前置：v1.1 已收口（`v0.66.0`）。本文件 = 现行 5 步方案；旧 [`2026-07-31-min-pipeline-next.md`](2026-07-31-min-pipeline-next.md) 缺口表 **已完成（史）**。

## 步骤

1. **fanout 探针保真** — epic 强探针不得静默换成 `py_compile`（`_product_fanout`）
2. **二次瘦身** — `verify_gate` / `hang_support` / `dev_salvage`
3. **verify 一扇门** — loop/gates 叙事；`semantic_counts`
4. **权威对齐** — authority + consensus + golden
5. **2017 复验 + qb 交接** — 无人工改探针 FAIL；开程 → B4.2/B5

## 不做

删旧列名大迁移 / 重开 L3b·stress·Ops / QuantHive 并轨 / force push
