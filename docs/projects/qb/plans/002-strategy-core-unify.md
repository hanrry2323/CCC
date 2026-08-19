# 方案 · 策略接口统一（StrategyCore 共享核心 · R14）

> 项目：qb · 编号：qb-plan-002 · 状态：待验收 · 作者：Claude Code W1 · 工具：ccc-plan
> 批准：老板确认转卡 · 2026-08-19
> 创建：2026-08-19 · 更新：2026-08-19
> 关联卡：qb008
> 里程碑：M1 · 回测统一与策略可验证化（子项目 1.1）
> 子项目：1.1 策略接口统一（StrategyCore 共享核心）
> 环境准备：qb 业务仓 mac2017 可写 + 现有回测引擎可跑（src/backtest_engine）
> 进度：1/1 (100%)

## 目标

收敛两条断裂管线——回测引擎用 `OHLCVBar`+`on_bar/generate`，实盘策略用 `MarketDataEvent`+`on_market_data`，接口不兼容。参照 QuantHive R14（回测=实盘同代码，禁双轨），抽 StrategyCore 共享核心类，让 unified_arb/momentum 等实盘主力策略能用回测引擎跑。

## 背景

QB 回测深挖（2026-08-19）发现致命缺陷：unified_arb（主套利策略）和 momentum（实盘）**不能用 BacktestRunner 跑**（接收 MarketDataEvent 非 OHLCVBar），只能用 Mock 回测（合成随机数据、无费率无滑点）。违反 QuantHive backtest-canon R14（回测=实盘同代码）。UnifiedSignal 桥接层只适配已实现 OHLCV `generate(bar)` 的策略，对 unified_arb 无效（其 generate_signals 返回 []）。

## 方案内容

### 1. 抽 StrategyCore 共享核心
- 参照 QuantHive StrategyCore 模式：抽策略核心逻辑为纯函数/类，不依赖数据模型（OHLCVBar vs MarketDataEvent）。
- 策略核心（信号生成逻辑：价差计算/阈值判断/净机会扣费）与数据适配解耦。

### 2. 数据适配层
- 回测适配：MarketDataEvent→OHLCVBar 回放（或回测引擎适配 MarketDataEvent 流）。
- 策略实现 `on_bar/generate`（回测协议）或回测引擎支持 MarketDataEvent 回放——二选一，选改动最小路径。

### 3. unified_arb/momentum 适配回测
- 让 unified_arb 的三套利计算（跨所价差/永续基差/资金费率）能用历史数据回测。
- momentum 均值回归逻辑适配回测协议。

## 功能卡

### 策略接口统一与 StrategyCore 抽取

目标：消除回测/实盘双轨，让 unified_arb/momentum 可用回测引擎跑（R14）。

实现：抽 StrategyCore 共享核心（信号逻辑与数据模型解耦）+ 数据适配层（MarketDataEvent↔OHLCVBar）+ unified_arb/momentum 适配回测协议。

验收：unified_arb 用真实历史数据跑通 BacktestRunner（非 Mock）；回测策略代码=实盘 Worker 代码（R14）；现有 buy_hold/ma_cross/bollinger/rsi 回测不回归。

颗粒度：核心重构（base.py + runner.py StrategyProtocol + unified_arb/momentum 适配），2-3 张卡。

依赖：无（M1.1 是回测统一起点）。

架构位置：strategies/base.py（StrategyBase 契约）+ backtest_engine/runner.py（StrategyProtocol）+ strategies/unified_arb.py、momentum.py。

## 验收标准

- [ ] unified_arb 可用 BacktestRunner + 真实历史数据跑通（非 generate_mock_ticks 合成数据）
- [ ] 回测策略代码与实盘 Worker 同一套逻辑（R14，无"回测一份代码实盘另一份"双轨）
- [ ] 现有 BACKTEST_STRATEGIES（buy_hold/ma_cross/bollinger/rsi）回测结果不回归（行为等价）
- [ ] qb 业务仓 pytest 全绿（含回测引擎单测）

## 备注

参照 QuantHive `docs/backtest-canon.md` R14 + `docs/research/r14-strategy-migration-gap-20260813.md`（StrategyCore 共享核心迁移范式）。M1.2 真实数据回测通路依赖本卡（1.1 完成后才能接真实数据）。
