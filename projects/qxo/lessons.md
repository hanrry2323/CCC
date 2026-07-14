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

### Lesson 26 · V9.S0 · dispatch 资源洪水 + 协作诊断 (2026-07-02)

**原始条目**：见 `~/program/qx-observer/docs/lessons.md` Lesson 26 row。

**完整复盘**：

#### 1. 背景
2026-07-02 在 30 commits 日触发 daily-snapshot 自动分发。`dispatch_snapshot()` 一次性 `create_task` 55 个 Claude 子进程，每个 fork 出 ~300MB（Python runtime + 历史 imports）。M1 8GB 物理内存 55×300MB = 16.5GB，触发 swap 抖动，uvicorn 主进程 OOM kill，dispatch 链路完全挂掉。

#### 2. 根因（两层）
- **第一层（修真因）**：`dispatch_snapshot` 没有任何并发限流。`for ci in project_snap.review_items: asyncio.create_task(_add_decision_safe(...))` 直接把 55 个 task 丢进事件循环，所有 task 同时 await DB。
- **第二层（缺兜底）**：`app/services/executor/worker.py` 没有全局 worker pool semaphore。其他调用路径（如 CCC Engine 调度任务）也会击穿同样的内存炸弹。

#### 3. 诊断协作
单视角不够。两个 agent 交叉对比才完整：

- **Claude Code（修真因视角）**：看 dispatch 循环 → 找到 55 并发元凶 → 推荐方案 1（dispatch 边界 semaphore）+ 方案 2（worker pool 兜底）。
- **qxo-CC（二级 bug 视角）**：grep 全网 `asyncio.run` / `dict.get` / 阈值常量 → 发现 3 个二级 bug：
  1. `_submit_to_queue_safe` 在已有 loop 中调用 `asyncio.run()` 死锁 30s（用户已察觉但当时没修）
  2. `_on_task_failed` handler 遇到 legacy `retry_count=NULL` 行 → `None < int` TypeError → 静默挂掉 → dead task 永远不升级
  3. `check_dead_pileup` 阈值默认 5 太敏感 → 每 30s 重复 alert + `purge_dead_pileup(keep=10)` 把正在排查的 dead 证据误删

**关键认知**：两个 agent 看的不是同一份代码 → 单 Claude Code 修真因就停手 → 漏 3 个二级 bug；单 qxo-CC 找二级 bug 不知哪个是真因。**交叉对比互补盲点**。

#### 4. 修复（方案 1 + 方案 2 双保险 + 3 个二级 bug）

| Phase | 改动 | Commit |
|-------|------|--------|
| 1 | `dispatch_snapshot` 加 `asyncio.Semaphore(3)` gate inner closures；executor/worker.py 加 `_worker_semaphore` cap 4 | `f6b5dd8` |
| 2 | `_submit_to_queue_safe` 检测 running loop；`_add_decision_safe` 加 async sibling；`_on_task_failed` 加 `is None → 0/3` 守卫；`check_dead_pileup` 阈值 5 → 100 + 加 `dead_pileup_gc()` 显式入口 | `d1ae1b8` |
| 3 | SKILL.md 加 "Concurrency limit" 警告段 + Lesson 26 沉淀 | (本 commit) |

测试覆盖：+6 cases（WP-05 peak ≤ 3 / PS-04 None guard / PS-05 dead_pileup_gc）→ 30/30 PASS。

#### 5. 教训

1. **"测试通过 ≠ 没问题"**：单元测试 mock 一切外部依赖（boss_service / task_service / DB），看不见物理资源限制。`dispatch_snapshot` 之前所有测试都 PASS，但实际跑就 OOM。
2. **必须看物理资源**：dispatch 类批任务必先算 `(N tasks × per_task_cost) ≤ 80% × physical_RAM` 再启并发。per_task_cost 估 300MB（Claude CLI 子进程 + Python runtime），8GB M1 上限 ≈ 21 tasks。
3. **协作诊断价值**：单 agent 修真因就停手 → 漏二级 bug；单 agent 找 bug 不知哪个是真因 → 修错方向。**两个 agent 看不同层 → 交叉对比是修真因 + 找齐二级的唯一方法**。
4. **API 边界 vs 兜底**：dispatch semaphore 是边界（限用户输入），worker pool semaphore 是兜底（限所有路径）。**两层缺一不可**——只做边界，CCC Engine 内部任务仍可击穿；只做兜底，单用户 55 个 commit 仍可击穿。
5. **dead_pileup GC 不是越激进越好**：阈值 5 看似"早发现早处理"，实则误删正在排查的证据。**告警阈值要参考物理上限**——50 项目 × 2 dead ≈ 100 才是 sane 起点。
6. **`dict.get(k, default)` 不防 None**：键存在但 value 是 NULL（legacy 数据 / DB schema 漂移）时 `dict.get` 返回 None，None 和 int 比较 TypeError。**所有"读到数字然后比较"的代码必须显式 `is None → default`**。

#### 6. 预防

1. **dispatch 类 SKILL.md 必含 "Concurrency limit" 警告段**：8GB 机器 batch=3，16GB+ 可调大，明确写出 "调大前先算 (N × 300MB) ≤ 80% × physical_RAM"。
2. **新 dispatch 任务加 OPS-GATE**：dispatch 启动前自动跑 `os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')` 算可用内存，超 80% 拒绝启动。
3. **诊断协作 SOP**：修真因（Claude Code）+ 找 bug（qxo-CC / 代码审查 agent）**强制两个 agent 都签字**才能进 verify，单 agent 修真因就 verify 等于漏过半数问题。
4. **`dict.get(k, default)` 重构为 `safe_int(d, k, default)` helper**：项目内统一抽象，所有"读数字字段"走 helper，内部统一 `is None → default`。
5. **dead_pileup 类监控告警阈值默认值 = (项目数 × 平均 dead 上限)**：动态计算而不是硬编常量。

**适用范围**（W7+ 接力）：
- 任何批量启动子进程的模块（LoopEngine / V9 batch 任务 / CCC Engine）都先看 semaphore 在不在
- 任何"读 int 字段后比较"的代码都先看 None 守卫在不在
- 任何"周期性 alert + 自动 cleanup"监控都先评估阈值是不是 sane