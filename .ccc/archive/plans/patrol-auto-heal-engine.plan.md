# Plan: patrol-auto-heal-engine — Patrol 自动修复 Engine 增强（日志 + 通知）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（多 workspace 巡检主程序）
- **当前结构要点**：
  1. `ccc-patrol-v4.py:164-187` `ensure_engine_healthy()` 已具备自动重启 Engine 能力——检测到死亡时通过 3 种方式（launchctl bootstrap / launchctl load / python3 后台）兜底，返回 `"OK"` / `"RESTARTED"` / `"DEAD"`
  2. `ccc-patrol-v4.py:561-583` `commit_engine_restart()` 会在 restart 后 `git commit --allow-empty` 记录事件
  3. `ccc-patrol-v4.py:633-635` main() 中 RESTARTED 分支只调 `commit_engine_restart()`，**没有结构化日志文件和桌面通知**
  4. `ccc-patrol-v4.py:624-631` main() 中 DEAD 分支**静默退出（exit 1）**，没有告警
  5. `scripts/ccc-notify.sh` 已有 L1/L2/L3 三级通知能力（L2: 通知面板, L3: +Basso 声音），被 `ccc-engine.py` 使用但 patrol-v4.py 未引用
  6. `~/.ccc/logs/` 目录已由日志轮转方案创建，`engine.log` 已存在
- **待改动点**：
  - `ccc-patrol-v4.py:635`（RESTARTED 分支）追加日志写入 + L2 通知
  - `ccc-patrol-v4.py:625-631`（DEAD 分支）追加日志写入 + L3 带声音告警

---

## 范围

- **目标**：Engine 被 patrol 自动重启时写 JSONL 事件日志到 `~/.ccc/logs/engine-restarts.jsonl`，发送桌面通知；Engine 完全死亡（无法重启）时写日志 + L3 带声音告警
- **只改文件**：`scripts/ccc-patrol-v4.py`
- **不改文件**：`scripts/ccc-engine.py`、`scripts/ccc-engine.sh`、`scripts/ccc-notify.sh`、`scripts/ccc-board.py`、`.plist`、`tests/`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：添加重启日志 JSONL + 桌面通知

### 做什么

当前 patrol 已能自动重启 Engine，但重启事件缺少可追溯的结构化日志（git commit 不便程序化查询），且用户无感知——Engine 崩溃到恢复的间隙无人知晓。

改为：
1. `/Users/apple/.ccc/logs/engine-restarts.jsonl` 记录每次重启事件（JSONL 格式），含时间戳、状态（RESTARTED/DEAD）、原因
2. Engine 重启成功时触发 L2 桌面通知："Patrol-v4 检测到 Engine 已停止，已自动重启"
3. Engine 完全死亡（无法重启）时触发 L3 带声音告警："Patrol-v4 尝试自动重启 Engine 失败，需人工介入"
4. 已累积的 `patrol-state.json` 会记录 engine 状态，但新增的 JSONL 日志更便于外部工具（如 Cockpit 仪表盘）消费

### 怎么做

**1. `ccc-patrol-v4.py` 添加日志文件路径常量**（L35 `PATROL_STATE_FILE` 之后，约 L36）：

```python
RESTART_LOG = HOME / ".ccc" / "logs" / "engine-restarts.jsonl"
```

**2. 新增 `_log_engine_restart()` 函数**（`commit_engine_restart()` 之前，约 L559-L560 之间）：

```python
def _log_engine_restart(status: str, reason: str) -> None:
    """记录 Engine 重启/死亡事件到 JSONL 日志。幂等不抛异常。

    Args:
        status: "RESTARTED"（重启成功）或 "DEAD"（无法重启）
        reason: 描述原因，如 "patrol-v4 detected Engine dead, auto-restarted"
    """
    RESTART_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now_iso(),
        "status": status,
        "reason": reason,
    }
    try:
        with RESTART_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 日志不可写不影响 patrol 主流程
```

**3. 新增 `_notify_engine_restart()` 函数**（`_log_engine_restart` 之后）：

