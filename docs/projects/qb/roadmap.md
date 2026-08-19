# qb 线路图

> 项目：qb · 更新：2026-08-19
> 权威蓝图：业务仓 `docs/DEV_PLAN_v1.1.md`（四级目标）
> 参照标杆：QuantHive `docs/backtest-canon.md`（回测准则 R12/R13/R14 + 置信度四维）
> 项目本质：跨所加密货币套利交易系统（Python asyncio + Redis Streams + FastAPI/Vue3 Dashboard）
> 双机路径：Mac2017 `/Users/fan/program/apps/qb`（编排 SSOT）、M1 `/Users/apple/program/apps/qb`（对话 cwd）

## 项目本质

单机多 Worker 多策略套利引擎：`DataEngine → WorkerManager(1策略/Worker) → OrderGateway → Exchange`，Redis Streams 串联。核心铁律：Redis Streams 唯一 IPC、OrderGateway 唯一下单、Worker:策略=1:1、DRY_RUN=true 不下单。现状：34k 行代码、data-engine/order-gateway 在线运行。

## 与 QuantHive 的关系（关键认知）

| | QuantHive | QB |
|--|-----------|-----|
| 定位 | 研究驱动（策略证伪/方法论） | 工程化套利引擎（执行链路） |
| 回测 | R14 回测=实盘同代码（StrategyCore 共享）、R13 基准对比、置信度四维、40 方向全证伪 | ❌ 两条断裂管线、Mock 回测、无基准无置信度 |
| 策略 | DCA/MA/Bollinger/Grid/TWAP 等已 R14 统一 | unified_arb/momentum 实盘主力不能回测；4 简单策略能回测无实盘 |

**QB 应参照 QuantHive 的回测准则（backtest-canon.md），把割裂的两条管线收敛为 R14 统一管线，并补齐 R13 基准对比 + 置信度评估。** 这是 QB roadmap 的核心主线。

## 草案池

- 跨机扩展（2.0.0 cluster）——DEV_PLAN §4 明确门槛未满足前冻结，cluster/ 5526 行代码保留 experimental 位，不进活跃里程碑。仅当 M3 验证有真实 alpha + testnet 稳跑≥2 周满足后才评估。
- 组合 ML/高维因子（过拟合风险高，需更严协议，M3 有 alpha 后再议）

## 里程碑

### M1 · 回测统一与策略可验证化（R14 收敛）
- 状态：待启动
- 关联方案：qb-plan-002（待立项）
- 描述：**核心主线**。收敛两条断裂管线（OHLCVBar 回测 vs MarketDataEvent 实盘）为 R14 统一管线——回测=实盘同代码，禁双轨。让 unified_arb/momentum 等实盘主力策略能用真实数据回测。对照 QuantHive R14 迁移（StrategyCore 共享核心类）。
- 子项目：
  - 1.1 策略接口统一（StrategyCore 共享核心） · 状态：未启动 · 方案：qb-plan-002
  - 1.2 真实数据回测通路（替代 Mock 合成数据） · 状态：未启动 · 方案：qb-plan-003
  - 1.3 回测三套收敛（消除循环弃用链） · 状态：未启动 · 方案：qb-plan-004
  - 1.4 基准对比落地（R13 buy-and-hold） · 状态：未启动 · 方案：qb-plan-005
- 退出条件：unified_arb/momentum 可用真实历史数据回测；回测策略代码=实盘 Worker 代码（R14）；回测报告附 buy-and-hold 基准（R13）；Mock 回测废弃。

### M2 · 策略 alpha 验证与防过拟合（置信度四维）
- 状态：待启动
- 关联方案：qb-plan-006（待立项）
- 描述：**策略选择的核心**。M1 能回测后，对实盘策略做 alpha 验证——基准对比/置信度/稳定性/防过拟合四维评估，证伪或采信。参照 QuantHive 40 方向全证伪的严谨度。
- 子项目：
  - 2.1 IS/OOS 分段回测 · 状态：未启动 · 方案：qb-plan-006
  - 2.2 Monte Carlo bootstrap 置信度（≥1000 次） · 状态：未启动 · 方案：qb-plan-007
  - 2.3 参数稳定性扫描（±10% 不崩） · 状态：未启动 · 方案：qb-plan-008
  - 2.4 事件归因与脏币过滤（防假 alpha） · 状态：未启动 · 方案：qb-plan-009
  - 2.5 真实费率/滑点校准（从实际成交反推） · 状态：未启动 · 方案：qb-plan-010
