# Mac2017 并发能力探针 · 2026-07-23

- 工具：`scripts/ccc-capacity-probe.py`
- 默认抬升：`ccc-engine.sh` → `CCC_MAX_CONCURRENT=${CCC_MAX_CONCURRENT:-6}`
- 硬约束：同仓 OpenCode **1**；跨仓池与全局 OpenCode 槽正交

## 方法

1. 干净板 + 多仓有活卡时采样 `host-resources`（≥30 忙时点）
2. `summary` → `headroom|borderline|saturated`
3. 阶梯：4→5→6→8（必要时 10）；`saturated`/挂死上升则回退

## 本轮落地

见 2017 `~/.ccc/stats/capacity-probe.json`（部署后 `write-brief`）。  
目标「10 项目同时开发」的有效天花板 ≈ `min(有卡 app 数, MAX_CONCURRENT, 全局 OpenCode 槽)`，不是同仓 10 路写码。
