# 方案 · 回测三套收敛（消除循环弃用链）

> 项目：qb · 编号：qb-plan-003 · 状态：部分执行 · 作者：Claude Code W1 · 工具：ccc-plan
> 批准：老板确认转卡 · 2026-08-19
> 创建：2026-08-19 · 更新：2026-08-19
> 关联卡：qb007
> 里程碑：M1 · 回测统一与策略可验证化（子项目 1.3）
> 子项目：1.3 回测三套收敛（消除循环弃用链）
> 环境准备：qb 业务仓 mac2017 可写
> 进度：0/1 (0%)

## 目标

消除回测三套并存的循环弃用链——`src/backtest/__init__.py` 标"废弃，使用根目录 backtest/ 替代"指向 `backtest/`，而 `backtest/run_backtest.py` 标"回测核心已迁移到 src/backtest_engine/runner.py"指向 `src/backtest_engine/`，三方互相推诿没收敛。明确 `src/backtest_engine` 为唯一回测引擎。

## 背景

QB 回测深挖（2026-08-19）发现：三套回测入口互相指向——src/backtest/（标废弃指向 backtest/）、backtest/（run_backtest.py 标迁移到 backtest_engine）、src/backtest_engine/（唯一新引擎）。循环弃用链导致开发者不知该用哪个，且 backtest/data.db 为空（4096 字节无 ohlcv 表，回测实际无法运行）。违反 DRY + 制造认知负担。

## 方案内容

### 1. 明确唯一引擎
- `src/backtest_engine/` 为唯一回测引擎，runner.py 为唯一入口。
- `src/backtest/__init__.py` 的"废弃指向 backtest/"改为"废弃，使用 src/backtest_engine"（修正指向）。
- `backtest/run_backtest.py` 定位为 CLI 包装（调用 src/backtest_engine.runner）或归档。

### 2. 归档 legacy
- `backtest/_legacy/` 加废弃头注，明确不维护。
- 损坏的 IS/OOS 路径（`backtest/_legacy/run_momentum_backtest.py` 的 `from src.strategies.backtest_momentum import` ModuleNotFoundError）标注或修复。

### 3. 入口收敛
- 确认实际跑回测的 CLI 入口（backtest/run_backtest.py 或新 CLI）调用 src/backtest_engine.runner，不指向废弃路径。

## 功能卡

### 回测三套收敛与循环弃用链消除

目标：明确 src/backtest_engine 为唯一回测引擎，消除三套互相指向的循环弃用链。

实现：修正 src/backtest/__init__.py 指向（→backtest_engine）；backtest/run_backtest.py 定位 CLI 包装或归档；backtest/_legacy/ 加废弃头注；统一实际跑回测的入口调用 backtest_engine.runner。

验收：回测入口单一（指向 src/backtest_engine）；无循环弃用指向；qb pytest 全绿。

颗粒度：文件定位/归档改动，1 张卡。

依赖：无（清理类工作，不改引擎逻辑）。

架构位置：回测入口层（src/backtest/ + backtest/ + src/backtest_engine/）。

## 验收标准

- [ ] 回测入口单一，明确指向 src/backtest_engine/runner.py
- [ ] 无循环弃用指向（src/backtest 不再指向 backtest/，backtest/ 不再指向 src/backtest_engine 再被指回）
- [ ] backtest/_legacy/ 有废弃头注，损坏 import 标注或修复
- [ ] qb 业务仓 pytest 全绿

## 备注

属清理类工作（不改引擎逻辑），可与 M1.1（策略接口统一）并行。backtest/data.db 为空问题属 M1.2（真实数据回测通路）范围，本卡只收敛入口不补数据。
