# qxo Lessons — 镜像归档

> 归档规则：每次完成 v6.0.3o+ 风格的 verify 闭环后，把 `~/program/qx-observer/docs/lessons.md` 表中本项目相关 lessons 同步到此处。
> 仅同步**单项目特定 lessons**（跨项目通用 lessons 留在 qx-observer/docs/lessons.md）。
> 当前镜像：Lesson 18（V9.S1a · QbAgentRunner 接入）。

## 镜像 lessons

### Lesson 18 · V9.S1a · QbAgentRunner 接入 (2026-07-14)

**原始条目**：见 `~/program/qx-observer/docs/lessons.md` line 7 (本文件镜像后变为 line 8)。

**关键摘要**（项目特定）：

新 agent runner 接入踩 3 个坑：

1. **真正 wiring 点是 `MultiAgentScheduler.dispatch()`，不是 `L2Adapter.execute()`**。
   `L2Adapter.execute()` 内部硬编 `LoopRunner()` (Claude CLI)，`routing_type` 字段被读取但**不参与选 runner**。
   smoke 必须直接调 `MultiAgentScheduler.dispatch(task)` → `future.result(timeout=15)` 拿 L1 message 流，
   才能真正驱动 `get_runner('qb') → QbAgentRunner.run()`。

2. **新 runner 复用 `AgentRunner` 抽象而非 `ExternalCLIRunner`**。
   - prompt 是 JSON → 多 CLI 参数（symbol/strategy/fee/sweep）→ 自己继承 `AgentRunner` + `_parse_prompt_args` 拆解
   - 输出是 `output/backtest_summary.json` 文件（不是 stdout）→ 必须自己读文件、塞进 `L1Message.payload["summary"]`
   - `ExternalCLIRunner` 把整段 prompt 当单 arg 传 CLI，不匹配语义

3. **mock 必须放 `<workspace>/backtest/run_backtest.py`**。
   `QbAgentRunner` 硬编 `QB_RUNNER_PATH = "backtest/run_backtest.py"` (qb_runner.py:33)，
   不是 `<workspace>/run_backtest.py`。第一版 smoke 把 mock 放错位置，触发
   `qb exit=2: can't open file '<workspace>/backtest/run_backtest.py'` L1[error]。

**适用范围**（W7 接力 — xianyu / ClawCinema runner 沿用）：
- xianyu (内容生成) — prompt 是 markdown 文本 + 输出是 stdout → 可以复用 `ExternalCLIRunner`
- ClawCinema (影视墙渲染) — prompt 是 JSON + 输出是 MP4 文件 → 沿用 `QbAgentRunner` 模式（继承 `AgentRunner`）

**smoke 模板**（V9.S1a 已沉淀）：
- 13 个 PASS check（l1_trace 存在 / 6 message / 5 stage / result.ok=True / qb_args / summary / summary 文件 / return_pct / task_id 传播）
- 3 阶段：幂等护栏 → 准备 mock（backtest/run_backtest.py + output/） → 驱动 MultiAgentScheduler