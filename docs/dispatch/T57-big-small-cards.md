# 任务卡 T57 · T-A4 大卡/小卡 + 项目级执行体隔离（Claude Code 执行）

> 关联：阶段 3（T-A4，过夜任务后端链 2/3）· 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t57-big-small-cards`（先 `git fetch origin main && git checkout -b codex/t57-big-small-cards origin/main`）
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

大卡（epic）/小卡（task）机制：类型字段 + 父卡 + 只有 task 可派发 + epic 聚合视图；执行体注册表项目级绑定（隔离）。

## 具体项

1. **类型/父卡字段**：卡头 `类型：epic|task`（缺省 task）+ `父卡：<id>`（仅 task）；loader/validate 校验（epic 无父卡、task 父卡存在且同项目）。
2. **派发规则**：`decide_work` 只有 task 可派发；epic 不派发（只拆解/聚合）。
3. **聚合视图**：线路图/看板按 epic 聚合子卡进度（已完成/总子卡）；epic 状态由子卡派生（全部关闭+目标达成→待验收）。
4. **项目级执行体隔离**：executors.json 支持按项目绑定（如 qb 卡只派 qb 执行体）；`decide_work` 加项目维度校验（缺省=当前绑定）。
5. 测试任务先行：临时目录占位卡验证 epic/task 流转。

## 红线

1. 只改 server/board/、server/engine/、server/config/、server/web/server.py（聚合接口区）、tests；**禁止改 legacy-chat 前端（T-B2 所有权）**。
2. 旧卡兼容（无类型/父卡字段按 task 处理）。
3. 回写前 push 成功并附证据。

## 验收标准

1. epic/task 卡头校验（非法组合被拦）；epic 不被派发（测试占位验证）。
2. 聚合视图：epic 子卡进度正确（含部分完成/全关）。
3. 项目级执行体：qb 卡只派 qb 绑定执行体（配置示例 + 测试）。
4. pytest 全绿、ruff clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：字段/派发/聚合/隔离实现、测试任务验证、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-05

### 1. 字段/派发/聚合/隔离实现

- **类型/父卡字段**：在 `BoardItem` 数据模型中新增 `type` 与 `parent` 字段，并在 `parse_card` 中解析卡头 `类型` 及 `父卡`，默认值为 `"task"` 与空。在增量加载中也支持从 index 读取与保存，在 `validate_cards` 中严格校验 `epic` 无父卡及 `task` 的父卡存在且在同个项目中。
- **派发规则**：在 `decide_work` 中对 `epic` 类型的卡片进行判定，直接返回 `DispatchDecision.NONE` 拦截派发，仅允许 `task` 派发。
- **聚合视图**：在 `loader.py` 中实现 `derive_epic_states_and_progress`，扫描并聚合子卡进度。如所有子卡均已关闭则 Epic 状态自动派生为 `"已回写"`（即待验收），否则根据是否有活跃子卡（执行中/已回写/打回）派生为 `"执行中"` 或 `"待分派"`。进度追加到 Epic 的 `title` (`f"{title} ({closed}/{total})"`) 以及桌面端兼容的 `note` 字段。
- **项目级隔离**：在 `executors.json` 注册表条目中支持 `"项目"` 字段；在 `Work` 模型中新增 `project` 字段。在 `ExecutorRegistry` 的 `rows_for_role` 等查找方法、以及 `decide_work` 匹配逻辑中，优先精确匹配特定项目的执行体（如 `qb` 项目仅匹配 `qb` 绑定的执行体），无则回退至全局。

### 2. 测试任务验证

- 新增 `test_board_validate.py::test_epic_task_validation`，测试 Epic 不能指定父卡、非空父卡必须存在、以及父卡与当前卡片项目必须一致等规则，校验全部成功通过。
- 新增 `test_engine_dispatch.py::TestDecideWork::test_epic_not_dispatched`，测试 `decide_work` 对 Epic 拦截，不派发。
- 新增 `test_engine_dispatch.py::TestDecideWork::test_project_level_executor_isolation`，测试项目级执行器隔离匹配与回退机制，确保 `qb` 仅派发到 `qb` 指定执行体。

### 3. pytest/build & Ruff 证据

- **ruff check**: `All checks passed!`
- **pytest**: `470 passed in 15.33s` 单元/接口测试全绿通过。

### 4. Push 证据

- **Commit**: `feat(epic-task): T57 epic/task mechanisms & project-level executor isolation`
- **Verification**: `pytest 470 passed, ruff clean`


---

## 验收区（Codex 独立取证 · 过夜执行）

**判定：✅ 通过。** epic/task 机制 + 项目级执行体隔离落地（f4dd805e，pytest 全绿，2017 已部署）。
