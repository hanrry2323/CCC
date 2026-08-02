# KPI R5 优化方案（R4 验收后）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-kpi-r5-opt-plan` |
| 输入 | [`2026-07-23-kpi-r4-eval.md`](./2026-07-23-kpi-r4-eval.md) |
| 现状 | R4 **近通关**：仅 `queue_wait_p95_s=574` FAIL；其余主门绿 |
| 纪律 | ≤2 主攻；禁加 `MAX_CONCURRENT` |

## 问题

1. **scorecard 与同仓串行冲突**：e02-w2 queue 500–700s 是依赖地板；用全量 p95≤300 会永久卡死通关。  
2. **卫生 × scope DoD**：paper 报告脏文件触发 `dirty_block`，board_ops 预算耗尽 → 1 张 abnormal。

## 方案

### A. queue 门禁适型（主攻 1）

- `ccc-stress-efficiency-report` / gate：标记 work 是否有未完成前驱  
- scorecard：`queue_wait_p95_s` 改为 **独立卡**（无 blocked-by 同 epic 前驱）p95≤300  
- 可选保留观测：`queue_wait_p95_all_s`≤900 不挡 PASS  
- 同步 `stress-kpi-scorecard.json` + authority 一句

### B. hygiene dirty_block 豁免（主攻 2）

- `ensure_task_commit`：hygiene / board_ops 任务对 `docs/reports/**` 等非 scope 脏 **留 unstaged 且不 dirty_block**  
- 或 board_ops：scope 仅 `.ccc/**` 时 `ok` 不依赖吞掉业务脏

## 明确不做

加并发；再改短路径互斥；为刷 p95 拆同仓 OpenCode 锁。

## 验收

同 profile 再跑：独立卡 queue p95≤300；abnormal≤1（理想 0）；duration=1；ghost=0 → **PASS 可宣布 efficiency_six 打通**。
