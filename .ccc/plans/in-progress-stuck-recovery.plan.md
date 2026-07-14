```markdown
# Plan: in-progress-stuck-recovery — in_progress 卡死任务自动恢复增强

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（695 行，无分模块）
- **当前结构要点**：
  1. `check_stuck_tasks()`（L372-432）是唯一的卡死检测函数：检查 in_progress 下每个 task 的文件 age 和进程存活。只区分两档阈值（STUCK_THRESHOLD=300s 且无进程 → planned；FORCE_MV_THRESHOLD=1800s → planned），不检测 zombie 状态和 crash loop
  2. 进程存活检测用 `os.kill(pid, 0)` 检查 PID 是否存在（L397-403），但 zombie 进程也会响应 kill 0（进程表项存在），因此当前检测无法区分"正常进程"和"zombie 进程"
  3. PID 信息来源于 `~/.ccc/opencode-pids/<task_id>.pid`（opencode-exec.py L168-169 在子进程启动后写入，finally 中 L213-214 删除）。若 opencode 异常崩溃（SIGKILL/系统 OOM），finally 不执行 → PID 文件残留
  4. `save_patrol_state()`（L437-474）将本轮状态追加到 `~/.ccc/patrol-state.json`，保留最近 6 轮，但只存列级计数，不存 per-task 卡死次数
  5. 无 `patrol-state.json` 的统一读写入口——`detect_stagnation()`(L477) 自己读 json 解析，`save_patrol_state()` 自己写
- **待改动点**：
  - `scripts/ccc-patrol-v4.py:check_stuck_tasks()`（L372-432）增强 zombie 检测、crash loop 检测、≥3 次卡死走 backlog
  - 新加 zombie 检测工具函数 `_is_zombie_pid()`
  - 新加 crash loop 检测函数 `_detect_crash_loop()`
  - `patrol-state.json` 新增 `stuck_tasks: {task_id: count}` 持久化字段
  - `save_patrol_state()` / `main()` 增加 stuck_tasks 的读写传递

---

## 范围

- **目标**：in_progress 卡死任务增加 zombie 检测、crash loop 检测、超过 3 次卡死自动退 backlog
- **只改文件**：`scripts/ccc-patrol-v4.py`
- **不改文件**：`scripts/ccc-engine.py`、`scripts/ccc-board.py`、`scripts/_board_store.py`、`scripts/opencode-exec.py`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：check_stuck_tasks 三增强

### 做什么

当前 `check_stuck_tasks()` 只检测文件 age（300s/1800s）和进程有无（kill 0），错过三个场景：
1. **zombie 进程**：进程表项存在（kill 0 返回 True）但已是 defunct，实际不再执行，task 永远不会自己前进
2. **opencode crash loop**：PID 文件残留、进程反复崩溃重启，task 反复进出 in_progress
3. **反复卡死**：同一 task 被卡死移回 planned → Engine 重新调度 → 再次卡死，循环 ≥3 次

三者的修复方向一致——检测到后不走 planned（Engine 会重新调度导致循环），而是退 backlog 人工介入。

### 怎么做

**`scripts/ccc-patrol-v4.py`**：

**1. 新加工具函数 `_is_zombie_pid()`**（接在 `_move_task` 之后、`check_stuck_tasks` 之前，约 L367）：

```python
def _is_zombie_pid(pid: int) -> bool:
    """检测 PID 是否为 zombie (defunct) 进程。
    
    macOS/Linux 均可用 ps -o state 检测状态为 'Z' 的进程。
    zombie 进程已死但未 reap，pid 表项残留，kill(0) 返回成功。
    """
    try:
        r = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return False
        state = r.stdout.strip()
        # 'Z'/'Z+'/'Zs' 等 → zombie
        return state.startswith("Z")
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return False
```

**2. 新加 crash loop 检测函数 `_detect_crash_loop()`**（接在 `_is_zombie_pid` 之后）：

```python
def _detect_crash_loop(tid: str) -> bool:
    """检测 opencode 是否 crash loop。
    
    检查 ~/.ccc/opencode-pids/ 中匹配该 task_id 的 pid 文件：
    - pid 文件存在但进程已死 → stale 残留
    - 残留数 ≥ 2 → crash loop 信号
    这是在线检测：只看当前文件系统快照，不依赖历史 patrol 数据。
    """
    if not PID_DIR.is_dir():
        return False
    stale_count = 0
    for pid_file in PID_DIR.iterdir():
        if tid in pid_file.name:
            try:
                pid_str = pid_file.read_text().strip()
                pid = int(pid_str)
                try:
                    os.kill(pid, 0)
                    # 进程存在，检查是否 zombie
                    if _is_zombie_pid(pid):
                        stale_count += 1
                except (OSError, ProcessLookupError):
                    stale_count += 1
            except (ValueError, OSError):
                stale_count += 1
    return stale_count >= 2
```

**3. 新增 stuck 计数器持久化函数**（接在 `_detect_crash_loop` 之后）：

```python
def _load_stuck_counters() -> dict[str, int]:
    """从 patrol-state.json 加载 per-task stuck 计数。无状态文件返回空 dict。"""
    if not PATROL_STATE_FILE.exists():
        return {}
    try:
        state = json.loads(PATROL_STATE_FILE.read_text())
        return state.get("stuck_tasks", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_stuck_counters(counters: dict[str, int]) -> None:
    """持久化 per-task stuck 计数到 patrol-state.json。幂等，不抛异常。"""
    try:
        state: dict = {"rounds": []}
        if PATROL_STATE_FILE.exists():
            try:
                state = json.loads(PATROL_STATE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                state = {"rounds": []}
        state["stuck_tasks"] = counters
        PATROL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PATROL_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False) + "\n")
    except OSError:
        pass
