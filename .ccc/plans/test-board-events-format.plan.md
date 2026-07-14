# Plan: test-board-events-format — BoardStore 事件格式一致性测试

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

BoardStore 的 `move_task()` 和 `add_event()` 写入 events.jsonl，但写入格式一致性未用测试覆盖。事件字段名（`from`/`to`/`timestamp`）和类型可能因代码改动悄然变化。

## 范围

- **目标**: 新增测试验证事件写入格式与 `board-task-schema.md` 一致
- **只改文件**: `tests/scripts/test_board_store.py`

## 改动

1. `test_board_store.py` 新增 `test_event_format`：模拟 move 操作，检查 events.jsonl 内容
2. 验证每个事件包含 `event`, `task_id`, `from`, `to`, `timestamp` 字段
3. 验证 `from` = "none" 的首个事件
4. 验证 `event` ∈ {"move", "assign", "quarantine"}

## 验收

- [test] `python3 -m pytest tests/scripts/test_board_store.py::test_event_format -q` → PASS
- [字段] 测试断言事件 JSON 含 event/task_id/from/to/timestamp
- [schema] 事件格式与 board-task-schema.md 一致
