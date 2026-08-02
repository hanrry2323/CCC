# Brief: stress-mx-20260723 效率压测 v2（有价值场景 · 明日回顾）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-stress-efficiency-v2` |
| 批次 | `stress-mx-20260723` |
| 仓 | `ccc-demo` + `qb` |
| 规模 | **每仓 8 场景**（双仓 16 transfer）——**不做每仓 20** |
| 机器 | Mac2017 · MAX_CONCURRENT=4 · 同仓 1 OpenCode |
| 生成器 | `scripts/ccc-stress-matrix.py --profile efficiency_v2` |
| 效率报告 | `scripts/ccc-stress-efficiency-report.py --run stress-mx-20260723` |

## 为何减量（相对「每仓 20」）

| 每仓 20 | 每仓 8（本批次） |
|---------|------------------|
| 同仓互斥 → 排队再次淹没真信号 | queue_wait 可对比 P1 前后 |
| 故意 FAIL/重开制造 ops 红灯 | 去掉噪音场景，保留路径+闭环 |
| 产物垃圾淹没有价值落地 | qb/demo 留下可复用探针/卫生/小模块 |

对齐方案验收总闸：**缩小压测**，不是再倒 40 张。

## 8 场景设计（每仓同构 · 有意图）

| sid | 价值 | 测什么（P1–P5） | path 期望 |
|-----|------|-----------------|-----------|
| e01 | 小模块可 import | 同仓连续 launch / 释槽 | opencode |
| e02 | 两 phase 依赖链 | queue + 同仓串行不幽灵 | opencode |
| e03 | 纸面意图探针 | 短路径硬门 | **script_seed** |
| e04 | 功能 DRY_RUN 探针 | 禁止 script_seed 劫持 | opencode |
| e05 | 看板卫生 | board_ops / python | **board_ops\|python** |
| e06 | 缺探针拒单 | Hub gate（期望 400） | — |
| e07 | 模块+文档双 phase | medium 扇出不过载 | opencode |
| e08 | 纸面路径再确认 | 短路径稳定 + duration 可统计 | **script_seed** |

刻意不做：故意空实现 FAIL、abnormal 重开（上次已验证，且污染运维）。

## 埋点清单（明日回顾必齐）

开工前已写 baseline：`~/.ccc/stress-matrix/stress-mx-20260723-baseline.json`

| 指标 | 源 |
|------|-----|
| dispatch_ok / 场景意图达成 | `stress-mx-20260723.json` |
| queue_wait / dev_wall / gate_wall p50·p95 | efficiency report |
| `dev_path` 占比（board_ops/script_seed/opencode） | events.jsonl |
| `duration_s` fill_rate | opencode-timings |
| dirty_result_n / revert abort | events + engine.log |
| ghost「同仓延后」且无活 pid | engine.log ∩ ps |
| host load/mem p95、active_dev | host-resources.jsonl |
| testing 墙钟超时杀进程次数 | engine.log `budget timeout` |

## 明日回顾命令

```bash
# 2017
python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260723
python3 scripts/ccc-host-resources.py summary --n 200
# 对照 baseline + 本 brief 勾选 P1–P5
```

产出：`~/.ccc/stress-matrix/stress-mx-20260723-efficiency.{md,json}` → 回顾报告：[`2026-07-23-stress-efficiency-v2-report.md`](./2026-07-23-stress-efficiency-v2-report.md)（2026-07-23 11:44，只读未修卡）。
