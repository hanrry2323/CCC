# Brief: stress-mx-20260722 效率评估（下一步开发数据）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-22-stress-efficiency-eval` |
| 状态 | **P0 止损已做；平台 P1–P5 已落地；终稿等 2017 部署后缩小压测复跑** |
| 批次 | `stress-mx-20260722`（双仓 ×10 场景 = 20 transfer） |
| 机器 | Mac2017 · 16GB · i7-7700HQ 4C/8T |
| 生成器 | `scripts/ccc-stress-efficiency-report.py` |
| 产出 | `~/.ccc/stress-matrix/stress-mx-20260722-efficiency.{md,json}` |

## 为什么做

提效是刚需。本次 20 大卡不是「能不能跑通」 alone，而是给 **下一轮平台开发** 提供可对比基线：卡在哪一阶段、墙钟浪费在排队还是执行、主机是否还能加并行。

对齐权威：**少而硬意图 · 唯一路径 · 偏差默认**——报告量「闭环效率」，不量「画布炫技」。

## 统计维度（终稿必须齐）

### A. 吞吐与完成度（场景层）

| 指标 | 定义 | 源 |
|------|------|-----|
| dispatch_ok | 20 transfer 中符合 expect 的比例（含 s07 期望 400） | `stress-mx-*.json` dispatches |
| epic_terminal | epic `split_status` ∈ {done, failed, running, planned} 计数 | board backlog |
| work_terminal | work 终态：released / verified / testing / planned / abnormal | board |
| scenario_pass | 按 s01–s10 是否达成设计意图（门禁/扇出/依赖/拒单） | 人工+板+日志 |

### B. 时间线（效率核心）

| 指标 | 定义 | 源 |
|------|------|-----|
| T_dispatch | transfer 成功时刻 | dispatches / hub |
| T_planned | work 首次进 planned | `board/events/*.events.jsonl` |
| T_dev_start | planned→in_progress | events |
| T_dev_done | in_progress→testing | events |
| T_gate_done | testing→verified\|planned\|abnormal | events |
| T_released | →released | events |
| **queue_wait_s** | T_dev_start − T_planned（同仓排队） | 算 |
| **dev_wall_s** | T_dev_done − T_dev_start（写码墙钟） | 算 |
| **gate_wall_s** | T_gate_done − T_dev_done（审测墙钟） | 算 |
| **e2e_work_s** | T_released\|terminal − T_planned | 算 |
| **e2e_epic_s** | 末子卡终态 − epic 进 backlog | 算 |
| opencode duration_s / wall_s | exec 内 / launch→done | `~/.ccc/stats/opencode-timings.jsonl` |
| 按 complexity | small/medium p50/p95 | timings + task.complexity |

### C. 失败与返工

| 指标 | 定义 | 源 |
|------|------|-----|
| fail_reopen_n | testing→planned / FAIL 回滚次数 | events + engine.log |
| abnormal_n / quarantine_n | 终态 abnormal、quarantine 包 | board + quarantines |
| revert_fail_n | revert 因 dirty/conflict 失败 | engine.log |
| hollow/self-check fail | 门禁拒 | failures.jsonl |
| ghost_slot_events | 「同仓已有 active」且无活进程 | engine.log 交叉 ps（定性） |
| dirty_result_json | result.json 非纯 JSON | reports 扫描 |

### D. 主机与并行

| 指标 | 定义 | 源 |
|------|------|-----|
| load_ratio p50/p95 | load1/ncpu | host-resources.jsonl |
| mem_used_pct p50/p95 | | 同上 |
| active_dev max / avg | | 同上 |
| opencode_n max | | 同上 |
| headroom verdict | | `ccc-host-resources.py summary` |
| 理论并发建议 | 结合 16G/8T 与实测 | 报告结论节 |

### E. 路径分流（提效关键）

| 指标 | 定义 | 源 |
|------|------|-----|
| board_ops / script_seed / opencode 占比 | 短路径 vs 长跑 | engine.log + report 标记 |
| 误进 opencode 的卫生卡 | executor=python 仍长跑 | 对照 |

## 报告结构（终稿章节）

1. **执行摘要** — 完成度、总墙钟、三大瓶颈、下一步开发优先级（≤1 页）  
2. **场景矩阵** — 20 卡 × 终态 × e2e（表）  
3. **时间分解** — queue / dev / gate 堆叠；small vs medium  
4. **失败账本** — 按根因归类（生命周期 / 门禁 / 脏仓 / LLM）  
5. **主机曲线** — 忙时 vs 闲时；能否试 MAX_CONCURRENT+1  
6. **对照权威** — 与「产线提效综合方案 A–F」映射：每条对应数据与建议  
7. **下一程开发 backlog（建议）** — 按 ROI 排序，供拍板

## 方案落地对照（2026-07-23）

平台已实现：P0 止损清场 · P1 槽 FSM · P2 result 契约 · P3 安全 revert · P4 门禁解耦 · P5 短路径硬门 + path 埋点。见 lifecycle brief。  
**终稿仍须**：2017 拉新代码后缩小压测，再跑 `ccc-stress-efficiency-report.py`（含 `dev_path` 占比）。

## 初步效率判断（未收口 · 2026-07-23 00:15）

| 观察 | 含义 |
|------|------|
| 首批 commit ~21:32，仍有 testing/abnormal | **端到端已超数小时**（含排队+人工清槽+Engine 重启） |
| qb 三件套 planned→in_progress 隔约 **2h** | **同仓排队 / 槽占用** 远大于单卡写码 |
| opencode_done wall p50≈10–12s | 含短路径/失败快死，**不能**当「小卡只要 10 秒」；需按 success+真实 duration 重算 |
| duration_s 大量缺失 | 脏 result.json / 收口路径 → **埋点缺口本身是提效项** |
| 主机闲时 headroom | 忙时未采满；**勿据此加并行** |
| demo 多 abnormal + dirty 挡 revert | 纠错路径拖垮吞吐 |

**一句话初评**：路径能力已证明（扇出/依赖/拒单/短路径）；**效率短板在排队+生命周期泄漏+审测同步堵+脏仓回滚**，不是「模型写代码太慢」单因。

## 收口条件（出终稿）

1. stress 相关 work：无 in_progress；testing 清空或明确冻结  
2. epic：running 清零或标注「放弃收口」  
3. 再跑一遍 `ccc-stress-efficiency-report.py` 写入 efficiency.md/json  
4. host-resources 忙时样本 ≥30 点（或注明仅闲时）

**草稿已生成（未收口）**：`~/.ccc/stress-matrix/stress-mx-20260722-efficiency.{md,json}`（2026-07-23 00:16）。

## 命令

```bash
# 在 Mac2017
python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260722
python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260722 --out ~/.ccc/stress-matrix/
```
