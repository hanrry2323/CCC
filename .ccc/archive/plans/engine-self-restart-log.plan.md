# Plan: engine-self-restart-log — Engine 自重启写结构化日志

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.py`（~2284 行）
- **当前结构要点**：
  1. Engine 生命周期起点：`main()`（L2126）→ `engine_loop()`（L1345）。SIGTERM 信号处理在 `_handle_sigterm`（L2147），只设 `_engine_shutdown=True`，不写日志
  2. 退出路径有三条：SIGTERM 信号（L2147 → 循环退出 L1589）、KeyboardInterrupt（L2160）、`except Exception` 在主循环内捕获（L1579，打印后 continue，不退出）。没有统一的退出日志记录
  3. Patrol 已在 `scripts/ccc-patrol-v4.py` 中写 `~/.ccc/logs/engine-restarts.jsonl`（L698-715），格式为 `{"ts": ..., "status": ..., "reason": ...}`。Engine 本身不写此文件，重启事件只有 patrol 的外部视角
  4. 运行时长通过模块级 `_stats_started_at: float | None = time.time()`（L2177）追踪，Stats HTTP 端点（`:7776`）的 `uptime_sec` 字段由此推算
  5. `_handle_sigterm` 只是信号处理函数（L2147-2152），不能执行文件 I/O 之外的重操作。但写一行 JSONL 文件 I/O 属于轻量操作，信号安全级别可接受
- **待改动点**：
  - `scripts/ccc-engine.py`：新增 `_write_engine_restart()` 函数，在关键生命周期点调用
  - 启动点（engine_loop 入口）、SIGTERM 处理、KeyboardInterrupt 处理、atexit 兜底

---

## 范围

- **目标**：Engine 在启动、SIGTERM、Ctrl+C、意外崩溃时写结构化 JSON 日志（pid、uptime、原因）到 `~/.ccc/logs/engine-restarts.jsonl`（与 patrol 共享同一文件），便于 patrol 后续分析重启频率
- **只改文件**：`["scripts/ccc-engine.py"]`
- **不改文件**：`["scripts/ccc-patrol-v4.py", "scripts/_board_store.py", "scripts/ccc-board.py", "scripts/ccc-board-server.py"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：Engine 自重启结构化日志

### 做什么

Engine 当前在重启/退出时只在普通 logger 中写一行文本日志（`engine_log("Engine 终止")`），patrol 无法自动解析程序化判断。改为写入结构化 JSONL 日志，每条记录包含：

- **ts**：事件 ISO 时间戳
- **pid**：Engine 进程 PID
- **uptime_sec**：从 Engine 启动到事件发生时的运行秒数
- **status**：`"started"` / `"shutdown"` / `"stopped"` 三态
- **reason**：原因字符串或 `null`

覆盖四个事件点：
1. **Engine 启动** → `status: "started"`，patrol 可据此感知 Engine 新进程上线时间线
2. **SIGTERM 信号** → `status: "shutdown", reason: "SIGTERM"`，patrol 可区分故意关闭 vs 崩溃
3. **KeyboardInterrupt** → `status: "shutdown", reason: "KeyboardInterrupt"`，本地调试时记录
4. **atexit 兜底** → `status: "stopped", reason: "exit/by_crash"`，捕获 SIGTERM/KeyboardInterrupt 未覆盖的意外退出（如 `sys.exit()`、未捕获异常）

**核心设计**：文件路径复用 patrol 已定义的 `~/.ccc/logs/engine-restarts.jsonl`，JSONL 追加写，幂等（`_restart_log_written` 全局 flag 防止多写）。同时 Engine 写入和 patrol 写入不会冲突——Engine 写 `started/shutdown/stopped`，patrol 写 `RESTARTED/DEAD`，通过 `pid` 字段区分。

### 怎么做

**1a. `scripts/ccc-engine.py`** — 新增全局变量（模块级，建议插在 `_engine_shutdown` 附近，L82 之后）：

```python
_engine_start_ts: float = time.time()  # Engine 模块加载时间，uptime 基准
_restart_log_written: bool = False  # 幂等保护：每个生命周期最多写一条
_RESTART_LOG_PATH: Path = Path.home() / ".ccc" / "logs" / "engine-restarts.jsonl"
```

**1b. `scripts/ccc-engine.py`** — 新增 `_write_engine_restart()` 函数（建议插在 `_set_parallel_disabled` 之前，L90 附近，或 engine 函数区之前）：

```python
def _write_engine_restart(status: str, reason: str | None = None) -> None:
    """写入结构化重启日志到 ~/.ccc/logs/engine-restarts.jsonl。

    Args:
        status: "started" | "shutdown" | "stopped"
        reason: 描述原因，如 "SIGTERM" | "KeyboardInterrupt" | None（started 时为 None）
    """
    global _restart_log_written
    if _restart_log_written:
        return
    _restart_log_written = True
    uptime = max(0.001, time.time() - _engine_start_ts)
    entry = {
        "ts": now_iso(),
        "pid": os.getpid(),
        "uptime_sec": round(uptime, 3),
        "status": status,
        "reason": reason,
    }
    try:
        _RESTART_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _RESTART_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
```

**1c. `scripts/ccc-engine.py`** — Engine 启动点写 `"started"`。在 `engine_loop()` L1352 `engine_log("CCC Engine 启动...")` 之后插入：

```python
engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
# ...
_write_engine_restart("started")
```

**1d. `scripts/ccc-engine.py`** — SIGTERM 信号处理中写 `"shutdown"`。在 `_handle_sigterm`（L2147-2152）的 `engine_log("收到 SIGTERM, 优雅关闭中...")` 之后插入：

```python
_write_engine_restart("shutdown", "SIGTERM")
```

**1e. `scripts/ccc-engine.py`** — KeyboardInterrupt 处理写 `"shutdown"`。在 `main()` 的 `except KeyboardInterrupt:` 块（L2160-2161）中，在 `engine_log("Engine 关闭")` 之后插入：

```python
_write_engine_restart("shutdown", "KeyboardInterrupt")
```

**1f. `scripts/ccc-engine.py`** — 注册 `atexit` 兜底。在文件顶部新增 `import atexit`（按 alphabet 序插入 `import argparse` 之后）。在 `main()` 内，`signal.signal(...)` 之前注册：

```python
def _final_restart_log():
    if not _restart_log_written:
        _write_engine_restart("stopped", "exit/by_crash")
atexit.register(_final_restart_log)
```

### 验收清单

- [ ] Engine 启动时 `engine-restarts.jsonl` 追加一条 `status: "started"`，含 pid 和 uptime_sec
- [ ] SIGTERM 时写一条 `status: "shutdown", reason: "SIGTERM"`，uptime > 0
- [ ] Ctrl+C（KeyboardInterrupt）时写 `status: "shutdown", reason: "KeyboardInterrupt"`
- [ ] `atexit` 兜底在测试中能触发（KILL 模拟之外），幂等不重复写
- [ ] `_restart_log_written` 确保写一次后不再重复（atexit 不覆盖 SIGTERM 日志）
- [ ] 文件路径 `~/.ccc/logs/engine-restarts.jsonl` 目录不存在时自动创建
- [ ] 文件写失败时静默忽略（不抛异常，不中断 Engine 流程）
- [ ] `python3 -m compileall -q scripts/ccc-engine.py` 零错误
- [ ] 所有现有测试通过
- [ ] Engine 正常退出后，JSONL 文件至少包含一条 `started` + 一条 `shutdown`
- [ ] 多次 Engine 启停后，JSONL 文件包含多条记录可作时序分析

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-engine.py` → 0 errors
- [启动测试] timeout 3 启动 Engine，检查 `~/.ccc/logs/engine-restarts.jsonl` 最后一条是 `{"status": "started", ...}`
- [SIGTERM 测试] start Engine in background, sleep 1, `kill -TERM <PID>`, wait, 检查 JSONL 追加 `{"status": "shutdown", "reason": "SIGTERM", ...}`
- [KeyboardInterrupt 测试] timeout 3 启动 Engine，Ctrl+C 终止，检查 JSONL 含 `"started"` + `"shutdown"/"stopped"`
- [幂等] SIGTERM 后 atexit 不应重复写，JSONL 只应有 `started` + `shutdown` 两条
- [兼容性] Patrol 的 `_log_engine_restart()` 写入格式不冲突——Engine 新条目在 JSONL 中带 `pid` 和 `uptime_sec`，patrol 条目无这两字段，解析方通过区分字段即可分辨来源
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | Engine 启动/退出写结构化 JSONL 日志（pid/uptime/status/reason）到 engine-restarts.jsonl，含 SIGTERM、KeyboardInterrupt、atexit 兜底 | `feat(engine): 自重启写结构化日志（pid+uptime+原因） (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-engine.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-engine.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] JSONL 文件路径和 patrol 的定义一致（`~/.ccc/logs/engine-restarts.jsonl`），不引入新路径
- [ ] 写日志使用 try/except OSError 保护，不因写入失败影响 Engine 正常关闭流程

---

## 后续步骤

后续 patrol 可增强分析：
- 统计 recent N 条 engine-restarts 中 `"status": "stopped"` 的比例 → 估算非预期重启率
- 结合 patrol 自己的 `"RESTARTED"` 记录对比：Engine 写了 `"shutdown"` + Patrol 写了 `"RESTARTED"` 是正常重启链路；Engine 无 `"shutdown"` 的记录就是异常崩溃
- 在 Cockpit 中展示重启时间线