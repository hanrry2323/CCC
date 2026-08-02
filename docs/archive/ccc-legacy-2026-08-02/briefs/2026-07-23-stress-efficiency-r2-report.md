# Report: stress-mx-20260723r2 中期审查（~1h10m，板未空）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-stress-efficiency-r2-report` |
| 批次 | `stress-mx-20260723r2` · profile `efficiency_six` |
| 仓 | `ccc-demo` + `qb` |
| 开工 | 2026-07-23 12:43 CST（baseline · HEAD `cc745bce`） |
| 审查 | 2026-07-23 13:51 CST（定时 +10m 触发；**不等板空**） |
| 机器 | Mac2017 · MAX_CONCURRENT=4 · 同仓 1 OpenCode |
| 原始产物 | `~/.ccc/stress-matrix/stress-mx-20260723r2{,-baseline,-efficiency}.{json,md}` |
| 纪律 | **只读看板与指标；未修/未归档/未 reopen 任何卡** |

对照昨夜全量回顾：[`2026-07-23-stress-efficiency-v2-report.md`](./2026-07-23-stress-efficiency-v2-report.md)。  
本批已带 **gate fitness + failure learning R1/R2**（`cc745bc`）。

---

## 1. 一句话结论

**相对 v1，时延与失败面明显收敛；闭环仍未收口。**  
主矛盾已从「整夜排队+无 verdict」转为：**短路径做完却卡 in_progress（幽灵槽）+ L0 分级/提交门硬死 + 审测仍慢于写码**。Failure learning 在 qb 侧已证明能救回多卡；demo 两处死在学习环之外的硬门。

---

## 2. 看板快照（13:51，板未空）

### Work 列（本批 stress 卡）

| 状态 | n | 说明 |
|------|---|------|
| released | **10** | 多数场景已闭环 |
| in_progress | **2** | 双仓 e05 卫生：`board_ops` 已 done，卡仍停 |
| abnormal | **2** | 均在 ccc-demo |

### Epic `split_status`（12 入板场景）

| 态 | n | 卡 |
|----|---|-----|
| **done** | **8** | demo e01/e03/e08；qb e01/e02/e03/e04/e08 |
| **failed** | **2** | demo e02（w2 abnormal）；demo e04（w1 abnormal） |
| **running** | **2** | demo e05、qb e05（卫生 work 卡死 in_progress） |

**口径**：dispatch **12/12** ok ≠ 意图闭环。截至审查时 epic done **8/12（67%）**；若 e05 能推进，理论上可达 10/12。

### 场景意图表

| sid | 意图 | ccc-demo | qb |
|-----|------|----------|-----|
| e01 | 小模块闭环 | **done** | **done**（fail_loops=2 后经 R1 救回） |
| e02 | 依赖链 A→B | **failed**（w1 released，w2 abnormal） | **done**（w2 fail_loops=2 后 released） |
| e03 | 纸面 script_seed | **done** | **done** |
| e04 | 功能探针禁劫持 | **failed**（commit-gate / dirty） | **done**（fail_loops=1 后 released） |
| e05 | 看板卫生 | **running**（board_ops 已 ok，卡 in_progress） | **running**（同左） |
| e08 | 纸面路径复验 | **done** | **done** |

（本 profile 故意跳过 e06 拒单门、e07 文档双 phase。）

### Abnormal / 卡死事实（未处置）

| work | 主因 |
|------|------|
| demo `…feature-dr-…-w1` | **commit-gate: auto-commit failed** — 工作区脏（`demo-medium-fanout`，未暂存变更）；进 abnormal；dev_wall 未形成 |
| demo `…util-a-b-…-w2` | **L0 reviewer**：`diff stat 缺 summary 行，无法分级` → quarantine / abnormal（非「无 verdict」） |
| demo/qb e05 `…-w1` | **board_ops 短路径已写 report + result.json + done/exitcode=0**，列仍 **in_progress** ≈1h → **幽灵槽 / 推进漏拍** |

### Failure learning 信号（正向）

qb 侧至少 3 张留下 R1 `*.review_fail.md` 且最终 **released**：

- `qb-hello-…-w1`（loops=2，gate_wall≈1162s）
- `qb-util-a-b-…-w2`（loops=2，gate_wall≈636s）
- `qb-feature-dry-run-…-w1`（loops=1，gate_wall≈972s）

说明：**FAIL→planned + fail pack 注入在真实压测上有效**；代价是 gate_wall / e2e 被拉长（学习税）。

---

## 3. 效率指标（vs v1 昨夜）

| 指标 | r2（本批 ~1h） | v1（昨夜全跑） | 读法 |
|------|----------------|----------------|------|
| dispatch | **12/12** | 16/16 | 下达稳 |
| work released / abnormal | **10 / 2** | 11 / 7 | 失败面大幅收 |
| epic failed | **2**（+2 running） | 7 | 收敛；未终局 |
| queue_wait p50/p95 | **97 / 554** | 823 / 2367 | **~4× 改善** |
| dev_wall p50/p95 | **28 / 227** | 73 / 477 | 写码仍不是主矛盾 |
| gate_wall p50/p95 | **176 / 1067** | 800 / 3566 | **~3× 改善**；仍 > dev |
| e2e p50/p95/max | **385 / 1516 / 1680** | 2202 / 3715 / 4998 | 小时内可闭环 |
| dirty_result_n | **0** | 0 | 保持 |
| duration_s fill_rate | **0.0** | 0.51 | **观测回退** |
| dev_path share | opencode 63% / script_seed 26% / board_ops 11% | 相近 | 短路径在用 |
| host | load_p95≈0.35 · mem_p95≈64% · **headroom** | 同 | **勿靠加 MAX_CONCURRENT 掩盖** |

