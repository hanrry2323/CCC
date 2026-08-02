# Mac2017 并发能力探针 · 2026-07-23

- 工具：`scripts/ccc-capacity-probe.py`
- 默认抬升：`ccc-engine.sh` → `CCC_MAX_CONCURRENT=${CCC_MAX_CONCURRENT:-6}`
- 硬约束：同仓 OpenCode **1**；跨仓池与全局 OpenCode 槽正交

## 方法

1. 干净板 + 多仓有活卡时采样 `host-resources`（≥30 忙时点）
2. `summary` → `headroom|borderline|saturated`
3. 阶梯：4→5→6→8（必要时 10）；`saturated`/挂死上升则回退

## 本轮落地

- 2017 `~/.ccc/engine.env`：`CCC_MAX_CONCURRENT=6`（`ccc-engine.sh` source）
- gate-clean baseline 主机摘要已见 `max_concurrent: 6`，仍 `headroom`
- `~/.ccc/stats/capacity-probe.json`：`write-brief` 会读 engine.env
- 下一档可试 **7–8**（仅当忙时 ≥30 点仍 headroom 且挂死不升）
