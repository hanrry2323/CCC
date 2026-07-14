# Plan: fix-debt-test-regression — 恢复被删测试 + 补充并行调度 unit test

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段 -->
<!-- 目的：确保 dev 执行时有足够的代码上下文 -->

- **入口/核心文件**：`tests/scripts/test_engine.py`（Engine 测试）、`tests/scripts/test_engine_phase_parallel_dispatch.py`（并行调度测试）、`scripts/ccc-engine.py`（Engine 主逻辑）
- **当前结构要点**：
  1. commit `425897c` 删除 `TestEngineHelpers` 类（4 个测试：`_wait_tick` / 2x `_audit_should_run` / `_get_store` 缓存）无代替，测试覆盖退步
  2. `_get_store` 缓存在 425897c 之后已经从 `_store_instance` 单例改为 `_stores` dict（`scripts/ccc-engine.py:236`）
  3. `test_engine_phase_parallel_dispatch.py` 已有 22 个测试函数覆盖 _group_parallel_phases / _on_parallel_group_complete / _check_parallel_task_complete 等，但仍有以下缺口：
     - `_group_parallel_phases` 的复杂菱形依赖分组（1→2, 1→3, 2→4, 3→4）
     - `_group_parallel_phases` 输入含 non-executable phase 时的过滤行为
     - `_on_parallel_group_complete` 的 phases.json 缺失/损坏错误路径
- **待改动点**：`tests/scripts/test_engine.py` 恢复 TestEngineHelpers（需适配 `_stores`），`tests/scripts/test_engine_phase_parallel_dispatch.py` 追加 3 个补充测试

---

## 范围

- **目标**：恢复 425897c 删除的 4 个测试 + 补充 3 个并行调度 unit test，总回退 0
- **只改文件**：`tests/scripts/test_engine.py`，`tests/scripts/test_engine_phase_parallel_dispatch.py`
- **不改文件**：`scripts/` 下任何功能代码不动
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1：恢复 TestEngineHelpers 4 个被删测试

### 做什么
恢复 commit 425897c 中被删除的 `TestEngineHelpers` 类，包含 `test_wait_tick_sleeps_remaining` / `test_audit_should_run_when_no_last_run` / `test_audit_should_run_respects_interval` / `test_get_store_cached` 四个测试。

注意 `test_get_store_cached` 的缓存字段已从 `_store_instance` 改为 `_stores` dict（`ccc-engine.py:90`），恢复时重置 `ccc_engine._stores = {}` 而非旧代码的 `ccc_engine._store_instance = None`。

### 怎么做
在 `tests/scripts/test_engine.py` 末尾追加 `TestEngineHelpers` 类，直接引用 `6da7b48` 版本中对应 4 个测试的实现，仅修正 `test_get_store_cached` 中的缓存重置方式。

详细对照：`tests/scripts/test_engine.py` 当前文件末尾（92 行为止）追加约 50 行。

### 验收清单

- [ ] 验收条件 1：`TestEngineHelpers` 类包含 4 个测试方法
- [ ] 验收条件 2：`test_get_store_cached` 使用 `ccc_engine._stores = {}` 而非 `_store_instance = None`
- [ ] 验收条件 3：4 个测试全部 pass
- [ ] 边界场景：`_get_store` 用 `_stores` dict 缓存，清除空 dict 与 `_stores = {}` 等价的
- [ ] 错误处理：无新增错误处理逻辑

### 验收

- [恢复 4 个测试] `grep -c 'def test_' tests/scripts/test_engine.py` 从 4 → 8（参考：`grep -n 'class TestEngineHelpers' tests/scripts/test_engine.py` 确认类存在）
- [适配 `_stores`] `grep '_store_instance' tests/scripts/test_engine.py` 无输出（禁止引用旧字段名）
- [全部 pass] `cd /Users/apple/program/CCC && uv run pytest tests/scripts/test_engine.py -v` 8 passed（参考：`uv run pytest tests/scripts/test_engine.py -q`）

---

## 改动 2：补充并行调度 unit test（3 个）

### 做什么
在 `tests/scripts/test_engine_phase_parallel_dispatch.py` 追加 3 个单元测试，补齐以下缺口：

1. **菱形依赖分组**：phase 1（无依赖）、phase 2（依赖 1）、phase 3（依赖 1）、phase 4（依赖 2&3）→ 4 个 phase 全部 executable 时分组应为 `[[1], [2,3], [4]]`
2. **non-executable phase 过滤**：phases 列表包含 phase 3（blocked，不在 executable 集合），只应分组可执行的 phase 1、2、4
3. **`_on_parallel_group_complete` 错误路径**：phases.json 文件不存在时，返回 `still_running` 或抛出合理异常，不静默崩溃

### 怎么做
在 `tests/scripts/test_engine_phase_parallel_dispatch.py` 末尾（当前 693 行）追加 3 个测试函数，使用该文件已有的 AST 提取和 engine 模块加载机制。

详细位置：
- 追加在 `test_check_parallel_task_complete_writes_done_marker` 之后（692 行附近）
- 使用 AST 提取的 `_group_parallel_phases`（已有 `_load_group_function()`）
- 使用 `_load_engine_module()` 测试 `_on_parallel_group_complete`

### 验收清单

- [ ] 验收条件 1：菱形依赖测试正确分组为 `[[1], [2,3], [4]]`
- [ ] 验收条件 2：non-executable phase 被过滤，不出现在 groups 中
- [ ] 验收条件 3：缺失 phases.json 时 `_on_parallel_group_complete` 不崩溃
- [ ] 边界场景：菱形依赖中 4 个 phase 同时 executable，第 2/3 可同组
- [ ] 错误处理：缺失文件测试确认正常返回而非 Python 异常

### 验收

- [新增 3 个测试] `grep -c 'def test_' tests/scripts/test_engine_phase_parallel_dispatch.py` 从 22 → 25（参考：`uv run pytest tests/scripts/test_engine_phase_parallel_dispatch.py -q` 25 passed）
- [全部 pass] `cd /Users/apple/program/CCC && uv run pytest tests/scripts/test_engine_phase_parallel_dispatch.py -v --tb=short` 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 恢复 TestEngineHelpers 4 个被删测试 | `fix(test): 恢复 425897c 删除的 TestEngineHelpers 4 个测试，适配 _stores 缓存 (phase 1/2)` |
| 2 | 补充 3 个并行调度 unit test | `test(parallel): 补充菱形依赖 / non-executable 过滤 / on_complete 错误路径 3 个测试 (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q tests/scripts/`）
- [ ] `tests/scripts/test_engine.py` 全部 8 test passed
- [ ] `tests/scripts/test_engine_phase_parallel_dispatch.py` 全部 25 test passed
- [ ] diff 范围仅限白名单 2 个文件
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2 phases）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

无。此 H1 修复完成后 test_engine.py 覆盖恢复，并行调度模块测试缺口补齐。