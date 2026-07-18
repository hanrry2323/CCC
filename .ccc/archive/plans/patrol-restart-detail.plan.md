# Plan: patrol-restart-detail — Engine 重启 commit 增加 PID/uptime/看板快照

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制 -->
- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（863 行，单文件无分模块）
- **当前结构要点**：
  1. `commit_engine_restart()`（L711-740）在 Engine 重启后单独 `git commit --allow-empty`，commit message 只有 `"chore: patrol-v4 engine restart ({reason})"`，**无正文**
  2. `_log_engine_restart()`（L655-672）写 JSONL 日志，但只有 `ts`/`status`/`reason`，无 PID/uptime/看板快照
  3. `ensure_engine_healthy()`（L173-196）封装了杀 + 重启流程，返回 `"OK"`/`"RESTARTED"`/`"DEAD"`，但不暴露新 PID 或旧 uptime
  4. `engine-heartbeat.json` 存有 `timestamp` 和 `running` 字段，来自 Engine 自身写入——可作为 uptime 计算的原始数据
  5. `scan_all_ws()`（L283-291）通过 `read_board_index()` 遍历目录获取板快照，无副作用，可在任何时机调用
  6. `main()`（L777）在 Step 0 检测到 RESTARTED 后立即调 `commit_engine_restart()`，此时 `ws_stats` 尚未计算——需先获取看板数据再 commit
- **待改动点**：
  - 新增 engine PID 捕获函数 `_get_engine_pid()`
  - 新增 uptime 计算函数 `_get_engine_uptime()`
  - 修改 `commit_engine_restart()` 签名，接受额外参数写 commit body
  - 修改 `main()` 中 RESTARTED 分支：先扫描看板 → 再 commit → 继续后续流程

---

## 范围

- **目标**：patrol 重启 Engine 时 commit 包含新 PID、旧 uptime、重启前看板快照
- **只改文件**：`["scripts/ccc-patrol-v4.py"]`
- **不改文件**：`["scripts/ccc-engine.py", "scripts/_board_store.py", "scripts/ccc-board.py"]`
- **执行方式**：`manual`
- **Phase 数**：1（4 subtasks）

---

## 改动 1（Phase 1）：commit_engine_restart 增加详细 commit body

### 做什么

当前 `commit_engine_restart()` 只写一行 subject：
```
chore: patrol-v4 engine restart (restarted by patrol-v4)
```

增强后 commit 包含完整 body：
```
chore: patrol-v4 engine restart (restarted by patrol-v4)

PID: 12345
Uptime: 45m12s (before restart)
Board: CCC(pl:2 ip:1 rel:5 ab:0) qxo(pl:0 ip:0 rel:10 ab:0) ...
```

其中：
- **PID** = 重启后的 Engine 进程号（从 `ps aux` 提取）
- **Uptime** = 重启前 Engine 运行时长（从 `engine-heartbeat.json` 的 timestamp 计算）
- **Board** = 重启前各 workspace 看板计数快照（从 `read_board_index()` 获取）

同时更新 `_log_engine_restart()` 也在 JSONL 日志中记录这些字段。

### 怎么做

**`scripts/ccc-patrol-v4.py`**：

**1.1 新增 `_get_engine_pid()`**（接在 `_notify_engine_restart` 后，约 L708）：

```python
def _get_engine_pid() -> int | None:
    """从 ps 输出获取 ccc-engine.py 进程 PID。重启后调用以记录新 PID。"""
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.splitlines():
            if "ccc-engine.py" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None
```

**1.2 新增 `_get_engine_uptime()`**（接在 `_get_engine_pid` 后）：

```python
def _get_engine_uptime() -> str:
    """从 engine-heartbeat.json 的 timestamp 计算 Engine 运行时长。
    
    在重启 Engine 前调用，读取旧心跳的时间戳计算 uptime。
    返回人类可读字符串如 "45m12s"，无法获取时返回 "unknown"。
    """
    hb_file = CCC_HOME / ".ccc" / "engine-heartbeat.json"
    if not hb_file.exists():
        return "unknown"
    hb = json_load(hb_file)
    if not hb:
        return "unknown"
    ts_str = hb.get("timestamp", "")
    if not ts_str:
        return "unknown"
    try:
        if ts_str.endswith("Z"):
            hb_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        elif "+" in ts_str:
            hb_ts = datetime.fromisoformat(ts_str)
        else:
            hb_ts = datetime.fromisoformat(ts_str + "+00:00")
        age = datetime.now(timezone.utc) - hb_ts
        total_secs = int(age.total_seconds())
        if total_secs < 60:
            return f"{total_secs}s"
        elif total_secs < 3600:
            return f"{total_secs // 60}m{total_secs % 60}s"
        else:
            h, remainder = divmod(total_secs, 3600)
            return f"{h}h{remainder // 60}m"
    except (ValueError, TypeError):
        return "unknown"
```

**1.3 修改 `commit_engine_restart()`**（L711-740）：

