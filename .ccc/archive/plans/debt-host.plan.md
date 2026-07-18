# debt-host

> 标题: 看板绑定改回 127.0.0.1（安全）
> 创建: 2026-07-07T12:45:02Z

## 目标

## 问题
ccc-board-server.py plist --host 0.0.0.0，局域网可访问看板 API，无认证。
如果不需要局域网访问，应该绑 127.0.0.1。

## 执行方案
1. 问你：需要局域网访问吗？
2. 要 → 保持现状
3. 不要 → sed plist 0.0.0.0→127.0.0.1，reload launchd

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
