# Plan: engine-task-state-persist — Engine 重启后 task 状态持久化恢复

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Engine 进程崩溃或重启后，正在执行的 task 丢失恢复上下文。Engine 从 tick 0 重启，不会自动恢复 in_progress 或 testing 列的 task。

## 范围

- **目标**: Engine 启动时扫描 board 当前列，恢复 task 到对应执行阶段
- **只改文件**: `scripts/ccc-engine.py`, `scripts/ccc-board.py`

## 改动

1. `ccc-engine.py` 启动时调 `_recover_tasks()` 函数
2. 扫描 in_progress 列 → 调 `dev_role_check_complete()` 恢复 phase
3. 扫描 testing 列 → 调 `reviewer_role()` + `tester_role()` 恢复验收
4. 记录 recovery 日志: "Recovered task <id> at phase <n>"
5. 每个 task 恢复间隔 5s 避免并发

## 验收

- [in_progress] Engine 重启后，in_progress 列的 task 自动恢复 phase 执行
- [testing] testing 列 task 自动恢复 reviewer 验收
- [日志] 日志含 "Recovered" 字样
- [跳过] board 为空时跳过恢复