- 退出条件：每个实盘策略有 alpha verdict（证伪 or 采信+置信区间）；无"数字过门"假 alpha（扣事件归因）；真实费率/滑点建模。

### M3 · 上线前资金门槛与回测可视化
- 状态：待启动
- 关联方案：qb-plan-011（待立项）
- 描述：M2 有采信策略后，打通实盘链路门槛（paper→testnet→密钥→稳跑）+ 回测可视化 Dashboard。合并 DEV_PLAN VIP + 上线前清单 + ship-gate B5。
- 子项目：
  - 3.1 paper→testnet 门槛（DRY_RUN 切换+testnet keys） · 状态：未启动 · 方案：qb-plan-011
  - 3.2 .env 密钥+Telegram 告警 · 状态：未启动 · 方案：qb-plan-012
  - 3.3 testnet 连续稳跑≥2 周 · 状态：未启动 · 方案：qb-plan-013
  - 3.4 回测可视化 Dashboard（backtest_engine 产物→前端） · 状态：未启动 · 方案：qb-plan-014
  - 3.5 回测 vs 实盘对比基线（同库 mode 区分） · 状态：未启动 · 方案：qb-plan-015
- 退出条件：三环境 checklist 勾选进 STATUS；testnet 有可复盘 PnL 无双仓/漏单；回测可视化绿；ship-gate B5 满足。

## 开发路线依赖链

```
M1（回测统一 R14）──► M2（alpha 验证 置信度四维）──► M3（上线门槛+可视化）
                                                           └── 满足后评估 2.0 跨机（冻结）
```
- M1 是 M2 前置（不能回测就无法验证 alpha）
- M2 是 M3 前置（无采信策略则实盘无意义，可能"市场无简单 alpha"需战略决策）
- 跨机 2.0 冻结，M2 有 alpha + M3 testnet 稳跑后才评估

## 子项目功能卡拆分（供老板审核，激活后落方案 ## 功能卡段）

### M1 · 回测统一与策略可验证化（R14 收敛）

- **1.1 策略接口统一**：收敛两条断裂管线。回测引擎用 OHLCVBar+on_bar/generate，实盘策略用 MarketDataEvent+on_market_data，接口不兼容。参照 QuantHive StrategyCore——抽共享核心类，回测/实盘调用同一逻辑。unified_arb/momentum 适配回测协议（实现 on_bar/generate 或回测引擎适配 MarketDataEvent 回放）。颗粒度：2-3 卡。依赖：无。架构位置：strategies/base.py + backtest_engine/runner.py StrategyProtocol。
- **1.2 真实数据回测通路**：现 unified_arb 只能 Mock 回测（generate_mock_ticks 合成随机数据）。补真实历史数据回测——DataEngine 录制的市场数据或交易所历史 K 线导入 OHLCVBar。颗粒度：1-2 卡。依赖：1.1。架构位置：数据加载层。
- **1.3 回测三套收敛**：src/backtest/__init__.py（标废弃指向 backtest/）↔ backtest/run_backtest.py（标迁移到 src/backtest_engine）↔ src/backtest_engine/——循环弃用链。明确 src/backtest_engine 为唯一引擎，其余归档或定位为 CLI 包装。颗粒度：1 卡。依赖：无。架构位置：回测入口。
- **1.4 基准对比落地（R13）**：回测报告必须附 buy-and-hold 基准（QuantHive R13）。现 BacktestResult 无基准对比字段。补基准策略 + 报告对比展示。颗粒度：1 卡。依赖：1.1。架构位置：backtest_engine/report.py + recorder.py。

### M2 · 策略 alpha 验证与防过拟合（置信度四维）

