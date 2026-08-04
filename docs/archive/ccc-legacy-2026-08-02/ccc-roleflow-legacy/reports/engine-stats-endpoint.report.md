# engine-stats-endpoint 执行报告

## 信息
- Task: engine-stats-endpoint
- Phase: 1/1 (single phase)
- 复杂度: small（跳过 reviewer+tester，直通 kb）
- Commit: a3556db

## 改动文件
- `scripts/ccc-engine.py`（仅此文件，符合 plan 白名单）

## 实现内容

### 1. 模块级 stats 状态（line 1346-1357）
```python
_stats_started_at: float | None = None
_stats_lock = threading.Lock()
_stats_data: dict = {
    "uptime_sec": 0,
    "current_task": None,
    "current_phase": None,
    "phase_status": None,
    "in_progress_count": 0,
    "engine_version": "v0.28.1",
    "last_tick_at": None,
    "workspace": Path.cwd().name,
}
```

### 2. `_update_stats()` (line 1362-1389)
线程安全的状态更新器（持有 `_stats_lock`）：
- 首次调用时初始化 `_stats_started_at`
- 后续调用计算 `uptime_sec = int(now_ts - _stats_started_at)`
- 更新 `current_task` / `current_phase` / `phase_status` / `in_progress_count` / `last_tick_at`

### 3. 主循环集成（line 915）
`engine_loop()` 每轮 tick 调用 `_update_stats()` 一次：
```python
_update_stats(
    active_count=len(active_tasks),
    current_task=first_task_id,
    phase_status="running" if any_active else "idle",
    workspace_name=first_task_ws.name if first_task_ws else None,
)
```

### 4. HTTP 端点（line 1390-1420）
- `_StatsHandler(BaseHTTPRequestHandler)` 处理 `GET /api/stats`
- 返回 JSON: `{uptime_sec, current_task, current_phase, phase_status, in_progress_count, engine_version, last_tick_at, workspace}`
- 非 `/api/stats` 路径 → 404
- 仅绑定 `127.0.0.1`（无外网暴露）
- `log_message` 重写走 engine_log（不污染 stderr）

### 5. HTTP 服务启动（line 1418-1451）
- `_run_stats_server(port)` 在 daemon 线程跑 HTTPServer
- 每轮 `handle_request()` 后检查 `_engine_shutdown` → 优雅退出
- SIGTERM 时 `server_close()` 释放端口

### 6. CLI 参数（line 1320-1324）
```python
parser.add_argument("--port", type=int, default=_STATS_PORT, help=...)
```
支持 `python3 ccc-engine.py --port 7776` 自定义端口。

## 验收验证（隔离测试）

通过 exec 模块（stub ccc_board 避免无关 ccc-board.py 缩进 bug 干扰）：

```
HTTP 200
BODY: {"uptime_sec": 0, "current_task": null, "current_phase": null,
       "phase_status": null, "in_progress_count": 0,
       "engine_version": "v0.28.1", "last_tick_at": null, "workspace": "CCC"}

[更新 stats] _update_stats(active_count=2, current_task='foo', phase_status='running')

after update: current_task=foo in_progress_count=2 phase_status=running
              last_tick_at=2026-07-14T18:21:41.928987

unknown → HTTP 404
ALL ASSERTIONS PASSED ✓
```

| 验收项 | 结果 |
|-------|------|
| [HTTP] `curl http://localhost:7776/api/stats` 返回合法 JSON + HTTP 200 | ✓ |
| [字段] 响应包含 uptime_sec, current_task, phase_status, engine_version | ✓ |
| [边界] 无任务运行时 current_task = null，不 crash | ✓ |
| [安全] 仅监听 127.0.0.1 | ✓ |

## 已知 out-of-scope

测试时发现 `scripts/ccc-board.py:3867` 有预存的语法错（else 块未缩进），
不在本 plan 白名单内，不修。

## AGENTS.md 建议

> 模块级 daemon 线程启动的辅助函数（如 `_run_stats_server`）必须定义在
> `main()` 之前，不能依赖 `if __name__ == "__main__":` 之后才执行。