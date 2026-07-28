# Layer2 qb 开程（2026-07-28）

> **选轨**：Layer2 qb（业务意图样板）  
> **冻结本开程**：飞轮 T1–T4 自动 · invent · Ops UI 抛光  
> **平台前置**：Relay Flash + R1–R4 封印（`fcd7c0f`）→ 开程文档 `6ec4f28`  
> **域清单 SSOT**：[`2026-07-27-qb-domain-ship-gate.md`](./2026-07-27-qb-domain-ship-gate.md)  
> **权威仓**：`/Users/fan/program/apps/qb`（2017）· Hub `project_id=qb` · M1 **无**第二树

---

## 目标 / 禁止

少而硬意图走 LPSN **L → P → 人点 S**，域 KPI 另表勾选。  
禁止：`released` 冒充盈利；自动 `stable`；invent；卫生 epic 主业。

---

## A — CCC 侧（本开程结果）

| # | 状态 | 证据 |
|---|------|------|
| A1 register / 无 M1 第二树 / engine@2017 | **勾** | `~/.ccc/workspaces.json` qb `engine=true`；M1 无 `apps/qb` 权威树 |
| A2 规划 SSOT = DEV_PLAN_v1.1 | **勾** | qb `CLAUDE.md` 声明规划文 |
| A3 验收含可重放探针 | **勾** | transfer acceptance 含 `paper_intent_probe` + 戳记路径 |
| A4 L → P → 人点 S | **勾**（诚实注下） | 见附录 |
| A5 不投卫生主业 | **勾** | 本开程未投卫生 epic；abnormal 用 board-repair |

### A4 附录（诚实）

| 步 | 结果 |
|----|------|
| transfer | `POST /api/desktop/transfer` → epic `layer2-lpsn-3b8aed9c`（`supersede_goals=true`） |
| L `code_landed` | commit `ee1b688f` 含 `docs/reports/layer2-open-lpsn-evidence.md`（`LAYER2_LPSN_OPEN_OK`） |
| 板面 | work `…-w1` 曾因 **全仓 pytest**（2 failed testnet smoke，与本戳记无关）`tester_fail_loop_exhausted` → abnormal；已 `clear_blockers` 隐藏并快照 quarantine |
| P | `DRY_RUN=true .venv/bin/python scripts/paper_intent_probe.py --env paper` → **PASS**；goal `g-a61a67dd84` → **probed** |
| S | Cursor 代人：`ccc-mind-update.py qb --stable g-a61a67dd84` → **stable** |

**不宣称**：该 work 自动走到 `released` 列（tester 全仓套件假红挡门）。L 认 **git commit**；P/S 认探针与 mind。

---

## B — qb 域 KPI（本开程结果）

### B1 意图与探针

| # | 状态 | 证据 |
|---|------|------|
| B1.1 退出条件可执行 | **勾** | `g-a61a67dd84.exit_condition` = probe + 戳记文件 |
| B1.2 钱优先于 alpha | **勾** | DEV_PLAN：「钱能不能保住 → alpha」；VIP→P1 排序 |
| B1.3 regress 挂了不装完成 | **部分** | 本笔未开假绿 regress epic；全仓测红未标 intent 完成 |

### B2 风控与熔断

| # | 状态 | 证据 |
|---|------|------|
| B2.1 日亏/回撤硬闸 | **勾** | `src/config/risk.py` `LossLimitsConfig.daily_max_loss_usd=10` / `max_drawdown_pct=0.10`；`gatekeeper`/`record_pnl` 存在；相关单测 **45 passed**（`-k gatekeeper\|daily_loss\|drawdown\|circuit`） |
| B2.2 异常停机/降级演练 | **部分** | 有 `src/healthcheck/auto_downgrade.py`、`trading_circuit_breaker.py`；本开程演练 = paper DRY_RUN 双探针间隔 60s 均 PASS（连通软演练）。**未**做实盘断行情硬演练 |
| B2.3 密钥/实盘不进对话默认 | **勾** | 探针强制 `DRY_RUN=true`；实盘开关不在本开程路径 |

### B3 运行稳定

| # | 状态 | 证据 |
|---|------|------|
| B3.1 保活 plist | **部分** | 已装并 loaded：`com.qb.guardian` / `dashboard` / `dual-strategy`。**缺**仓内模板 `qb-data-engine.plist` / `qb-order-gateway.plist` → VIP live 仍 3 error（check_plist_health） |
| B3.2 崩溃可告警 | **部分** | guardian loaded；未在本开程制造崩溃告警样例 |
| B3.3 纸面窗口 | **勾**（薄） | `2026-07-28T04:43:27Z` → `04:44:32Z`（≈65s）两次 paper probe PASS |

### B4 盈利与上线

| # | 状态 | 证据 |
|---|------|------|
| B4.1 纸面门槛 | **部分** | paper probe PASS；**未**对照 DEV_PLAN 全量盈利数字门槛出报告 |
| B4.2 实盘人确认 | **未勾** | 本开程 **不开** 实盘 |
| B4.3 不认 released 张数 | **勾** | 出门句见下 |

---

## Layer2 出门句（诚实 · 2026-07-28）

**可以说**：qb 已在 CCC 上跑通一笔意图的 **L（commit）→ P（paper 探针）→ S（人点 stable）**；风控日亏/回撤配置与相关单测存在；guardian/dashboard 保活已装；纸面短窗探针绿。

**不可以说**：qb 已生产级可盈利、可无人值守实盘、VIP live 全套 plist 齐、或 Layer2 全域 B 表全绿。

**仍冻结**：飞轮 T1–T4 自动 · invent · 实盘开关 Agent 自开。

**下一刀（域内）**：补 `order-gateway`/`data-engine` plist 模板并装齐 → VIP V5 checklist；可选实盘断连演练记 INCIDENTS；B4.1 纸面门槛报告。
