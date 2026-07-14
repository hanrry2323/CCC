# Plan: cockpit-auto-refresh — Cockpit 30s 自动轮询刷新

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Cockpit 页面 `:7778` 加载后不自动更新，需用户手动刷新浏览器。端口探测结果在服务端缓存 30s，但浏览器不轮询。

## 范围

- **目标**: Cockpit 前端每 30s 自动轮询 `/api/alive` 更新端口状态
- **只改文件**: `scripts/ccc-cockpit.py`（内嵌 HTML/JS）

## 改动

1. render_html() 的 JS 块中添加 `setInterval(fetchAlive, 30000)` 轮询
2. `fetchAlive()` 调用 `GET /api/alive` → 更新 `.dot-green/red/gray` 的 className
3. 首次加载 2s 后启动轮询（避免与初始加载同时）
4. 页面底部显示 "上次更新: HH:MM:SS"
5. 轮询失败（HTTP 500/超时）不弹窗，静默略过

## 验收

- [自动] 页面加载 2s 后开始轮询（开发者工具 Network 可见 30s 间隔请求）
- [刷新] 手动 kill 某端口进程后，页面 30s 内自动转红
- [时间戳] 底部显示 "上次更新: 14:30:01"
- [容错] Network offline 时页面不弹窗不崩溃
