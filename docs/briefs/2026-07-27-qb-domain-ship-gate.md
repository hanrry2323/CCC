# qb 业务域出门清单（与 CCC `intent_stable` 分离）

> **日期**：2026-07-27  
> **样板仓**：qb（量化）— 脑包见 [`../product/project-agent-brain.md`](../product/project-agent-brain.md)  
> **平台出门**：[`2026-07-27-ccc-production-readiness.md`](./2026-07-27-ccc-production-readiness.md) Layer1  
> **意图飞轮**：[`../product/lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)  
> **开程（2026-07-28）**：[`2026-07-28-layer2-qb-open.md`](./2026-07-28-layer2-qb-open.md) · 飞轮自动本开程冻结。

---

## 两套勾选（禁止混勾）

| 套 | 证明什么 | 不证明什么 |
|----|----------|------------|
| CCC Layer1 + LPSN | 能用 CCC 把意图开发到 `released`，探针可重放，可标 `intent_stable` | 策略赚钱、风控扛得住、进程 7×24 稳 |
| 本清单（qb 域） | 纸面/实盘门槛、熔断、保活、可观测达标 | 平台编排能力（那是 Layer1） |

生产级 qb = **两套都绿**。

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
| B3.3 | 纸面连续跑窗口达标（时长由 DEV_PLAN 定） | 日志起止 + 无未解释断流 — **勾（薄 65s 双探针）** |

### B4 盈利与上线（禁止用代码合入替代）

| # | 条件 | 证据 |
|---|------|------|
| B4.1 | 纸面/testnet 达成 DEV_PLAN 写明的门槛 | `docs/reports/layer2-b41-paper-gate.md` — **勾（定性；DEV_PLAN 无数字 PnL）** |
| B4.2 | 实盘开关有人确认清单（非 Agent 自决） | 签字/会话确认记录 — **未勾**（实盘仍冻结） |
| B4.3 | 「能盈利」只认 B4.1–B4.2，**不认** `released` 张数 | 本表勾选状态 — **勾**（出门句诚实） |

---

## C — 明确禁止的假绿

1. 策略文件进 `released` → 声称可上线  
2. VERSION bump / README stamp → 声称意图稳定  
3. Desktop 能聊 qb → 声称量化闭环已通  
4. 只有 CCC Layer1 绿 → 声称 qb 生产级  

---

## 维护

- 改本清单阈值 = 改 qb `DEV_PLAN` 门槛时同步；冲突以业务 DEV_PLAN 数字为准、以本清单**结构**为准。  
- 平台权威只指针到本文，不把回撤百分比写进 `loop-engineer-authority.md`。
