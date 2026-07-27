# KPI 缩小复跑 R1 评估（ccc-demo · 2026-07-28）

> **run**：`stress-mx-20260728-kpi-r1`  
> **profile**：`efficiency_six` · **apps**：`ccc-demo` only  
> **loop**：`kpi-20260728-021455` · max_rounds=2  
> **gate**：`~/.ccc/stress-matrix/stress-mx-20260728-kpi-r1-kpi-gate.json`

## Verdict

**PASS**（`evaluated_at=2026-07-28T03:34:32+08:00`）· `primary_fail=[]` · state=`passed`

| Gate | Expected | Actual | OK |
|------|----------|--------|----|
| epic_done_rate | ≥0.8 | **1.0**（5/5 done） | yes |
| work_abnormal_n | ≤1 | **0**（computed） | yes |
| ghost_in_progress_n | =0 | 0 | yes |
| queue_wait_indep p95 | ≤300s | **89.25s** | yes |
| queue_wait_all p95 | ≤900s | 89.25s | yes |
| gate_wall p95 | ≤600s | 0.85s | yes |
| e2e_work p95 | ≤1200s | 203.4s | yes |
| duration_s fill | ≥0.9 | 1.0 | yes |
| dirty_result_n | =0 | 0 | yes |

## vs R5

R5（`stress-mx-20260723-kpi-r5`，双仓）曾 PASS。本轮为 **Layer1 出门后单仓缩小复跑**：验证 Relay/DoD/board/`--apps` 改动未打穿主门；独立卡 queue p95 显著好于历史双仓地板。

## 诚实残留（不挡 PASS）

1. **手工 seed**：OpenCode 卡曾因 `prepare`「scope 文件缺失」空转；seed `scripts/eff23r2_ccc_demo_{mod,util_a,util_b}.py` 后才启动。→ 平台修：缺失 in-tree leaf **放行**（见 `_role_tool.py`）。
2. **板面孤儿**：evaluate 时仍见 `util-w1` 在 `abnormal`（reason 曾为 `reviewer 未产出 verdict`）且 `util-w2` planned；gate `work_abnormal_n`/`epic_done` 按效率报告 computed 仍绿（epic `split_status=done`）。不另开卫生 epic；清场归会话 board_ops 若需。
3. **干预**：非无人值守；Cursor 热更 + seed + evaluate。

## 下一步

- 程 B KPI 勾完成；**不** `continue` r2（本轮 PASS）。
- 进入 v0.63 `nudge_bg_session` 真注入。
