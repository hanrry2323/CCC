# Plan: engine-stats-endpoint — Engine /stats 健康检查端点

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`scripts/ccc-engine.py` 主循环没有 HTTP 端点暴露当前状态。`board-server.py` 有 `/api/tasks` 端点，但 Engine 自身的运行状态（uptime、task、phase、子进程等）无法外部查询。

## 范围

- **目标**: Engine 添加 `/api/stats` HTTP 端点，返回 Engine 运行状态 JSON
- **只改文件**: `scripts/ccc-engine.py`
- **不改文件**: `.ccc/` 下任何文件，其他脚本

## 改动

在 `ccc-engine.py` 中添加：
1. 导入 `http.server` 或使用 `socketserver` 在 Engine 内部启动轻量 HTTP 服务（线程，port 7776）
2. 端点 `GET /api/stats` 返回 JSON: `{uptime_sec, current_task, current_phase, phase_status, in_progress_count, engine_version, last_tick_at}`
3. Engine 主循环更新 `last_tick_at`
4. 添加 `--port` 参数支持自定义端口

## 验收

- [HTTP] `curl http://localhost:7776/api/stats` 返回合法 JSON + HTTP 200
- [字段] 响应包含 uptime_sec > 0, current_task (或 null), phase_status (running/pending/done), engine_version
- [边界] Engine 无任务运行时 current_task = null，不 crash
- [安全] 仅监听 127.0.0.1，不暴露到外网

## 后续

可在 Cockpit 中通过 `/api/stats` 展示 Engine 状态卡片。
