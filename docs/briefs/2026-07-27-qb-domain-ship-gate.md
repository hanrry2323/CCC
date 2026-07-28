# qb 业务域出门清单（与 CCC `intent_stable` 分离）

> **日期**：2026-07-27 · **修订 2026-07-29**（开发收口 = B4.2 + B5）  
> **样板仓**：qb（量化）— 脑包见 [`../product/project-agent-brain.md`](../product/project-agent-brain.md)  
> **平台出门**：[`2026-07-27-ccc-production-readiness.md`](./2026-07-27-ccc-production-readiness.md) Layer1  
> **意图飞轮**：[`../product/lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)  
> **权威摘要**：[`../product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「双轨业务」  
> **开程记录**：[`2026-07-28-layer2-qb-open.md`](./2026-07-28-layer2-qb-open.md)

---

## 定位与收口（硬 · 2026-07-29）

**qb** = CCC 产线养大的**单机 VIP 套利引擎**（权威仓 2017 `apps/qb`）。

| 阶段 | 条件 | 可以说 | 不可以说 |
|------|------|--------|----------|
| **开发收口前** | LPSN + B1–B3 + B4.1；**B4.2 / B5 未齐** | 纸面/意图探针可用；收口进行中 | 开发结束、可无人值守实盘、永盈 |
| **开发收口** | 上表 + **B4.2 实盘人确认** + **B5 回测可视化** 都绿 | **开发阶段结束，进入维护态** | invent / 自动 stable / 开源星数=成熟 |
| **维护态** | 收口后默认 | regress / bugfix / 板务养机 | 默认新功能、扩所、跨机、开源公开（须人 supersede） |

**收口前主业只认**：当前 inflight 意图（LPSN）→ **B5 回测可视化** → **B4.2 实盘人确认**。  
P3 跨机、扩所到 30+、开源公开：**非默认**。

---

## 两套勾选（禁止混勾）

| 套 | 证明什么 | 不证明什么 |
|----|----------|------------|
| CCC Layer1 + LPSN | 能用 CCC 把意图开发到 `released`，探针可重放，可标 `intent_stable` | 策略赚钱、风控扛得住、进程 7×24 稳、可实盘 |
| 本清单（qb 域） | 纸面门槛、熔断、保活、**回测可视化**、**实盘人确认** | 平台编排能力（那是 Layer1） |

生产级 / **开发收口** qb = **两套都绿**（含 B4.2 + B5）。

---

## A — CCC 侧（先决 · 非本清单主体）

- [x] 权威仓已 register；M1 **无**第二树  
- [x] 规划 SSOT = `docs/DEV_PLAN_v1.1.md`（CLAUDE 已声明）  
- [x] 业务 epic 验收含可重放探针（白名单；禁散文）  
- [x] 至少一笔产品意图：L → regress P → 人点 S（`intent_stable`）— 见 [`2026-07-28-layer2-qb-open.md`](./2026-07-28-layer2-qb-open.md)（L=commit；tester 全仓假红已诚实记录）  
- [x] 空闲时下一卡来自 `next_product_goal`，非卫生 epic 当主业（本开程遵守）

（细项见 LPSN 出门清单。）

---

## B — qb 域 KPI（必须另立证据）

### B1 意图与探针（业务语义）

| # | 条件 | 证据 |
|---|------|------|
| B1.1 | 产品 goal 退出条件可执行（回测/纸面/契约命令） | L1 `decided.goals[].exit_condition` — **2026-07-28** `g-a61a67dd84` 已可执行 |
| B1.2 | 探针覆盖「钱能不能保住」优先于 alpha | DEV_PLAN VIP→P1 排序可核对 — **勾** |
| B1.3 | regress 挂了建回归 epic，不假装完成 | 板面 tid + `failures.jsonl` — **勾**（假红已修；未假绿 intent） |

### B2 风控与熔断

| # | 条件 | 证据 |
|---|------|------|
| B2.1 | 最大回撤 / 单日亏损上限有硬闸 | 配置 + 单测或纸面跑挂闸日志 — **勾**（risk.py + 45 tests） |
| B2.2 | 异常行情 / 连通中断有停机或降级 | runbook + 至少一次演练记录 — **勾**（进程侧 unload；`docs/INCIDENTS/2026-07-28-disconnect-drill.md`；无实盘断连） |
| B2.3 | 密钥与实盘开关不进对话默认路径 | 控制面/env 分离；禁止 Agent 自开实盘 — **勾**（DRY_RUN 强制） |

### B3 运行稳定

| # | 条件 | 证据 |
|---|------|------|
| B3.1 | 策略/行情进程保活（launchd/systemd 或等价） | plist/unit + `status` 绿 — **勾**（五模板齐；check_plist_health 0 error；socks/frontend warn） |
| B3.2 | 崩溃可告警并可一键交 Agent/人 | 告警条或 Ops 红灯样例 — **勾**（同 INCIDENT 演练窗） |
| B3.3 | 纸面/实盘连续跑窗口达标（时长由 DEV_PLAN 定；**收口前抬高薄 65s**） | 日志起止 + 无未解释断流 — **勾（薄 65s；收口前须按 DEV_PLAN 加长）** |

### B4 盈利与上线（禁止用代码合入替代）

| # | 条件 | 证据 |
|---|------|------|
| B4.1 | 纸面/testnet 达成 DEV_PLAN 写明的门槛 | `docs/reports/layer2-b41-paper-gate.md` — **勾（定性；DEV_PLAN 无数字 PnL）** |
| B4.2 | **实盘开关有人确认清单**（非 Agent 自决）；完成一次受控开/关 | 签字/Desktop 会话确认 + `docs/INCIDENTS/` 或 reports 戳记 — **未勾（收口必选项）** |
| B4.3 | 「能盈利」只认 B4.1–B4.2，**不认** `released` 张数 / GitHub 星 | 本表勾选状态 — **勾**（出门句诚实） |

**B4.2 人确认清单最少含**：开关位、额度/日亏/回撤上限、回滚步骤、观察窗。Agent **禁止**建议「先开源再实盘」当收口路径。

### B5 回测可视化（收口必选项 · 2026-07-29）

| # | 条件 | 证据 |
|---|------|------|
| B5.1 | 一条可重放命令生成**结构化报告**（HTML 或 Markdown+表：净值/回撤/成交摘要） | 脚本路径 + 样例报告进 `docs/reports/` — **未勾** |
| B5.2 | 至少一种**参数扫描**入口（CLI/脚本），结果进同一报告目录；默认 ≥**5** 组参数 | DEV_PLAN 写明 N；命令 exit 0 — **未勾** |
| B5.3 | L1 `exit_condition` 含报告命令；regress 可重放 | `decided.json` + regress 绿 — **未勾** |

**不要求** Grafana/Prometheus 全家桶。**禁止**把「缺开源社区」写成 B5。

---

## C — 明确禁止的假绿

1. 策略文件进 `released` → 声称可上线 / 开发收口  
2. VERSION bump / README stamp → 声称意图稳定  
3. Desktop 能聊 qb → 声称量化闭环已通  
4. 只有 CCC Layer1 绿 → 声称 qb 生产级  
5. GitHub 星 / 社区人数 → 声称 qb 成熟度  
6. 只有 LPSN `intent_stable`、无 B4.2/B5 → 声称开发收口  

---

## D — 维护态（收口后默认 · 硬）

| 类型 | 谁做 | 怎么进板 |
|------|------|----------|
| 意图回归 | Engine `regress` → 失败建回归 epic | 自动 |
| 板堵/残卡 | Desktop 本会话 `hub_repair` | 不下达卫生主业 |
| 生产 bug | Desktop 定稿 → transfer → Engine（bugfix；验收含复现探针） | 人确认 |
| 新功能 / 扩所 / 跨机 / 开源 | **默认拒** | 须人 `supersede_goals` + 新 L1 goal |
| invent / 自动 `intent_stable` | **仍禁** | — |

技术指标（维护态监控；数字以 DEV_PLAN 为准）：B2 风控硬闸；B3.3 观察窗；B5 报告命令 exit 0；regress 探针绿。

---

## 维护

- 改本清单频率 = 改 qb `DEV_PLAN` 门槛时同步；冲突以业务 DEV_PLAN 数字为准、以本清单**结构**为准。  
- 平台权威只指针到本文，不把回撤百分比写进 `loop-engineer-authority.md`。
