# Plan: test-engine-phase-failover — Engine phase 失败转移测试

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`tests/scripts/` 下有 `test_phase_dependencies.py` 和 `test_phase_end_to_end.py`，但缺少 Engine phase 失败后自动跳到下一个 executable phase 的集成测试。

## 范围

- **目标**: 新增测试覆盖 Engine 的 phase 失败传染和跳过逻辑
- **只改文件**: `tests/scripts/test_engine.py`
- **不改文件**: scripts/ 下任何功能代码

## 改动

1. `test_engine.py` 新增 `test_phase_fail_skip_dependent`：模拟 phase 1 失败，验证 phase 2（depends_on phase1）也被标记 skipped
2. `test_phase_fail_jump_executable`：模拟 phase 1 失败，验证无依赖的 phase 3 仍可执行
3. `test_phase_all_terminal`：模拟全部 phase 失败或完成，验证 _check_phase_failures 返回 terminal

## 验收

- [test] `python3 -m pytest tests/scripts/test_engine.py::test_phase_fail_skip_dependent -q` → PASS
- [test] `test_phase_fail_jump_executable` → PASS
- [test] `test_phase_all_terminal` → PASS
- [不���] 不修改 scripts/ 下任何功能代码
