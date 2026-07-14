# Plan: engine-events-rotation — events.jsonl 自动轮转

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`.ccc/board/events/` 下的 events.jsonl 只追加不截断。历史记录显示 397MB 文件导致 Engine 98% CPU 空转。

## 范围

- **目标**: Engine 空闲循环中添加 events.jsonl 自动轮转机制
- **只改文件**: `scripts/ccc-engine.py`
- **不改文件**: `.ccc/` 下 events 目录

## 改动

1. 在 Engine 空闲循环中（无 task 时），检查 `.ccc/board/events/` 下所有 `.jsonl` 文件
2. 单文件 > 10MB 或总 events 目录 > 50MB 时，压缩归档：`mv events.jsonl events-YYYY-MM-DD.jsonl.bz2`
3. 保留最近 7 天归档，更早的 `rm`
4. 归档操作间隔至少 1 小时（避免频繁 IO）

## 验收

- [阈值] Engine 检测到 events.jsonl > 10MB 时自动轮转
- [归档] 轮转后存在 `.bz2` 压缩文件
- [清理] 7 天前的归档被自动删除
- [间隔] 轮转后不重复轮转（mtime < 1h 跳过）
