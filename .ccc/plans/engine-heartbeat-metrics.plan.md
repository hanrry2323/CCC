# Plan: engine-heartbeat-metrics — 心跳增加活跃任务数

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.py`（~2105 行）
- **当前结构要点**：
  1. `_write_heartbeat()`（L1932-1943）在 Engine 主循环的活跃分支（L1479-1481）和空闲分支（L1522）两个位置被调用。当前写入 `{workspace, running, timestamp}` 三个字段到 `.ccc/engine-heartbeat.json`
  2. `_update_stats()`（L2011-2035）维护内存中 `_stats_data`，已含 `in_progress_count`（即 `len(active_tasks)`），但 `_write_heartbeat()` 不接收此数据——两个函数互不关联
  3. `active_tasks`（L1355）是 Engine 主循环全局 dict，key=`_task_key(ws, tid)`，value=`{workspace, task_id, complexity, started_at}`。它记录全局活跃任务，不按 workspace 分组统计
  4. 运行中的 PID 信息分散在两处：并行 phase 的 PID 在 `_parallel_phases["phase_meta"]` 中，串行 phase 的 PID 通过 opencode-runner 写入 `.ccc/pids/<subid>.pid` 文件
  5. `_phase_market_subid(tid, phase_num)`（L780）生成 `{tid}__p{phase_num}` 格式的 subid，对应 `pids/{subid}.pid` 文件
  6. `.ccc/pids/` 目录同时包含 `.pid`（存活态）、`.done`（完成态）、`.exitcode`（退出码）三类标记——通过检查 `.pid` 文件存在但对应 `.done` 不存在，可推断正在运行的 PID
- **待改动点**：
  - `scripts/ccc-engine.py` 中 `_write_heartbeat()`：新增 `active_task_count` 和 `running_pids` 参数 + 写入
  - `scripts/ccc-engine.py` 中 `engine_loop()` 的 L1479-1481 调用处：计算传入
  - `scripts/ccc-engine.py` 中 `engine_loop()` 的 L1522 调用处：传入 0 / []

---

## 范围

- **目标**：Heartbeat 增加 `active_task_count`（该 workspace 活跃任务数）和 `running_pids`（该 workspace 正在运行的 PID 列表），使 patrol 可通过心跳直接判断 Engine 真实健康度
- **只改文件**：`["scripts/ccc-engine.py"]`
- **不改文件**：`["scripts/ccc-patrol-v4.py", "scripts/_board_store.py", "scripts/ccc-board.py"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：_write_heartbeat 增加活跃任务数和 PID 列表

### 做什么

当前 `_write_heartbeat()` 只输出 `{workspace, running, timestamp}`，patrol 只能靠时间戳判断 Engine 是否"在写"，无法判断 Engine 是否真的在工作还是空转。增加两个字段：

1. **`active_task_count`**：该 workspace 在 Engine 全局 `active_tasks` 中的活跃任务数。0 表示空闲，>=1 表示繁忙
2. **`running_pids`**：该 workspace 下 `.ccc/pids/` 中仍在运行（有 `.pid` 文件且无 `.done` 文件）的 PID 列表。空列表表示无进程在跑

patrol 通过这两个字段的组合可以判断：
- `active_task_count=0, running_pids=[]` → Engine 健康空闲
- `active_task_count=0, running_pids≠[]` → Engine 可能挂了但残留进程（异常）
- `active_task_count≥1, running_pids=[]` → Engine 声明有任务但无进程（潜在死锁）

**核心设计**：不新增依赖，不修改 patrol。只增强 heartbeat 数据，patrol 消费者日志或后续版本自行利用新增字段。Patrol 通过 `check_heartbeat()` 返回的 `hb_dict` 自然能读到新字段。

### 怎么做

**1a. `scripts/ccc-engine.py`** — 新增 `_get_running_pids()` 辅助函数（建议插入在 `_write_heartbeat` 之前，约 L1932）：

```python
def _get_running_pids(ws: Path) -> list[int]:
    """扫描 .ccc/pids/ 目录，返回没有对应 .done 标记的 PID 列表。

    用于 heartbeat 报告当前 workspace 正在运行哪些进程。
    静默跳过不可读或无 ID 的文件。
    """
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return []
    result: list[int] = []
    for f in sorted(pids_dir.iterdir()):
        if not f.suffix == ".pid":
            continue
        subid = f.stem
        if (pids_dir / f"{subid}.done").exists():
            continue
        try:
            pid = int(f.read_text().strip())
            if pid > 0:
                result.append(pid)
        except (ValueError, OSError):
            pass
    return result
```

**1b. `scripts/ccc-engine.py`** — `_write_heartbeat()` 函数签名和体（L1932-1943）：

函数签名新增两个可选参数（向后兼容，无默认值变化不破坏调用）：
```python
def _write_heartbeat(
    ws: Path,
    running_task_id: str | None,
    active_task_count: int = 0,
    running_pids: list[int] | None = None,
) -> None:
```

函数体内新增：
```python
hb = {
    "workspace": str(ws),
    "running": running_task_id or None,
    "active_task_count": active_task_count,
    "running_pids": running_pids or [],
    "timestamp": now_iso(),
}
```

**1c. `scripts/ccc-engine.py`** — L1479-1481（活跃分支调用处）：

```python
ws_first_running: dict[str, str | None] = {}
ws_active_counts: dict[str, int] = {}
for info in active_tasks.values():
    ws_key = str(info["workspace"])
    if ws_key not in ws_first_running:
        ws_first_running[ws_key] = info["task_id"]
    ws_active_counts[ws_key] = ws_active_counts.get(ws_key, 0) + 1
for ws in workspaces:
    ws_key = str(ws)
    running_task_id = ws_first_running.get(ws_key)
    ws_count = ws_active_counts.get(ws_key, 0)
    ws_pids = _get_running_pids(ws) if running_task_id else []
    _write_heartbeat(ws, running_task_id, ws_count, ws_pids)
```

**1d. `scripts/ccc-engine.py`** — L1522（空闲分支调用处）：

```python
_write_heartbeat(ws, None, 0, [])
```

### 验收清单

- [ ] `_get_running_pids()` 正确扫描 `.ccc/pids/*.pid`，只返回无 `.done` 标记的 PID
- [ ] heartbeat JSON 新增 `active_task_count` 和 `running_pids` 字段
- [ ] 活跃分支：active_task_count = 该 workspace 在 active_tasks 中的条目数
- [ ] 活跃分支：running_pids 包含正在运行的 PID（通过 pids/ 目录推断）
- [ ] 空闲分支：active_task_count=0, running_pids=[]
- [ ] `_write_heartbeat()` 签名向后兼容（不破坏现有调用）
- [ ] pids 目录不存在时静默返回空列表，不抛异常
- [ ] `python3 -m compileall -q scripts/ccc-engine.py` 零错误
- [ ] 所有现有测试通过

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-engine.py` → 0 errors
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过
- [heartbeat 格式] 启动 Engine 后检查 `.ccc/engine-heartbeat.json`，应包含 `workspace`/`running`/`timestamp`/`active_task_count`/`running_pids` 五个字段
- [空闲心跳] Engine 空闲时 heartbeat 的 `active_task_count`=0, `running_pids`=[]
- [有任务时] Engine 执行 task 时 heartbeat 的 `active_task_count`≥1，`running_pids` 非空
- [pids 目录不存在] 删除 `.ccc/pids` 目录后 Engine 仍能正常写 heartbeat，`running_pids`=[]
- [向后兼容] 不修改 `_write_heartbeat` 调用处已有的参数位置，只增加可选参数
- [import ok] `python3 -c "import sys; sys.path.insert(0,'scripts/'); from ccc_engine import _get_running_pids, _write_heartbeat; print('ok')"` (注：ccc-engine.py 直接运行，非模块，此验收点仅验证语法可用)

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | _write_heartbeat 增加 active_task_count + running_pids 字段，新增 _get_running_pids 辅助，更新两个调用点 | `feat(engine): 心跳增加活跃任务数和 PID 列表 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-engine.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-engine.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] heartbeat JSON 向后兼容——已存的心跳文件不影响读取，新增字段仅在写入时生效

---

## 后续步骤

未来 patrol 可以利用新增字段优化判断逻辑：
- `active_task_count=0, running_pids≠[]` → Engine 声明空闲但有残留进程 → 自动清理
- `active_task_count≥1, running_pids=[]` → 声明有任务但无可观测进程 → 触发 Engine 重启
- 当前 patrol 的 `ensure_engine_healthy()` 只用了时间戳判断，后续可升级到多维度判断