# Report: stress-mx-20260723 效率压测回顾（只读事实）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-stress-efficiency-v2-report` |
| 批次 | `stress-mx-20260723` · profile `efficiency_v2` |
| 仓 | `ccc-demo` + `qb` |
| 开工 | 2026-07-23 01:30 CST（baseline） |
| 回顾 | 2026-07-23 11:44 CST |
| 机器 | Mac2017 · MAX_CONCURRENT=4 · 同仓 1 OpenCode |
| 原始产物 | `~/.ccc/stress-matrix/stress-mx-20260723{,-baseline,-efficiency}.{json,md}` |
| 纪律 | **只读看板与指标；未修/未归档/未 reopen 任何卡** |

设计见 [`2026-07-23-stress-efficiency-v2.md`](./2026-07-23-stress-efficiency-v2.md)。

---

## 1. 一句话结论

**Hub 下达与短路径可用；产线仍被「同仓排队 + 审测门」拖死，闭环成功率约一半。**  
CPU/内存有余量，不是算力瓶颈。`dirty_result=0` 是 P2 正向信号；`duration_s` 填充率仍约半。

---

## 2. 看板终态（2026-07-23 11:44）

### 列计数

| app | backlog | planned | in_progress | testing | abnormal | verified | released |
|-----|---------|---------|-------------|---------|----------|----------|----------|
| ccc-demo | 2 | 0 | 0 | 0 | 2 | 0 | 10 |
| qb | 5 | 0 | 0 | 0 | 5 | 0 | 30 |

产线已空转（无 planned/in_progress/testing）；失败尾卡留在 backlog(epic failed) + abnormal(work)。

### 场景意图达成（按 epic / gate）

| sid | 意图 | ccc-demo | qb |
|-----|------|----------|-----|
| e01 | 小模块闭环 | **done**（work released） | **done** |
| e02 | 依赖链 A→B | **done**（w1+w2 released） | **failed**（w1 released，w2 abnormal） |
| e03 | 纸面 script_seed | **done** | **failed**（w1 abnormal） |
| e04 | 功能探针禁劫持 | **failed**（w1 abnormal） | **failed**（w1 abnormal） |
| e05 | 看板卫生 | **done** | **done** |
| e06 | Hub 缺探针拒单 | **GATE OK** http=400 | **GATE OK** |
| e07 | 模块+文档双 phase | **failed**（w1 released，w2 abnormal） | **failed**（同左） |
| e08 | 纸面路径复验 | **done** | **failed**（w1 abnormal） |

**口径**：dispatch 16/16 ok ≠ 意图闭环。transfer/gate 层全绿；epic `split_status=done` 仅 **7/14** 可入板场景（另 2 拒单不算 epic）。  
失败 epic **7**（demo 2 + qb 5），均 `ui_hidden=false`；成功 epic 多为 `done` + `ui_hidden=true` 沉底。

### Abnormal work 原因（事实摘录，未处置）

| work | 主因（ledger / note） |
|------|------------------------|
| demo e04-w1 | LLM JSON parse failed → fallback_quarantine；revert_skipped conflict；engine 重试 3 次隔离 |
| demo e07-w2 | `phase graph unresolvable`（epic 子卡，禁止 product regen）；report 自称 SELF-CHECKS PASSED |
| qb e02-w2 | **reviewer 未产出 verdict**（from testing） |
| qb e03-w1 | **reviewer 未产出 verdict** |
| qb e04-w1 | `phase graph unresolvable` |
| qb e07-w2 | `phase graph unresolvable`；report 记 **HOLLOW FAIL** |
| qb e08-w1 | reviewer 未产出 verdict；另有 large-class LLM JSON parse fallback_quarantine |

---

## 3. 效率指标（vs baseline）

Baseline（01:30）：两仓板空闲；host `headroom`；HEAD `59e90068`。

