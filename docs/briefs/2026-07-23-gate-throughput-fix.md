# Brief: 审测门禁吞吐修复（gate-clean 后）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-gate-throughput-fix` |
| 触发 | `stress-mx-20260723-gate-clean`：gate p95≈211s ≫ dev≈12s；ccc-demo～200s / qb～几秒 |
| 根因 | `testing_gate_max_per_tick=1` + 仅每 ~60s 跑 testing → 同仓多卡在 testing **空等**被计入 `gate_wall` |
| 非根因 | 残卡噪声（已干净板）；LLM 审测本身（短路径 deterministic 已存在） |

## 改动

| # | 内容 |
|---|------|
| 1 | `testing_gate_max_per_tick` 默认 **1→4** |
| 2 | testing 列 **短路径优先**（script_seed/feature_seed/board_ops） |
| 3 | 短路径单卡墙钟 cap **45s** |
| 4 | Engine **每 tick** 抽 testing（不再只挂在 `% 6`） |

## 预期

同仓 4 张短路径卡应在一两个 tick 内出 testing，gate_wall p95 从 ~210s 降到数十秒量级（仍受同仓 OpenCode 与依赖链约束）。
