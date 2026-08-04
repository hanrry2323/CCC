# CCC 多项目并发压力测试报告

**日期**: 2026-07-09
**测试执行**: ccc-protocol (自动调度)

---

## 1. 测试概要

| 指标 | 值 |
|------|-----|
| 项目数 | 5（CCC / xianyu / qx / qx-observer / qb） |
| 总任务数 | 15（每项目 3 个） |
| 任务类型 | .gitignore 更新 / README badge / CHANGELOG stub |
| 测试时间窗口 | 15:00 ~ 15:32 UTC（32 分钟） |
| Engine 进程 | 5（每项目 1 个常驻） |
| OpenCode 池上限 | 3（红线 X1） |

---

## 2. 调度正确性评估

**结论：通过。** 15 个任务全部正确分配到对应项目，无幻觉、无交叉错配。

| 项目 | 任务数 | 分配正确 | 幻觉/错误 |
|------|--------|---------|----------|
| CCC | 3 | 3/3 | 0 |
| xianyu | 3 | 3/3 | 0 |
| qx | 3 | 3/3 | 0 |
| qx-observer | 3 | 3/3 | 0 |
| qb | 3 | 3/3 | 0 |
| **合计** | **15** | **15/15 (100%)** | **0** |

所有 task JSONL 写入后，各项目 engine 正确识别并拾取属于自己 workspace 的 task，无误取、无抢夺。

---

## 3. Pipeline 并发表现

### 3.1 任务调度阶段（product → planned）

15 个 task 的 plan + phases 由调度直接写入，平均耗时 <1s/task（因为 task 简单，无需 LLM 规划）。

### 3.2 Dev 阶段（OpenCode CLI）

**并发峰值：6 个 opencode run 进程同时运行。**

| 时间点 | opencode run 数 | 说明 |
|--------|----------------|------|
| 15:20 | 5 | 5 个 engine 各取 1 个 task 同时启动 |
| 15:25 | 5 | 第一个 task 完成，新 task 立即补位 |
| 15:30 | 6 | 高峰期（CCC 新任务接替 + 其余仍运行） |
| 15:32 | 5 | 仍在运行 |

**关键发现：OpenCode 池上限（红线 X1）未被 engine 强制执行。**

红线 X1 规定 OpenCode 进程池最多 3 并发，但 engine 直接调用 `opencode-runner.sh`（`opencode-pool.py` 不被 engine 使用），导致 5 个 engine 可以同时启动 5 个 opencode 进程。M1 8GB 内存压力显著（swap 使用上升）。

### 3.3 各 task 执行耗时

| 项目 | Task | 耗时 | 状态 | 备注 |
|------|------|------|------|------|
| CCC | ccc-changelog-format | 214s | ✅ released | |
| CCC | ccc-docstring-sweep | 169s | ✅ released | |
| CCC | ccc-gitignore-update | ~180s | ✅ released | |
| xianyu | xianyu-cli-help | 300s+ | 🔄 in_progress | 超时待定 |
| xianyu | xianyu-readme-badge | - | ⏳ planned | 排队中 |
| xianyu | xianyu-gitignore | - | ⏳ planned | 排队中 |
| qx | qx-changelog-stub | 185s | ✅ released | |
| qx | qx-gitignore-audit | 186s | 🔄 in_progress | 刚启动 |
| qx | qx-readme-status | - | ⏳ planned | 排队中 |
| qx-observer | qxo-changelog | 300s+ | 🔄 in_progress | 超时待定 |
| qx-observer | qxo-readme-badge | - | ⏳ planned | 排队中 |
| qx-observer | qxo-gitignore | - | ⏳ planned | 排队中 |
| qb | qb-changelog-stub | 300s+ | 🔄 in_progress | 超时待定 |
| qb | qb-gitignore | - | ⏳ planned | 排队中 |
| qb | qb-readme-status | - | ⏳ planned | 排队中 |

### 3.4 中转站 LLM（:4000）压力

测试期间中转站无响应超时或限流。product 阶段的 LLM 调用（Claude CLI）仅限于 plan 生成本身，由于本次测试手动写 plan，未触发大量 LLM 调用。opencode 执行阶段调用的是 `loop/flash` 模型，经过中转站路由。5 个 opencode 同时运行时中转站无明显瓶颈。