- **2.1 IS/OOS 分段回测**：现 optimizer.py 无 IS/OOS/walk-forward（经典过拟合风险）。补样本内训练+样本外验证分段。颗粒度：1-2 卡。依赖：M1。架构位置：backtest_engine/optimizer.py。
- **2.2 Monte Carlo bootstrap**：QuantHive 最低标准≥1000 次 bootstrap 置信度。现无。补 bootstrap 重采样得置信区间。颗粒度：1 卡。依赖：2.1。架构位置：backtest_engine/recorder.py + 新 stats 模块。
- **2.3 参数稳定性扫描**：±10% 参数不崩（QuantHive 最低标准）。补参数敏感度分析报告。颗粒度：1 卡。依赖：2.1。架构位置：backtest_engine/optimizer.py。
- **2.4 事件归因与脏币过滤**：QuantHive 教训——"数字过门"扣单币暴涨事件后全转负（WPAY/ZEC/NEAR）。补事件归因（扣事件币看真实 alpha）+ 脏币过滤（62 干净币池方法论）。颗粒度：1-2 卡。依赖：M1。架构位置：策略评估层。
- **2.5 真实费率/滑点校准**：现 slippage_pct 默认 0（无滑点）、commission 0.1% 可调但未从实际成交反推校准。补从实盘成交反推校准滑点/费率。颗粒度：1 卡。依赖：M1。架构位置：backtest_engine/runner.py _execute_signal。

### M3 · 上线前资金门槛与回测可视化

- **3.1 paper→testnet 门槛**：DRY_RUN=true paper→DRY_RUN=false testnet keys 跑通。颗粒度：1 卡。依赖：M2。架构位置：OrderGateway testnet 适配。
- **3.2 .env 密钥+告警**：HMAC/JWT/ADMIN_PASS/TELEGRAM/METRICS_TOKEN 就位 + Telegram 告警实测。颗粒度：1 卡。依赖：3.1。架构位置：配置/告警层。
- **3.3 testnet 稳跑**：连续稳定≥2 周，有可复盘 PnL，无未解释双仓/漏单。颗粒度：1 卡（观察卡）。依赖：3.2。架构位置：运行态。
- **3.4 回测可视化**：backtest_engine 产物（HTML 报告）→ 前端 backtest 视图对齐。颗粒度：1-2 卡。依赖：M1。架构位置：Dashboard 回测视图。
- **3.5 回测 vs 实盘基线**：同库存储 + mode 区分对比（QuantHive 实盘反馈闭环）。颗粒度：1 卡。依赖：3.3+M1。架构位置：回测/实盘对比。

## 战略风险提示（给老板）

参照 QuantHive 结论——**"现货+永续简单策略在真实费率+事件归因下无超额 alpha"**（40 方向全证伪）。QB 的 unified_arb（跨所价差/永续基差/资金费率三套利）可能面临同样问题。M2 验证后若证伪，需老板战略决策：
1. 接受"无 alpha 阶段"，聚焦系统建设（QuantHive 已转向）
2. 探索结构性方向（做市/期权/DeFi 链上，需基础设施）
3. 深水区（组合 ML/高维因子，过拟合风险高需更严协议）

M2 是战略分水岭——有 alpha 则进 M3 上线，无 alpha 则转向。**激活 M1/M2 的价值不在"上线赚钱"，而在用 QuantHive 级严谨度验证 QB 策略到底有没有 alpha**，避免带着假 alpha 上实盘。

## 备注

- 本 roadmap 承接业务仓 DEV_PLAN_v1.1 蓝图 + 参照 QuantHive backtest-canon.md 回测准则，把核心从"地基收口"转向"回测统一+策略验证"。
- 方案编号 qb-plan-002 起续编（001 已用于 plan-001 重构）。
- 激活顺序：老板逐个指定子项目 → 1:1 建方案 → 转卡 → Engine 开发。**M1 优先**（回测统一是 M2 验证的前置，M1 不做则 alpha 验证无意义）。
- plan-001（重构）标已完成但版本/回测/部署地基未落地，其遗留并入 M1.3（回测收敛）+ 独立的 SSOT 地基清理（可作为 M1 前置快速任务，不单列里程碑）。
- 交叉复审协议（QuantHive 2026-08-18 定稿）：策略/回测结论一律盲审化复审，禁无复审采信。M2 alpha verdict 应走此协议。