| 指标 | 值 | 解读 |
|------|-----|------|
| dispatch | **16/16** ok | 下达与 e06 拒单门正常 |
| work 列 | released **11** / abnormal **7** | 闭环≈61% work；失败集中审测/图 |
| epic failed | **7** | 任一子卡 abnormal → epic failed |
| queue_wait_s p50/p95 | **823 / 2367** (n=18) | **排队主导** ≫ 写码 |
| dev_wall_s p50/p95 | **73 / 477** (n=14) | OpenCode/短路径本身可接受 |
| gate_wall_s p50/p95 | **800 / 3566** (n=14) | **审测比写码更慢** |
| e2e_work_s p50/p95/max | **2202 / 3715 / 4998** | 端到端小时级 |
| duration_s fill_rate | **0.512** | 仍近半缺 duration（P2 未完全收口观测） |
| dirty_result_n | **0** | P2 正向 |
| dev_path share | script_seed **50.8%** / opencode **45.8%** / board_ops **3.4%** | 短路径有触发；fail 计数空 |
| OpenCode wall p50/p95 | **32s / 245s** | 单次执行不慢 |
| host load_ratio p95 | **0.34** · mem p95 **~64%** | 仍 **headroom**；active_dev 均值≈0 |
| fail_loops 尖峰 | demo e03-w1 **20**；demo e01-w1 **11** | 门禁反复，拉高 gate_wall |

报告生成器 bottlenecks 原文：

- 排队主导：queue_wait p95=2367s ≫ dev p95=476s（同仓互斥/幽灵槽）
- 审测偏慢：gate p95=3566s > dev p95=476s
- abnormal=7；epic failed=7

---

## 4. 对照 P0–P5 验收（事实勾选）

| 项 | 本批事实 | 判 |
|----|----------|----|
| P1 槽位/同仓 | 双仓并行有 in_progress，但同仓 queue_wait p95 仍 >2ks | 部分改善，**排队仍主矛盾** |
| P2 dirty result | dirty_result_n=0 | **过** |
| P2 duration 可统计 | fill_rate 0.51 | **未过** |
| P3 revert 干净 | e04 出现 revert_skipped / conflict | **未过**（至少 1 例） |
| P4 testing 预算 | gate_wall p95 3.5ks；多卡 fail_loops 高 | **未证明变快** |
| P5 短路径硬门 | script_seed/board_ops 有 share；e05/e03 demo 闭环 | **路径存在**；qb 纸面卡死在 reviewer |
| Hub gate e06 | 双仓 400 `missing_intent_probe` | **过** |
| 主机并发 | headroom，建议试 +1 但同仓仍 1 路 | **勿用加并发掩盖排队** |

---

## 5. 场景级读法（有价值 vs 噪音）

- **稳定绿**：e01 小模块、e05 卫生、demo 侧 e02/e03/e08、双仓 e06 拒单。
- **路径对但审测脆**：qb e03/e08 script_seed 已写报告，卡在 **reviewer 无 verdict**。
- **图/多 phase 脆**：e07 双仓、qb e04 → `phase graph unresolvable` / HOLLOW。
- **模型/解析脆**：demo e04、qb e08 附带 **JSON parse → fallback_quarantine**。
- **减量正确**：若每仓 20，queue_wait 与 abnormal 尾会更淹没上述真信号。

---

## 6. 明日/下次平台开发优先（仅建议，本次未改码未修卡）

1. **审测墙**：reviewer 未产出 verdict 的超时/重试/硬失败路径（qb 纸面短路径被审测拖死）。
2. **phase graph unresolvable**：多 phase / 文档 phase 与 hollow 门交叉（e07）。
3. **queue_wait**：同仓串行可接受，但 p95>2ks 需对照 ghost slot / testing 占 tick（对照 lifecycle brief）。
4. **duration_s fill**：在 dirty=0 前提下把 fill_rate 拉到 ≥0.9。
5. **revert conflict**：FAIL 半途仍有 revert_skipped，对齐 P3。

---

## 7. 复现命令（2017）

```bash
python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260723
python3 scripts/ccc-host-resources.py summary --n 200
# 看板只读：FileBoardStore 列计数 + epic split_status（勿 quarantine / reopen）
```
