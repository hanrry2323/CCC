# 任务卡 T3-R · 看板状态归一（Claude Code 执行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：已关闭 · 日期：2026-08-02
> 前置：T3（已验收通过）

## 背景（验收复验发现）

状态带括号变体（如 `打回（原因）`、`待分派（实现）`、`已回写（有条件）`）未被归一：状态桶与线路图计数漏计（实测 T1=打回、T4=待分派 两卡未入桶，5 卡只数出 3）。契约（意图表校验 R4）明确允许括号变体，看板必须**按基础态归桶、明细保留全串**。

## 目标

board 状态聚合归一：带括号状态变体按基础态（括号前）归桶；明细/列表保留全串显示；未知态归「未知」桶；测试锁定。

## 红线（先看）

1. 不删除任何文件；不碰旧代码；不碰运行面；不读不写 qx-map / 外脑。
2. 只改 `server/board/` 与 `server/tests/`；验收标准不可自行解释；完成必须提交（真实 commit）。
3. 工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

## 范围

- 修改：`server/board/`（loader 或 queries 的状态归一，与 project/executor 已用的括号剥离逻辑一致）、`server/tests/test_board_*.py`。
- 不动：`server/engine/`、`server/web/` 其余、`server/relay/`。

## 步骤

1. 状态归一：解析/计数时对「状态」取括号前基础态（复用 `_strip_parenthetical` 同款逻辑），未知态归「未知」桶。
2. 明细保留全串：realtime / recent 项内 `state` 仍为原文（含括号）。
3. 测试：新增变体用例——`待分派（实现）` / `打回（原因）` / `已回写（有条件）` 归正确桶；未知态进「未知」桶；明细保留全串。
4. 重新导出：`python3 -m server.board.export`，确认 T1=打回、T4=待分派 正确入桶，5 卡计数与卡片数一致。
5. 提交 `chore(board):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 状态桶计数总和 = 卡片总数（含括号变体与未知态）。
2. 明细保留全串；测试覆盖三种变体 + 未知态。
3. `board.js` 重导出后 T1/T4 正确入桶；既有测试不回归。
4. 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码 / 运行面 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、重导出验证输出、commit hash、验收自检对照表。

按契约 §3（2026-08-02 补充纪律）：回写时同步更新本卡卡头「状态」——接单改「执行中」，回写改「已回写」；验收后由验收席改「已关闭」。禁止只写回写区不动状态行。

## 回写区

**执行体**：Claude Code（CLI）  
**日期**：2026-08-02  
**实现 commit**：`1a88e80`（`chore(board):` 前缀 · 5 文件 · 106 insertions）

> 卡头状态已按契约 §3 纪律同步：待分派 → 已回写（本卡执行完成，待验收席改已关闭）。

### 结果摘要

board 状态聚合归一：新增 `base_state()`（括号前基础态归一），三视图 / 线路图 / 徽章按基础态归桶、明细保留原文全串，未知态归「未知」桶；三变体 + 未知态测试锁定，74 用例全绿，已提交入库。

### 测试输出

```
$ python3 -m pytest server/tests/ -v --tb=short
collected 74 items
server/tests/test_board_export.py ...                                    [  4%]
server/tests/test_board_loader.py .......                               [ 15%]
server/tests/test_board_queries.py .............                        [ 32%]
server/tests/test_engine_dispatch.py .........                          [ 44%]
server/tests/test_engine_main.py ......                                 [ 51%]
server/tests/test_engine_task.py ........                               [ 62%]
server/tests/test_skeleton.py ...........................                [100%]
============================== 74 passed in 0.06s ==============================
```

- 新增 `TestStateNormalization`：6 passed（三变体归桶 / 明细全串 / 线路图+徽章计数 / 项目状态分布 / 未知桶 / recent 全串）
- 新增 loader 变体用例：`状态：打回（原因）` 明细保留全串 + 基础态=打回隐含打回次数 1
- 既有 67 用例不回归

### 重导出验证

```
$ python3 -c "from server.board.models import base_state; ..."
'打回（原因）' -> '打回' · '待分派（实现）' -> '待分派' · '已回写（有条件）' -> '已回写' · ''/'未知' -> '未知'

$ python3 -m server.board.export        # 写回后（T3-R=已回写）
exported 5 cards -> server/web/data/board.js
states: 待分派 0 · 执行中 0 · 已回写 1 · 已关闭 3 · 打回 1   # 桶总和 5 = 卡片数 5
```

### 硬编码扫描（S1–S4 · 零字面量）

范围同前：`server/` 生产代码/模板，排除 `tests/` 与 executors 配置。改后 `server/board/` 生产代码 `/Users`、字面端口、模型名、工具名 全 **0 命中**；`py_compile` OK。

### 验收自检对照表

| # | 验收标准 | 状态 |
|---|----------|------|
| 1 | 状态桶计数总和 = 卡片总数（含括号变体与未知态） | ✅ 桶总和 5 = 卡数 5；变体经 base_state 入桶、未知态入「未知」桶 |
| 2 | 明细保留全串；测试覆盖三种变体 + 未知态 | ✅ `state` 字段保留原文；TestStateNormalization 6 用例 |
| 3 | board.js 重导出后 T1/T4 正确入桶；既有测试不回归 | ✅ T1=打回入桶；T4 卡已由管理席删除（`8d96b92`）；5 卡全入桶；67 旧用例不回归 |
| 4 | 零硬编码；真实提交；工作树仅剩 2 个预存项；未碰旧代码/运行面/外脑 | ✅ S1–S4 零命中；`1a88e80`；工作树剩 decided.json(M) + _update_handoff.py(??)；`scripts/` 等零改动；未启动/注册；未读外脑 |

### 遗留/不确定项

1. **当前卡头状态已为基础态**（管理席 `5e33df2` 归一了数据层）：本次为代码层归一，确保未来括号变体也正确入桶；复验背景中「T4=待分派」对应卡已被删除（`8d96b92`）。
2. **打回次数无显式字段时仅从状态=打回 隐含 1 次**：多次打回需卡片显式 `打回次数：N`。
3. **未知态在路线图无桶**：base_state 归一后仍非五态的值归实时视图「未知」桶；线路图（占位）不计数该值（P3 定义）。
