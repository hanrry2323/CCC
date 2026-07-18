# Plan: fix-test-parallel-key — 修复 parallel dispatch 测试硬编码 active_key（H2）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含本段，描述当前代码结构的关键发现 -->

- **入口/核心文件**：`tests/scripts/test_engine_phase_parallel_dispatch.py`（并行调度测试）、`scripts/ccc-engine.py`（Engine 主逻辑，含 `_task_key` 和 `_try_launch_planned`）
- **当前结构要点**：
  1. `scripts/ccc-engine.py:219-220` 定义 `_task_key(ws, tid) -> f"{ws.resolve()}|{tid}"`，是 Engine 全局唯一的 active task 标识符
  2. `_try_launch_planned` 在 `ccc-engine.py:933` 计算 `key = _task_key(ws, tid)`，并在并行成功分支（`ccc-engine.py:981-987`）把 `active_tasks[key] = {... "mode": "parallel"}`；非并行分支（`ccc-engine.py:997-1002`）写 `active_tasks[key]` 但**没有** `"mode"` 字段
  3. `test_try_launch_planned_chooses_parallel_when_conditions_met`（`tests/scripts/test_engine_phase_parallel_dispatch.py:317-391`）通过 `_load_engine_module()` 拿到 `mod`，构造 `ws=tmp_path`、`tid="t-par"` 后调用 `_try_launch_planned(ws, active)`，最后断言 `active["active_key"]["mode"] == "parallel"`
  4. 实测确认 bug：当前断言 `KeyError: 'active_key'`，因为 key 永远是 `f"{tmp_path.resolve()}|t-par"`，不可能是字面量 `"active_key"`
  5. `_load_engine_module()` 用 `importlib.util.spec_from_file_location` 真正加载 ccc-engine，所以 `mod._task_key(ws, tid)` 在测试中可用，无需重复实现
- **待改动点**：`tests/scripts/test_engine_phase_parallel_dispatch.py:391` 一行的断言；可顺手在测试顶部 `mod = _load_engine_module()` 之前预计算 `par_key`，避免在该行重复逻辑

---

## 范围

- **目标**：把 `test_engine_phase_parallel_dispatch.py:391` 的硬编码 `"active_key"` 替换为基于 `_task_key(ws, "t-par")` 的真实 key，让断言匹配 Engine 实际行为
- **只改文件**：`tests/scripts/test_engine_phase_parallel_dispatch.py`
- **不改文件**：`scripts/ccc-engine.py` 及其他任何源码不动
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：用 `_task_key(ws, "t-par")` 计算真实 key 替换硬编码

### 做什么
修复 `test_try_launch_planned_chooses_parallel_when_conditions_met` 中第 391 行的断言。该测试目的是验证 Engine 在 3 phase 无依赖时走并行分支，并把 task 加入 `active_tasks` 时带上 `"mode": "parallel"`。

当前写法 `active["active_key"]["mode"] == "parallel"` 错把 `"active_key"` 当成 key，但 Engine 实际通过 `_task_key(ws, tid)` 生成 `f"{ws.resolve()}|{tid}"`。需要计算真实 key 后再断言。

### 怎么做
在 `tests/scripts/test_engine_phase_parallel_dispatch.py:391` 所在测试函数中：
- 该测试已在 `mod = _load_engine_module()` 之后（line 324），`mod._task_key` 可用
- 在调用 `mod._try_launch_planned(ws, active)` **之前** 计算 `par_key = mod._task_key(ws, "t-par")`（与 line 333/336 的 `tid="t-par"` 对齐）
- 把第 391 行改为 `assert active[par_key]["mode"] == "parallel"`
- 不改 `active = {}`（line 380），因为 Engine 的 key 就是 `par_key`，空 dict 仍是合法输入

**不引入新 import、不写新 helper**——`_task_key` 已在 `ccc-engine.py:219` 定义，测试通过 `mod._task_key` 直接调用即可。

### 验收清单

<!-- v0.21 强制：reviewer LLM 按此逐条核对 -->

- [ ] 验收条件 1：第 391 行不再出现字面量 `"active_key"` 作为 dict key
- [ ] 验收条件 2：使用 `mod._task_key(ws, "t-par")` 计算的 key 与 `ccc-engine.py:933` 保持一致（`f"{ws.resolve()}|{tid}"`）
- [ ] 验收条件 3：原 `test_try_launch_planned_chooses_parallel_when_conditions_met` 从 FAIL → PASS
- [ ] 边界场景：`active = {}` 在传入时为空，Engine 调用后应恰好写入一条 key；断言基于计算值而非字面量
- [ ] 错误处理：若 Engine 改 `_task_key` 格式（例如改用 `os.sep`），测试会一并暴露，无静默失效
- [ ] 安全相关：无

### 验收

- [不再硬编码] `grep -n '"active_key"' tests/scripts/test_engine_phase_parallel_dispatch.py` 在第 391 行附近不再命中（参考：行 391 应已替换为 `active[par_key]` 形式）
- [使用真实 key] `grep -n '_task_key' tests/scripts/test_engine_phase_parallel_dispatch.py` 至少 1 处新命中（参考：测试内部引用 `mod._task_key`）
- [测试通过] `cd /Users/apple/program/CCC && uv run pytest tests/scripts/test_engine_phase_parallel_dispatch.py::test_try_launch_planned_chooses_parallel_when_conditions_met -v` 显示 PASSED（参考：`uv run pytest tests/scripts/test_engine_phase_parallel_dispatch.py -q` 全部 PASSED）
- [回归 0] 整个文件无新失败用例（参考：`uv run pytest tests/scripts/test_engine_phase_parallel_dispatch.py --tb=short -q` 全 PASSED）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 用 `_task_key(ws, "t-par")` 替换第 391 行硬编码 `"active_key"` | `fix(test): 用 _task_key() 计算真实 key 替换 hardcoded "active_key" (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q tests/scripts/test_engine_phase_parallel_dispatch.py`）
- [ ] `test_try_launch_planned_chooses_parallel_when_conditions_met` PASSED
- [ ] `tests/scripts/test_engine_phase_parallel_dispatch.py` 全部用例 PASSED
- [ ] diff 范围仅限白名单 1 个文件
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json 与 plan phase 数一致（1 phase）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤（可选）

无。H2 修复后 `test_engine_phase_parallel_dispatch.py` 25 个测试全部可跑，配合 H1（fix-debt-test-regression）补齐覆盖后，并行调度模块测试从「部分 fail」恢复到「全绿」。