生成器 bottlenecks 原文：排队主导（554≫227）；审测偏慢（1067>227）；abnormal=2；epic failed=2。

---

## 4. 根因分层（全链路）

```text
Hub transfer ──OK──► product 扇出 ──OK──►
  ├─ script_seed / board_ops 短路径 ──执行 OK──► 【洞】列推进/salvage 漏拍（e05）
  ├─ OpenCode dev ──多数 OK──►
  │     └─ commit-gate ──【洞】业务仓脏树硬失败（demo e04）
  └─ testing / reviewer
        ├─ L0 分级 ──【洞】diff-stat 无 summary → 直接死（demo e02-w2）
        ├─ L1 Claude + R1/R2 ──【正】qb 多卡救回；【税】gate 分钟～十余分钟
        └─ 同仓串行 ──【结构】queue_wait 仍 > dev；e05 幽灵槽加剧占位
```

---

## 5. 优化方案（按优先级 · 平台开发）

### P0 — 立刻（否则压测/产线继续假忙）

1. **短路径完成后强制推进**  
   - 现象：`board_ops`/`script_seed` 已 `done`+report，卡停 `in_progress`。  
   - 目标：exitcode=0 且 result.json ok → 同 tick 进 testing（或 hygiene 直达 verified/released 的既定短路径），并释放同仓槽。  
   - 验收：复现 e05 双仓，**不得**出现 >2min 的 done+in_progress。

2. **L0 `diff stat 缺 summary` 不得黑盒隔离**  
   - 现状：无法分级 → abnormal/quarantine，学习环吃不到可修信号。  
   - 改法：缺 summary 时走 **可修复类别**（重取 `git diff --stat` / 按空 diff 或 hollow 规则 FAIL→planned+R1），禁止「无法分级」直接耗尽。  
   - 验收：同类卡至少 1 次进入 planned 且 fail pack 可读。

### P1 — 本周产线质量

3. **commit-gate × 脏工作树**  
   - demo e04 死在 auto-commit + 非本任务脏文件。  
   - 改法：dev 开跑前 `ccc_hygiene` 与业务脏分离；仅阻塞业务脏；或 isolation 提交只 stage 白名单路径。  
   - 验收：故意预置无关脏文件时，白名单任务仍能提交或明确 `dirty_block` 原因（非含糊 git 状态倾倒）。

4. **削减「学习税」下的 gate_wall**  
   - qb 已证明 R1 有效，但 hello gate≈19min。  
   - 改法：card-kind L0 先拦文件存在性/验收命令；Claude 仅语义层；同一 fail_loops 内复用 fail pack 禁止重复长审。  
   - 目标：有 R1 的卡 gate_wall p95 **< 600s**（本批 p95=1067）。

5. **duration_s fill_rate 回退（0.0）**  
   - OpenCode wall 有 n=14，duration 全空。  
   - 修 result.json / timings 写入；目标 fill_rate **≥0.9** 且 dirty=0 保持。

### P2 — 结构吞吐（仍不要加并发当药）

6. **queue_wait**  
   - 同仓 1 OpenCode 保留；优先消灭幽灵槽（P0-1）再看 p95。  
   - 目标：下一批同 profile queue_wait p95 **< 300s**（本批 554；v1 2367）。

7. **MAX_CONCURRENT**  
   - host 仍 headroom，**默认维持 4**；仅在幽灵槽清零且 busy 样本充分后再试 5。

### 明确不做（本轮）

- 不修/不 reopen 本批卡（除非你下令清场）。  
- 不上 Ollama / 第二写码 CLI。  
- 不把 Claude 变回默认全量审。

---

## 6. 建议下一批压测口径

| 项 | 建议 |
|----|------|
| 前置 | 合并 P0-1/P0-2 后再跑同 profile |
| 规模 | 继续 `efficiency_six`（6×2）；勿回到 20/仓 |
| 观察 | e05 是否 2min 内闭环；demo e02/e04 是否还进 abnormal；R1 卡 gate p95 |
| 成功线 | epic done **≥10/12**；abnormal **≤1**；queue p95**<300**；duration fill **≥0.9** |

---

## 7. 复现 / 只读命令（2017）

```bash
python3 scripts/ccc-stress-efficiency-report.py --run stress-mx-20260723r2
# 对照：~/.ccc/stress-matrix/stress-mx-20260723r2-efficiency.{json,md}
# 板未空属预期；本 brief 以 13:51 快照为准
```

---

## 8. 优化落地顺序（实施清单）

| 序 | 项 | 主要触点（预期） |
|----|-----|------------------|
| 1 | 短路径 done→列推进 | `scripts/board/roles/dev.py` / engine salvage / board_ops 收尾 |
| 2 | L0 diff-stat 可修复化 | `scripts/board/roles/reviewer.py` + gates |
| 3 | commit-gate 脏树策略 | exec-commit / isolation / dirty 分类 |
| 4 | L0 前置减 Claude 税 | gate fitness + fail pack 复用 |
| 5 | duration_s 回填 | opencode result / timings |

**平台开发默认下一步：先做 P0-1 + P0-2**（幽灵槽 + L0 分级死门）。等你点头再改码。
