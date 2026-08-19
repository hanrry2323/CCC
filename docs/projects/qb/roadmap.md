# qb 线路图

> 项目：qb · 更新：2026-08-19
> 权威蓝图：业务仓 `docs/DEV_PLAN_v1.1.md`（四级目标 + 版本里程碑）
> 项目本质：跨所加密货币套利交易系统（Python asyncio + Redis Streams + FastAPI/Vue3 Dashboard）
> 双机路径：Mac2017 `/Users/fan/program/apps/qb`（编排 SSOT）、M1 `/Users/apple/program/apps/qb`（对话 cwd）

## 项目本质

单机多 Worker 多策略套利引擎：`DataEngine → WorkerManager(1策略/Worker) → OrderGateway → Exchange`，Redis Streams 串联。核心铁律：Redis Streams 唯一 IPC、OrderGateway 唯一下单、Worker:策略=1:1、DRY_RUN=true 不下单。现状：34k 行代码、data-engine/order-gateway 在线运行，进入停滞维护态（8-12 后无提交）。

## 草案池

- 跨机扩展（2.0.0 cluster）——DEV_PLAN §4 明确门槛未满足前冻结，cluster/ 5526 行代码保留 experimental 位，不进活跃里程碑。仅当 M2 资金门槛（testnet 稳跑≥2周）满足后才评估。

## 里程碑

### M1 · SSOT 收口与地基清理
- 状态：待启动
- 关联方案：qb-plan-002（待立项）
- 描述：承接 plan-001（重构）未落地的 P2/P3 + 部署路径修复。plan-001 标"已完成"但实测版本/回测/部署地基仍脏，需先收口地基才能进 M2 上线门槛。
- 子项目：
  - 1.1 版本单一来源 · 状态：未启动 · 方案：qb-plan-002
  - 1.2 回测三套收敛 · 状态：未启动 · 方案：qb-plan-003
  - 1.3 部署路径修复 · 状态：未启动 · 方案：qb-plan-004
  - 1.4 根目录规划残留清理 · 状态：未启动 · 方案：qb-plan-005
- 退出条件：VERSION/README/STATUS 三处版本一致；回测单一引擎（src/backtest_engine）；Makefile/DEPLOY 路径修正；startup_check --strict 通过。

### M2 · 上线前资金门槛（实盘人确认链路）
- 状态：待启动
- 关联方案：qb-plan-006（待立项）
- 描述：对齐 DEV_PLAN VIP §1.2 + STATUS 上线前清单。从 paper→testnet→小资金 live 的门槛逐级打通，实盘前需人确认。
- 子项目：
  - 2.1 DRY_RUN=true paper 验收跑通 · 状态：未启动 · 方案：qb-plan-006
  - 2.2 testnet DRY_RUN=false + testnet keys 跑通 · 状态：未启动 · 方案：qb-plan-007
  - 2.3 .env 密钥配置 + Telegram 告警实测 · 状态：未启动 · 方案：qb-plan-008
  - 2.4 testnet 连续稳定 ≥2 周 · 状态：未启动 · 方案：qb-plan-009
- 退出条件：三环境 checklist 勾选进 STATUS；testnet 有可复盘 PnL，无未解释双仓/漏单。

### M3 · 回测可视化与策略期望值验证
- 状态：待启动
- 关联方案：qb-plan-010（待立项）
- 描述：收口前主业（hp-kb ship-gate B5）。回测可视化 + 策略期望值可解释，回测 vs 实盘对齐。
- 子项目：
  - 3.1 回测可视化 Dashboard 对齐 · 状态：未启动 · 方案：qb-plan-010
  - 3.2 unified_arb/momentum 策略期望值验证 · 状态：未启动 · 方案：qb-plan-011
  - 3.3 回测 vs 实盘对比基线 · 状态：未启动 · 方案：qb-plan-012
- 退出条件：B5 回测可视化绿；策略可解释 PnL；ship-gate B5 满足。

## 开发路线依赖链

```
M1（地基收口）──► M2（上线门槛）──► M3（回测可视化）
                                        └── 满足后评估 2.0 跨机（冻结）
```
- M1 是 M2 前置（地基脏则门槛不可信）
- M2 是 M3 前置（实盘链路通才有回测对比基线）
- 跨机 2.0 冻结，M2 门槛满足后才评估

## 子项目功能卡拆分（供老板审核，激活后落方案 ## 功能卡段）

### M1 · SSOT 收口与地基清理
- **1.1 版本单一来源**：VERSION 为唯一真源（v1.4.0），README/STATUS 顶部改"以 VERSION 为准"；消除 1.0.0/1.3.12/1.3.15 三源冲突。颗粒度：1 卡。依赖：无。架构位置：项目元数据。
- **1.2 回测三套收敛**：明确 src/backtest_engine 唯一引擎；修正 src/backtest/__init__.py 指向矛盾；backtest/run_backtest.py 定位 CLI 包装或归档；backtest/_legacy 归档。颗粒度：1-2 卡。依赖：无。架构位置：回测层。
- **1.3 部署路径修复**：Makefile/DEPLOY_MAC2017 废弃路径（/projects/qb→/apps/qb）；docker-compose cluster 架构与单机 VIP 冲突决策（删 or experimental 标注）；Python 3.11/3.12 口径统一。颗粒度：1-2 卡。依赖：无。架构位置：部署层。
- **1.4 根目录规划残留清理**：task_plan/progress/findings 并入 docs 或废弃；tests 一次性探测测试（test_ccc_loop_r3_util 等）归档。颗粒度：1 卡。依赖：无。架构位置：项目卫生。

### M2 · 上线前资金门槛
- **2.1 paper 验收**：DRY_RUN=true paper 跑通，无双开/风控有效。颗粒度：1 卡。依赖：M1。架构位置：DataEngine→Worker→Gateway 纸面链路。
- **2.2 testnet 跑通**：DRY_RUN=false + testnet keys，真实下单 testnet。颗粒度：1 卡。依赖：2.1。架构位置：OrderGateway testnet 适配。
- **2.3 密钥+告警**：.env（HMAC/JWT/ADMIN_PASS/TELEGRAM/METRICS_TOKEN）就位 + Telegram 告警实测。颗粒度：1 卡。依赖：2.2。架构位置：配置/告警层。
- **2.4 testnet 稳跑**：连续稳定 ≥2 周，有可复盘 PnL。颗粒度：1 卡（观察卡）。依赖：2.3。架构位置：运行态。

### M3 · 回测可视化与策略期望值
- **3.1 回测可视化**：backtest_engine 产物 → 前端 backtest 视图对齐。颗粒度：1-2 卡。依赖：M1.2 回测收敛。架构位置：Dashboard 回测视图。
- **3.2 策略期望值验证**：unified_arb/momentum 费用/滑点/敞口模型可信，净 edge 对齐回测。颗粒度：1-2 卡。依赖：3.1。架构位置：策略层。
- **3.3 回测 vs 实盘基线**：同库存储 + mode 区分对比。颗粒度：1 卡。依赖：3.2 + M2.2。架构位置：回测/实盘对比。

## 备注

- 本 roadmap 承接业务仓 DEV_PLAN_v1.1 蓝图，把四级目标映射成 CCC 标准化里程碑。
- 方案编号 qb-plan-002 起续编（001 已用于 plan-001 重构）。
- 激活顺序：老板逐个指定子项目 → 1:1 建方案 → 转卡 → Engine 开发。M1 优先（地基收口是 M2/M3 前置）。
- plan-001（重构）标已完成但 P2/P3 未落地，其遗留工作并入 M1，不在本 roadmap 单列。
