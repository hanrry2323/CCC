# 压测 KPI 闭环（标准流程）

> **状态**：现行 · 2026-07-23  
> **SSOT 门槛**：[`../../references/stress-kpi-scorecard.json`](../../references/stress-kpi-scorecard.json)  
> **权威摘要**：[`loop-engineer-authority.md`](loop-engineer-authority.md)（压测 KPI 节）

## 要解决什么

压测不能只「跑完写感受」。必须：**同一 profile → 出效率 JSON → 打 KPI 门禁 → 只改有数据支撑的项 → 再压**。  
`ccc-demo` + `qb` 先打通，再复制到已注册未开工旧仓与新仓 → **准入标准流程**。

## 可行性分层（硬）

| 层 | 内容 | 自动化 |
|----|------|--------|
| A 量测 | baseline / dispatch / efficiency report / KPI gate | **全自动脚本** |
| B 定时 | 投递后 sleep 1h → 唤醒 Cursor 审查 | **Cursor loop / arm-wake** |
| C 优化 | 按 `primary_fail` + allowlist 改平台 | **Cursor Agent**（禁止无人乱改） |
| D 再投 | `continue` 下一 round | 脚本；须 C 已部署 2017 |

**不要**指望无 Cursor 的 cron 自己改产线代码。高自动化 = A+B+D 稳，C 有门禁。

## 轮次评估

| 轮 | 主攻（典型） | 对应真相 |
|----|--------------|----------|
| R1 | ghost_in_progress / 短路径推进 | e05 done 卡 in_progress |
| R2 | L0 diff-stat 可修复 | e02 无法分级直接死 |
| R3 | commit-gate 脏树分离 | e04 dirty abort |
| R4 | gate_wall + duration fill | 学习税 / 观测回退 |
| R5 | 储备 / 收口 | 未过门禁用尽前最后一击 |

**推荐 4、上限 5**（写在 scorecard）。

## 核心门禁（摘要）

| KPI | 门槛 |
|-----|------|
| epic_done_rate | ≥ 0.833（≈10/12） |
| work_abnormal_n | ≤ 1 |
| ghost_in_progress_n | = 0 |
| queue_wait p95 | ≤ 300s |
| gate_wall p95 | ≤ 600s |
| e2e p95 | ≤ 1200s |
| duration_s fill | ≥ 0.9（否则 INVALID） |
| dirty_result_n | = 0（硬红） |

基线对照：v1 `stress-mx-20260723`、r2 `stress-mx-20260723r2` 已写入 scorecard.baselines。

## 操作

见 [`.cursor/skills/ccc-stress-kpi/SKILL.md`](../../.cursor/skills/ccc-stress-kpi/SKILL.md)。

```bash
python3 scripts/ccc-stress-kpi-loop.py init --apps ccc-demo,qb
python3 scripts/ccc-stress-kpi-loop.py dispatch
python3 scripts/ccc-stress-kpi-loop.py arm-wake --seconds 3600
```

## 旧仓 / 新仓

前置：`ccc-init --register`、Hub baseline、无活跃 inflight、控制面 `enabled`。  
然后 `init --apps <project_id>`，**同一 gates** —— 这就是标准准入压测。

> **现状**：`ccc-stress-matrix.py` 场景仍硬编码 `ccc-demo`+`qb` 双仓矩阵。单仓/多仓泛化是下一刀（KPI loop 的 `--apps` 已预留）；在此之前旧仓准入可先「注册后挂到 dual 矩阵旁路脚本」或扩 matrix `APPS`。