```python
def commit_engine_restart(
    reason: str,
    ws_stats: dict[str, dict] | None = None,
    pid: int | None = None,
    uptime: str = "unknown",
) -> None:
    """Engine 重启后 commit，包含 PID/uptime/看板快照正文"""
    ws_path = CCC_HOME
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws_path, capture_output=True, timeout=5,
        )
        if r.returncode != 0:
            return
    except OSError:
        return

    # 构造 commit body
    body_lines = []
    if pid is not None:
        body_lines.append(f"PID: {pid}")
    body_lines.append(f"Uptime: {uptime} (before restart)")
    if ws_stats:
        parts = []
        for name in sorted(ws_stats.keys()):
            c = ws_stats.get(name, {})
            if isinstance(c, dict):
                parts.append(
                    f"{name}(pl:{c.get('planned', 0)} ip:{c.get('in_progress', 0)} "
                    f"rel:{c.get('released', 0)} ab:{c.get('abnormal', 0)})"
                )
            else:
                parts.append(f"{name}:{c}")
        body_lines.append("Board: " + " ".join(parts))

    commit_msg = f"chore: patrol-v4 engine restart ({reason})"
    if body_lines:
        commit_msg += "\n\n" + "\n".join(body_lines)

    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", commit_msg],
        cwd=ws_path, capture_output=True, timeout=15,
    )
```

**1.4 修改 `main()` 中 RESTARTED 分支**（L799-805）：

在 `ensure_engine_healthy()` 与重启 commit 之间插入看板扫描和元数据捕获：
- 先读 uptime（重启前读旧心跳）
- 扫描所有 workspace 获取看板快照
- 重启 Engine（已在 `ensure_engine_healthy()` 内部完成）
- 捕获新 PID（重启后读新进程）
- 传入 `commit_engine_restart()`

```python
    if engine_status == "RESTARTED":
        engine_operated = True
        engine_pid = _get_engine_pid()              # 重启后 PID
        engine_uptime = _get_engine_uptime()         # 重启前 uptime
        board_snapshot = scan_all_ws(WORKSPACES)     # 重启前看板快照（已在 Engine 死后，但 board 文件未被改）
        _log_engine_restart(
            "RESTARTED", "patrol-v4 detected Engine dead, auto-restarted"
        )
        _notify_engine_restart("RESTARTED")
        # 推迟 ws_stats 的赋值：board_snapshot 先保存，后面 Step 1 会重新扫描最新状态
        restart_ws_snapshot = board_snapshot
        commit_engine_restart(
            "restarted by patrol-v4",
            ws_stats=restart_ws_snapshot,
            pid=engine_pid,
            uptime=engine_uptime,
        )
```

注意：由于 `scan_all_ws()` 后续在 Step 1 也会被调用并赋值给 `ws_stats`，此处暂存 `restart_ws_snapshot` 传给 commit，后边 Step 1 的 `ws_stats = scan_all_ws(...)` 覆盖为新数据——这是期望行为（Step 5 的 `commit_patrol_fix` 用新的 board 数据）。

### 验收清单

- [ ] Engine 重启后 commit 正文包含 `PID: <number>` 行
- [ ] commit 正文包含 `Uptime: <duration>` 行
- [ ] commit 正文包含 `Board: CCC(...) qxo(...) ...` 行（含 ≥ 2 workspace）
- [ ] Engine 未重启时（engine_status == "OK"），commit_engine_restart 未被调用，无影响
- [ ] Engine DEAD 时，无 commit、无副作用
- [ ] _get_engine_pid 正确返回 int 或 None（无进程时）
- [ ] _get_engine_uptime 从心跳文件正确计算时长，缺心跳时返回 "unknown"
- [ ] `python3 -m compileall -q scripts/ccc-patrol-v4.py` 零错误
- [ ] 不影响 Step 1-6 其他流程逻辑

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-patrol-v4.py` → 0 errors
- [导入检查] `python3 -c "import sys; sys.path.insert(0,'scripts/'); exec(open('scripts/ccc-patrol-v4.py').read().split('def main')[0]); print('import ok')"` → import ok
- [commit body 检查] 人工触发 Engine 重启（或测试时 mock），观察 git log 正文（参考：`git log -1 --format="%B"`）
- [边界：无心跳文件] `_get_engine_uptime()` 返回 "unknown"
- [边界：无 pid] `_get_engine_pid()` 返回 None，commit body 不包含 PID 行
- [回归走读] main() 中 RESTARTED 分支的 ws_stats 赋值不干扰 Step 1 正常扫描

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `commit_engine_restart` 增加 PID/uptime/看板快照正文 | `feat(patrol): engine 重启 commit 增加 PID/uptime/看板快照 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤（可选）

完成后可考虑将 `_log_engine_restart()` 也同步记录 PID 和 uptime，增强 JSONL 日志的排查价值。本次暂不改：task 范围限定在 commit 增强。