# 飞轮自动化开程（2026-07-28）

> **选轨**：LPSN 飞轮 T1–T4  
> **前置**：Layer2 qb 遗留已清（B4.2 实盘仍冻）；Relay Flash / R1–R4 封印  
> **规划 SSOT**：[`2026-07-24-lpsn-flywheel-auto.md`](./2026-07-24-lpsn-flywheel-auto.md)

## 目标

机械补齐 L1 goal seed（T1）与 regress→probed（T2）；Desktop 人点 stable（T3）；idle 强制露出 `next_product_goal`（T4）。

## 禁止

- 自动 `stable` / invent / 无人值守清板  
- Ops UI 大包、抬 `MAX_CONCURRENT`、HK/三档回流  
- 用 `released` 冒充意图稳定  

## 验收

| 步 | 条件 |
|----|------|
| T1 | 非卫生 transfer 成功后 `decided.goals` 有匹配 planned goal |
| T2 | regress 探针绿 → goal=`probed`（不写 stable） |
| T3 | FlowRail「标记稳定」→ Hub POST status → `stable` |
| T4 | baseline compact + sidecar digest 含 `next_product_goal` |
| 测 | `test_intent_probe_lpsn` + `test_lpsn_flywheel.sh` 覆盖 T1/T2 |

## 状态

**已实现**（Cursor · 2026-07-28）：T1 `maybe_seed_goal_from_transfer` · T2 regress→probed · T3 FlowRail「标记稳定」· T4 baseline/sidecar `next_product_goal`。单测 + `test_lpsn_flywheel.sh` 绿。

**仍禁**：自动 stable · invent · B4.2 实盘。