---

## 4. 执行成功率

| 项目 | 已计划 | 开发中 | 已测试 | 已验收 | 已发布 | 异常 | 成功率 |
|------|--------|--------|--------|--------|--------|------|--------|
| CCC | 0 | 0 | 0 | 0 | 3 | 0 | **100%** |
| xianyu | 2 | 1 | 0 | 0 | 0 | 0 | **0%**（未完成） |
| qx | 1 | 1 | 0 | 0 | 1 | 0 | **50%**（1/2） |
| qx-observer | 2 | 1 | 0 | 0 | 0 | 2 | **0%**（未完成） |
| qb | 2 | 1 | 0 | 0 | 0 | 0 | **0%**（未完成） |
| **合计** | 7 | 4 | 0 | 0 | 4 | 2 | **27%**（4/15） |

> 注：成功率低的原因是 32 分钟测试窗口内大部分 task 仍在排队或执行中。已完成 task（4 个）全部成功到 released。

---

## 5. 质量评估

### 5.1 Plan 质量（人工抽查）

已完成 task 均有 plan.md + phases.json。plan 内容基本覆盖任务目标，但由于是自动生成（模板化），缺少深度分析。

### 5.2 代码执行质量

已完成 task 的 report.md 显示 exit_code=0，openCode 成功执行了文件修改。

### 5.3 验收质量

**问题：reviewer 角色的 LLM 审查空转。**

已完成 task 中，仅 qx-changelog-stub 生成了 review.md（且 verdict = FALLBACK，0 条 findings）。其余 task 没有 verdict.md。意味着 reviewer_role 的 LLM gate 没有真正工作——审查阶段静默通过。

---

## 6. 发现的问题

### 🔴 P0: OpenCode 池上限未强制执行

**文件**: `scripts/ccc-engine.py:1783`

Engine 直接 `Popen(opencode-runner.sh)`，不走 `opencode-pool.py`。红线 X1 形同虚设。

**影响**: 5+ 开放 opencode 进程同时运行，M1 8GB 内存压力大。

**建议**: engine 的 dev_role_launch 改用 opencode-pool 或自行检查并发数。

### 🟡 P1: reviewer_role LLM 审查空转

已完成 task 无 verdict，reviewer 阶段的 LLM gate 未产出有效审查结果。

**影响**: 验收环节形同虚设，未经审查直接 released。

**原因**: 可能是 `reviewer_role` 调 `claude -p` 超时或返回空（v0.21 已修复但仍不稳）。

### 🟡 P2: task 超时处理不明确

多个 task 达到 300s 超时仍标记为 `in_progress`，engine 没有 timeout 后的降级/重试/跳过策略。超时后 engine 是否重试需要确认。

### 🟢 P3: task 简单场景下 pipeline 跑得通

正面发现：CCC 项目 3 个 task 全部自动走完 backlog → planned → in_progress → testing → verified → released，证明 pipeline 基础链路正常。

---

## 7. 改进建议

| 优先级 | 建议 | 对应版本 |
|--------|------|---------|
| 🔴 1 | Engine 检查 OpenCode 池上限或用 opencode-pool | v0.24 或提前修 |
| 🟡 2 | reviewer_role 调 LLM 失败的 fallback 和告警 | v0.21 需加固 |
| 🟡 3 | 超时 task 的 engine 降级策略（重试/跳过/告警） | v0.24 |
| 🟢 4 | 考虑加 task 执行时间上限的 phases 硬性超时 | v0.24 |

---

## 8. 结论

**调度正确性：✅ 通过。** 15 个 task 无幻觉、无交叉错配。

**Pipeline 并发：⚠️ 部分通过。** 5 个 engine 各自独立工作正常，但 OpenCode 池上限未被强制执行，M1 在 5 并发场景下面临内存压力。

**执行成功：🔄 进行中。** 32 分钟内 4/15 (27%) 完成到 released，CCI 的 3 个 task 全部成功。其余 task 仍在排队/执行中。已完成 task 成功率 100%。

**核心结论：CCC 的多项目看板调度基本正确，但 OpenCode 池管理和 reviewer LLM gate 需要加固才能稳定支撑多项目并发场景。**