```

**4. 修改 `check_stuck_tasks()` 签名和逻辑**（L372-432）：

```python
def check_stuck_tasks(ws_name: str, ws: Path, stuck_counters: dict[str, int] | None = None) -> tuple[list[str], dict[str, int]]:
    """检查 in_progress 任务卡死。返回 (操作列表, 更新后的 stuck_counters)。"""
    if stuck_counters is None:
        stuck_counters = {}
    if ws_name in READ_ONLY_WS:
        return ["skip (read-only)"], stuck_counters

    ops: list[str] = []
    ip_dir = ws / ".ccc" / "board" / "in_progress"
    if not ip_dir.is_dir():
        return ops, stuck_counters

    for f in sorted(ip_dir.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        tid = f.stem
        age = file_age_seconds(f)
        if age is None:
            continue

        # --- 增强：进程存活检测（含 zombie）---
        process_alive = False
        is_zombie = False
        if PID_DIR.is_dir():
            for pid_file in PID_DIR.iterdir():
                if tid in pid_file.name:
                    try:
                        pid_str = pid_file.read_text().strip()
                        pid = int(pid_str)
                        os.kill(pid, 0)
                        process_alive = True
                        if _is_zombie_pid(pid):
                            is_zombie = True
                        break
                    except (ValueError, OSError, ProcessLookupError):
                        pass

        # ps 兜底
        if not process_alive:
            try:
                r = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in r.stdout.splitlines():
                    if tid in line and "grep" not in line:
                        process_alive = True
                        break
            except (subprocess.TimeoutExpired, OSError):
                pass

        # --- 增强：crash loop 检测 ---
        is_crash_loop = _detect_crash_loop(tid)

        # --- 增强：stuck 次数决策 ---
        stuck_count = stuck_counters.get(tid, 0)
        target: str | None = None

        if age > FORCE_MV_THRESHOLD:
            if is_zombie or is_crash_loop or stuck_count >= 3:
                target = "backlog"
            else:
                target = "planned"
            ops.append(f"{tid}: stuck {age}s > {FORCE_MV_THRESHOLD}s → {target} (force)")
        elif age > STUCK_THRESHOLD and not process_alive:
            if stuck_count >= 3 or is_crash_loop:
                target = "backlog"
            else:
                target = "planned"
            ops.append(f"{tid}: stuck {age}s, no process → {target}")
        elif age > STUCK_THRESHOLD and process_alive:
            if is_zombie:
                if stuck_count >= 3 or is_crash_loop:
                    target = "backlog"
                else:
                    target = "planned"
                ops.append(f"{tid}: zombie {age}s → {target}")
            else:
                ops.append(f"{tid}: running {age}s (alive, no action)")
        else:
            ops.append(f"{tid}: active {age}s (normal)")

        if target:
            _move_task(ws, tid, "in_progress", target)
            stuck_count += 1
            stuck_counters[tid] = stuck_count

    return ops, stuck_counters
```

**5. 修改 `main()` 中 Step 3 的调用**（L696-707）：

插入 stuck 计数器的加载和持久化：

```python
    # Step 1-2 之后、Step 3 之前加载
    stuck_counters: dict[str, int] = _load_stuck_counters()

    # Step 3 调用
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ops, stuck_counters = check_stuck_tasks(name, path, stuck_counters)
        ...

    # Step 3 之后持久化
    _save_stuck_counters(stuck_counters)
```

同时在 Step 4（save_patrol_state）调用之前确保 stuck_counters 已持久化。

### 验收清单

- [ ] zombie PID 能被检测到（进程 kill(0) 返回 True，但 ps state 为 Z）
- [ ] 正常运行的进程不会被误判为 zombie
- [ ] opencode PID 残留 ≥ 2 个匹配同一 task → crash loop 标记
- [ ] 正常（无残留）→ 无 crash loop 标记
- [ ] stuck_count < 3 + 非 zombie + 非 crash loop → 照常移 planned
- [ ] stuck_count ≥ 3 → 即使无 zombie/crash loop 也移 backlog
- [ ] zombie 进程 + stuck_count ≥ 3 → 移 backlog
- [ ] crash loop 检测结果 → 移 backlog
- [ ] FORCE_MV_THRESHOLD（1800s）的旧逻辑保留，只增强目标列决策
- [ ] stuck 计数器在 patrol-state.json 中持久化，重启 patrol 后读取
- [ ] `scripts/ccc-patrol-v4.py` 编译无错误
- [ ] 不影响现有 triage_abnormal（abnormal→released/planned/backlog 逻辑不变）

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-patrol-v4.py` → 0 errors
- [zombie 检测] `python3 -c "import sys; sys.path.insert(0,'scripts/'); exec(open('scripts/ccc-patrol-v4.py').read().split('def main')[0]); print('import ok')"` 可导入
- [crash loop] 测试：PID_DIR 有一个残留 pid 文件（进程已死）→ `_detect_crash_loop` 返回 False（< 2）；两个残留 → 返回 True
- [stuck 计数器持久化] `grep -c 'stuck_tasks' ~/.ccc/patrol-state.json` 在 patrol 完成后 = 1
- [功能逻辑] 走读代码验证：zombie 分支、crash loop 分支、stuck_count ≥ 3 分支各对应 backlog 目标列
- [回归] 从 FORCE_MV_THRESHOLD 分支 `target` 赋值确认不影响现有流程结构

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | check_stuck_tasks 三增强：zombie/crash-loop/≥3次退backlog | `feat(patrol): in_progress 卡死任务自动恢复增强—zombie检测+crash-loop检测+≥3次退backlog (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
```