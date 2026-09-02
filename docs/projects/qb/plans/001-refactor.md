# 方案 · qb 项目重构——历史垃圾清理 + SSOT 统一

> 项目：qb · 编号：qb-plan-001 · 状态：已完成 · 作者：老板 · 工具：Codex
> 创建：2026-08-03 · 更新：2026-08-10
>  关联卡：已归档（原引用 qb001, qb002, qb003, qb004, qb005, qb006 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：无
> 进度：6/6 (100%)
> 迁移自：qx-map `__archive__/decisions/qb-refactor-方案-2026-08-03.md`
> 决策人：老板 · 记录/管理：Codex · 执行：Trae · 验收：Codex
> 关联：`command-post/intents.md`（INT-121）
> 性质：qb 重构唯一执行依据；与旧 qb 文档冲突处，以本方案为准。

## 一、背景与诊断（2026-08-03 实测）

老板定调：qb 历史垃圾多、信息过时，需要重构。Codex 实测取证如下：

| 项 | 实测值 | 判断 |
|----|--------|------|
| 代码规模 | 303 个 py 文件 / 48,406 行（src+tests+backtest） | 正常，业务主体在 `src/` |
| git 历史 | 716 commits，大量 CCC DoD 自动提交（`prop-*`） | 历史噪音，不删库，只收敛工作树 |
| 脚本 | 81 项，含 `ccc_loop_r3`、`ccc_open_intent_r7/r8/r10`、`eff23*`、`*probe*` 等一次性探测脚本 | 一次性垃圾，归档 |
| 回测体系 | 两套并存：`backtest/`（含 `_legacy`、`data.db`、`db/`）+ `src/backtest_engine`（optimizer/replay/report/runner） | 新旧重叠，收敛到新体系 |
| 工具目录 | `.opencode` 61M（纯 node_modules）、`.ccc` 23M（quarantines 10M）、另 .claude/.codex/.cursor/.workbuddy/.harness | 缓存/产线杂物，收敛 |
| 文档一致性 | VERSION=v1.4.0 vs README=1.0.0 vs STATUS=1.3.12/1.3.15；`docs/_archive` 9 份旧计划；根目录另存 findings/progress/task_plan | 过时 + 多版本，统一 SSOT |
| 运行面 | qb-data-engine / qb-order-gateway / qb-dual-strategy / qb-guardian 常驻（plist） | 红线：重构零接触运行面 |
| 数据 | `data/qb.db`、`backtest/data.db`、`backtest/db/backtest.db` | 红线：数据文件不动 |

## 二、终态一句话

qb = 一套文档（版本单一来源）、一套回测（`src/backtest_engine`）、一个干净工作树（无一次性脚本/缓存/旧计划），业务代码 `src/` 与测试全保留，运行服务与数据零接触。

## 三、执行阶段（Trae 按序执行，Codex 阶段验收）

### P0 基线冻结
1. 跑 `git status` 记录脏树现状；确认 plist 四服务 PID 快照。
2. 跑基线 `pytest tests/ -q`（当前 66 个测试文件）记录绿/红基线。
3. 产出「保留 / 归档 / 删除」三类清单（本方案第四节为默认清单，Trae 可补充但须写进执行报告）。

### P1 垃圾清理（不动业务代码）
1. 物理删除仅限缓存类：`.opencode/node_modules`、`arbitrage_trading.egg-info`、全部 `__pycache__`、`.pytest_cache`、`.ruff_cache`。
2. 一次性脚本移入 `docs/_archive/scripts-2026-08-03/`：`ccc_*`、`eff23*`、`*probe*`、`oncall_check.py`、`check_plist_health.py` 等判定为一次性/巡检类的脚本（保留仍在 plist/文档引用的运维脚本）。
3. `backtest/_legacy/` 移入 `docs/_archive/legacy-backtest-2026-08-03/`；`backtest/` 根目录的 `data.db`、`db/`、`results/`、`sample_data/` 仅登记不动（数据红线）。
4. `.ccc/board/_archive-*` 合并去重后保留一份；`.opencode`、`.workbuddy` 判断无用则整体移入 `docs/_archive/tools-2026-08-03/`（先移后删，留 7 天观察）。

### P2 文档 SSOT 统一
1. 版本单一来源：`VERSION`（现 v1.4.0）为唯一真源，README/STATUS 顶部改为「版本以 VERSION 为准」，消除 1.0.0/1.3.12/1.3.15 冲突。
2. 根目录 `findings.md`、`progress.md`、`task_plan.md` 并入 `docs/`（或标废弃指向 docs/plans/），根目录只留 README/CHANGELOG/STATUS。
3. `docs/_archive/` 旧计划（DEV_PLAN_v1、QUANT_DEV_PLAN、development_plan、project_management_plan 等 9 份）统一加「已废弃，以方案为准」头注，不物理删除。
4. STATUS.md 更新至与 VERSION 一致，模块状态表核对 `src/` 实际目录。

### P3 代码整合（低风险，须逐项过验收）
1. `src/backtest_engine` 为唯一回测实现；`backtest/run_backtest.py` 与 `src/backtest/`（data_loader/param_sweep/strategy_runner）判定为旧入口的，移入归档并更新引用。
2. 收敛重复工具：`scripts/format_utils.py`、`parse_pct` 类重复函数统一收口到 `src/utils/`，脚本侧改为引用。
3. 不引入新依赖、不改策略逻辑、不重构业务模块内部实现。

### P4 验收（Codex 独立取证）
1. `pytest tests/ -q` 与 P0 基线持平或更优。
2. `python scripts/startup_check.py --strict` 通过。
3. plist 四服务 PID 与 P0 快照一致（未被重启）。
4. 三类清单逐项核对：保留项在位、归档项可寻址、删除项仅缓存类。
5. VERSION/README/STATUS 版本一致；根目录无游离计划文档。

## 四、红线（永久）

1. 不碰 `data/*.db` 与 `backtest` 数据文件。
2. 不碰运行中的 qb 服务（四个 plist 进程）。
3. 不删 `src/` 生产模块、不删 `tests/`、不删 `config/`。
4. 不引入新依赖、不动 `.env` 与密钥文件。
5. 删除一律先归档（可回滚），物理删除仅限缓存类（node_modules/__pycache__/egg-info）。

## 五、交付物

1. qb 仓一个 commit（或分阶段 4 个 commit，信息含 `qb-refactor-2026-08-03` 关键字）。
2. 执行报告：三类清单 + 基线对比 + 验收证据，写回本决策档「执行记录」区。
3. Codex 验收通过后，INT-121 状态改「已回写」。
