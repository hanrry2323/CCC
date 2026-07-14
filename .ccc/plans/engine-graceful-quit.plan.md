# Plan: engine-graceful-quit — Engine 优雅退出

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Engine 收到 SIGTERM/SIGINT 时直接退出，不清理子进程（opencode/board-server）。可能导致孤儿进程残留，下次启动端口冲突。

## 范围

- **目标**: Engine 注册信号处理器，退出前终止子进程 + 清理临时文件
- **只改文件**: `scripts/ccc-engine.py`

## 改动

1. `signal.signal(SIGTERM)` + `SIGINT` 注册 `_handle_shutdown()`
2. 处理器逻辑：标记 `_shutting_down = True` → 终止当前子进程（Popen.terminate()）→ 清理 `/tmp/ccc-*` 临时文件 → `sys.exit(0)`
3. 主循环每次 tick 检查 `_shutting_down` 标志
4. 日志输出 "Engine shutting down gracefully..."

## 验收

- [信号] `kill <engine_pid>` 后 Engine 打印 "shutting down gracefully" 并退出
- [子进程] 当前运行的 opencode 子进程被终止（ps aux 确认无残留）
- [临时文件] `/tmp/ccc-*` 文件被清理
- [幂等] 重复 kill 不 panic（第二次 kill 直接 force exit）