```python
def _notify_engine_restart(status: str) -> None:
    """Engine 重启/死亡时发桌面通知。非阻塞，不抛异常。"""
    notify_script = CCC_HOME / "scripts" / "ccc-notify.sh"
    if not notify_script.is_file():
        return
    if status == "RESTARTED":
        subprocess.Popen(
            ["bash", str(notify_script), "L2", "Engine 自动重启",
             "Patrol-v4 检测到 Engine 已停止，已自动重启完成"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    elif status == "DEAD":
        subprocess.Popen(
            ["bash", str(notify_script), "L3", "Engine 重启失败",
             "Patrol-v4 尝试自动重启 Engine 失败，需人工介入"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
```

**4. 修改 main() 中 RESTARTED 分支**（L633-635）：

原代码：
```python
if engine_status == "RESTARTED":
    engine_operated = True
    commit_engine_restart("restarted by patrol-v4")
```

改为：
```python
if engine_status == "RESTARTED":
    engine_operated = True
    _log_engine_restart("RESTARTED", "patrol-v4 detected Engine dead, auto-restarted")
    _notify_engine_restart("RESTARTED")
    commit_engine_restart("restarted by patrol-v4")
```

**5. 修改 main() 中 DEAD 分支**（L624-631）：

原代码：
```python
if engine_status in ("DEAD",):
    ws_stats = scan_all_ws(WORKSPACES)
    report = format_report(ws_stats, engine_status, [], [], [
        "Engine DEAD — cannot continue"])
    print(report)
    save_patrol_state(ws_stats, engine_status, [], 0, "Engine DEAD")
    return 1
```

改为：
```python
if engine_status in ("DEAD",):
    _log_engine_restart("DEAD", "patrol-v4 failed to restart Engine")
    _notify_engine_restart("DEAD")
    ws_stats = scan_all_ws(WORKSPACES)
    report = format_report(ws_stats, engine_status, [], [], [
        "Engine DEAD — cannot continue"])
    print(report)
    save_patrol_state(ws_stats, engine_status, [], 0, "Engine DEAD")
    return 1
```

### 验收清单

- [ ] Engine 正常存活时 patrol 不写重启日志、不发通知
- [ ] Engine 死亡后被 patrol 自动重启（RESTARTED）→ `engine-restarts.jsonl` 写入一条 `"status":"RESTARTED"` 记录，桌面出现 L2 通知
- [ ] Engine 死亡且 patorl 无法重启（DEAD）→ `engine-restarts.jsonl` 写入 `"status":"DEAD"`，出现 L3 带声音通知
- [ ] `engine-restarts.jsonl` 每行是合法 JSON
- [ ] 日志目录 `~/.ccc/logs/` 不存在时自动创建
- [ ] 日志文件不可写时不抛异常（`OSError` 被捕获）
- [ ] 无新增外部依赖（`subprocess.Popen` + `json` 已 import）

### 验收

- [RESTARTED 日志验证] `tail -1 ~/.ccc/logs/engine-restarts.jsonl | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); assert d['status']=='RESTARTED'"` 无异常（需先模拟一次 Engine kill + patrol 轮训后检查）
- [DEAD 日志验证] `tail -1 ~/.ccc/logs/engine-restarts.jsonl | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); assert d['status']=='DEAD'"`（需模拟重启失败场景）
- [JSONL 合法性] `tail -3 ~/.ccc/logs/engine-restarts.jsonl 2>/dev/null | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]"` 无异常
- [编译通过] `python3 -m compileall -q scripts/ccc-patrol-v4.py` 返回 0
- [通知行为] RESTARTED 时 macOS 通知面板弹出 "Engine 自动重启"；DEAD 时带 Basso 声音

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | patrol-v4 在 Engine 重启/死亡时写 JSONL 日志 + L2/L3 桌面通知 | `feat(patrol): Engine 重启/死亡事件写入 JSONL 日志 + 桌面通知 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/ccc-patrol-v4.py`）
- [ ] `engine-restarts.jsonl` 每行合法 JSON（需模拟重启后验证）
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

部署后（patrol-v4 自动触发执行，无需重启服务）观察 `~/.ccc/logs/engine-restarts.jsonl` 内容。
已有 `patrol-state.json` 冗余保留 engine 状态，删除时机待定。