# Plan: debt-error-message-consolidate — 统一错误日志前缀格式

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

各脚本使用不同的日志前缀：`[ERROR]`, `ERROR:`, `(E)`, `!!`, `***`。板���时 grep 日志不统一，无法快速过滤。

## 范围

- **目标**: 所有 Python 脚本统一使用 `_logger.py` 的 `logger.error()` / `logger.warning()` / `logger.info()`
- **只改文件**: `scripts/ccc-engine.py`, `scripts/ccc-board.py`, `scripts/ccc-board-server.py`, `scripts/ccc-cockpit.py`, `scripts/opencode-exec.py`

## 改动

1. 搜索 `print(` 和 `sys.stderr.write` → 替换为 `logger.*()` 调用
2. `print(... file=sys.stderr)` → `logger.error(...)`
3. `print(...)` (info) → `logger.info(...)`
4. 确保每个脚本顶部 `from _logger import logger`

## 验收

- [统一] `grep -rn 'print(' scripts/ccc-engine.py scripts/ccc-board.py scripts/ccc-board-server.py scripts/ccc-cockpit.py scripts/opencode-exec.py` 返回 0（排除注释）
- [logger] 每个文件顶部有 `from _logger import logger`
- [无回归] Engine 启动后正常 tick，日志输出正常
