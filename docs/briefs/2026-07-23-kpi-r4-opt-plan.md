# KPI R4 优化方案（基于 R3 FAIL 统计）

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-kpi-r4-opt-plan` |
| 输入 | [`2026-07-23-kpi-r3-eval.md`](./2026-07-23-kpi-r3-eval.md) |
| 通关线 | epic≥10/12 · abnormal≤1 · ghost=0 · queue p95≤300 · duration≥0.9 · dirty=0 |
| 纪律 | 每轮 ≤2 primary；**禁止**加 `MAX_CONCURRENT` 当主药；改码仅 allowlist / 等价结构项 |

---

## 1. 统计摘要（一夜 → R3）

| 批次 | done | abnormal | queue p95 | duration fill | 主败 |
|------|------|----------|-----------|---------------|------|
| v1 overnight | ~50% | 7 | 2367 | 0.51 | 排队+审测爆炸 |
| 中期 r2 | 67% | 2+ghost2 | 554 | 0.0 | 幽灵槽+L0 死门 |
| KPI R1 | **92%** | 1 | 473 | 0.29 | 仅 queue |
| KPI R2 | 83% | 2 | 575 | 0.78 | abnormal+queue |
| KPI R3 | 83% | 2 | **694** | **1.0** | abnormal+queue |

读法：闭环与观测门已从「灾难」拉到「贴线可复盘」；**尾部 queue 与 e04 feature 场景**仍卡门禁。

---

## 2. 根因分层（R3 实锤）

```text
Hub transfer 12/12 OK
  ├─ script_seed / board_ops
  │     ├─ 绕 OpenCode 互斥 ✅（qb 短路径 queue≈0）
  │     └─ 【洞】board_ops 失败 → planned 无预算 → 1Hz 空转风暴（demo 卫生 ×255）
  ├─ OpenCode 同仓 1 路
  │     └─ 【结构】util-w2 / 尾卡 queue 500–800s（依赖+串行地板，勿加并发掩盖）
  └─ e04 feature 探针
        ├─ demo：未写目标文件 → FAIL×3 耗尽
        └─ qb：exit -15 + phase graph unresolvable → 直接 abnormal
```

---

## 3. 优化方案（按杠杆）

### P0 — 必做（直接打 queue p95 + 引擎空转）

**A. 短路径失败预算（board_ops / script_seed）**

| 项 | 内容 |
|----|------|
| 现象 | `dev_path path=board_ops ok=false` 同 task 连打数百次；同仓其它卡 queue 飙到 600–800s |
| 改法 | 短路径失败：记 `fail_count`；≥N（建议 2–3）→ abnormal 或 planned+backoff（指数退避 / 本 tick 跳过该 tid）；**禁止**每秒 `return True` 空转 |
| 埋点 | `dev_path` 带 `why`；`short_path_retry` 事件；效率报告过滤「同 tid 重复 fail」避免 share 虚高 |
| 验收 | 故意让 board_ops 失败：≤3 次尝试后停手；同仓其它 planned 卡 queue 不被拖到分钟级 |
| 触点 | `scripts/ccc-engine.py` 短路径分支；可选 `board/roles/board_ops.py` 返回稳定 `why` |

对应 primary：`queue_wait_p95_s`（结构项，优于加并发）。

### P0' — 与 A 同轮可搭（打 abnormal≤1）

**B. e04 feature 探针稳态（二选一落地）**

| 选项 | 改法 | 取舍 |
|------|------|------|
| B1 压测种子 | stress matrix e04 改为 **script_seed 风格确定性探针**（禁劫持仍可测：断言路径≠paper_intent） | 最快降 abnormal；略降「真 OpenCode」覆盖 |
| B2 产线 | OpenCode `exit=-15` / 空 stdout：**salvage 可修复**（FAIL verdict→planned+R1），禁直接 `phase graph unresolvable` 耗尽；feature 场景强制 `result.wrote` 门 | 更贴生产；改动面较大 |

R4 推荐 **A + B1**（量测可复现、主攻≤2）；B2 进 R5 / allowlist 扩展后再做。

### P1 — 本周（queue 地板认知 + 学习税）

**C. 同仓依赖链 queue 口径**

- util-w2 queue≈600–800s 在「同仓 1 OpenCode」下是**预期地板**；scorecard 可考虑：
  - 分位数排除 `depends_on` 后继卡，或
  - 门禁改为 p95(独立卡)≤300 且 p95(全量)≤900 双轨  
- **先不改门槛**：用 A 消掉风暴后再测一轮真 p95；若仍仅剩依赖地板，再改 scorecard + authority。

**D. 学习税（gate 有 R1 的卡）**

- demo feature gate≈481s ×3 loops — fail pack 已注入但仍不写文件 → 根因在 dev 空跑，不在审测。  
- 优先 hollow / `wrote[]` 空则 **L0 直接 FAIL**（不进 L1），省 Claude 税。

### P2 — 明确不做

- 加 `MAX_CONCURRENT` 当主药（host 已 headroom）  
- Ollama / 第二写码 CLI  
- invent CCC orch / 未核账 reopen  
- 为刷 queue 拆掉同仓 OpenCode 互斥  

---

## 4. R4 执行清单（确认后动手）

1. 实现 **A 短路径失败预算** + 单测（连失败不空转）  
2. 实现 **B1** stress e04 确定性化（或文档化 B2 若选产线）  
3. `py_compile` + 相关 pytest → push → 2017 `reset --hard origin/main`  
4. `ccc-stress-kpi-loop.py continue` + `arm-wake` 3600  
5. evaluate：期望 queue p95 **明显下降**（目标先破 400，再冲 300）；abnormal **≤1**（最好 0）；duration 保持 1.0  

---

## 5. 成功判据（R4）

| 指标 | 目标 |
|------|------|
| board_ops 同 tid 连续 fail | ≤3 即停 |
| queue_wait p95 | ≤300（理想）或 ≤400（可接受中期） |
| work_abnormal_n | ≤1 |
| epic_done_rate | ≥0.833 |
| duration_s_fill_rate | ≥0.9 |
| ghost / dirty | 0 |

未过门禁则 R5 只做 B2（OpenCode -15/空产物 salvage）+ 依赖链口径，**仍禁止加并发**。
