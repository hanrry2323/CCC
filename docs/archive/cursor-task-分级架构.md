# CCC Pipeline 分级架构 — Cursor 开发提示词

> **来源**：v0.34 架构审查（2026-07-16）
> **角色**：我（架构师）出方案，Cursor（开发者）实现，我审核
> **目标**：pipeline 有任务分级、有自我保护、有成本意识

---

## 一、架构问题总览

当前 CCC pipeline 只有一条路：

```
backlog → planned → in_progress → testing → verified → released
         ↓
    product_role    dev_role    reviewer+tester
    (Claude plan)   (opencode)  (LLM review + pytest)
```

**缺陷**：
1. **无任务分级** — 一行 type error 也走 `plan→exec→review→test` 全链路，成本远高于收益
2. **无 intake 分类** — audit_role 投什么 pipeline 就接什么，没有"这个 task 适合什么处理方式"的判断
3. **无自我保护** — product 失败 279 次引擎还在试，没有熔断
4. **成本不可见** — 不知道修一行 annotation 花了多少钱
5. **冗余的回顾策** — abnormal 列堆了东西没人自动清理

---

## 二、解决方案架构

### 2.1 任务分级（核心变更）

pipeline 入口加分类器，不再一刀切：

```
task 进入 backlog
  ↓
_classify_task_intake(task)
  ├─ "auto"        → ruff --fix + git commit → released（跳过整个 pipeline）
  ├─ "quick"       → dev_role(executor only) → testing → reviewer(small) → verified
  └─ "full"        → product_role → dev_role → reviewer+tester → verified  ← 现有流程
```

**分类规则**（`_classify_task_intake`，纯规则，不调 LLM）：

| 特征 | 分类 | 走什么 |
|------|------|--------|
| tags 含 `audit` + `review` | auto | ruff --fix + commit → released |
| tags 含 `auto` | auto | ruff --fix + commit → released |
| tags 含 `audit` + `decision` | full | 全链路（架构决策需要规划） |
| 描述 < 50 字 + 标题含 type/lint | auto | 类型标注/ lint 修 |
| 描述 < 100 字 + 标题含 fix/clean | quick | executor → reviewer(small) |
| 其他 | full | 全链路 |

### 2.2 Intake failsafe

投 task 前检查来源健康度，源头熔断：

```
audit_role 准备投 task 时：
  1. 查当前 workspace 的 abnormal 列
  2. 同类 audit-task 在 abnormal 占比 > 60%
  3. 如果是 → 不投，写 engine_log 说明原因
  4. 同时发桌面通知："audit 来源异常率高，intake 已熔断"
```

### 2.3 引擎自我保护（degraded mode）

监控滑动窗口，决定是否降级：

```
engine 每 60s 检查：
  - 过去 30 分钟 quarantine 数 > 10  → degraded
  - 过去 30 分钟 product_fail 数 > 10  → degraded
  - 过去 30 分钟 无任何 success  → degraded
  
degraded 模式下：
  - 不停引擎（继续跑 audit/maintenance）
  - 停 backlog → planned 的 intake（新 task 不进 pipeline）
  - 现有 in_progress/testing 继续跑完
  - 写 engine_log + 桌面通知
  - 等连续 10 分钟无新增异常 → 自动退出 degraded
```

### 2.4 成本可见

每个 task 生命周期结束（released 或 abnormal）时汇总成本：

```
task_cost_summary:
  - product_role: 调用次数 × ~$0.5  ≈ $X
  - dev_role: 调用次数 × 耗时 × ~$0.1/min  ≈ $X
  - reviewer: 调用次数 × ~$0.3  ≈ $X
  - tester: 运行次数 × 0  ≈ $0（pytest）
  - 总和: $X
```

写入 `task_cost_summary` 到 `.ccc/cost-telemetry.jsonl`（已有模块 `_cost_telemetry.py`）。

### 2.5 文件变更清单

| 文件 | 改动 |
|------|------|
| `scripts/ccc-engine.py` | 加 degraded mode、滑动窗口监控、intake 分流调用 |
| `scripts/ccc-board.py` | 加 `_classify_task_intake()`、加 `_run_auto_fix()`、加 `_run_quick_fix()`、audit intake 熔断 |
| `scripts/_cost_telemetry.py` | 加 `compute_task_cost(task_id)` |
| `scripts/_board_store.py` | 无改动 |
| `scripts/ccc-clean-abnormal.py` | 无改动 |

---

## 三、实现细节

### 3.1 `_classify_task_intake(task: dict) -> str`

位置：`ccc-board.py`，顶层函数。

```python
def _classify_task_intake(task: dict) -> str:
    """决定 task 的处理路径：auto | quick | full

    纯规则决策，不调 LLM，不读 phases.json。
    """
    tags = task.get("tags", [])
    title = task.get("title", "")
    desc = task.get("description", "")
    tid = task.get("id", "")
    
    # 1. auto: audit review 或 lint 类
    if "audit" in tags and "review" in tags:
        return "auto"
    if "auto" in tags:
        return "auto"
    if tid.startswith("audit-review-"):
        return "auto"
    # 描述有 type error 特征
    if any(kw in title.lower() for kw in ["type:", "lint:", "ruff:", "mypy:"]):
        return "auto"
    
    # 2. quick: 小改动
    if len(desc) < 100 and any(kw in title.lower() for kw in ["fix", "clean", "typo", "fast"]):
        return "quick"
    if "audit" in tags and "decision" not in tags:
        return "quick"
    
    # 3. full: 全链路
    return "full"
```

### 3.2 `_run_auto_fix(task: dict) -> dict`

位置：`ccc-board.py`，顶层函数。

```python
def _run_auto_fix(task: dict) -> dict:
    """自动修路径：ruff --fix → git commit → released

    Returns:
        {"ok": bool, "commit": str|None, "error": str|None}
    """
    ws = get_workspace()
    # ruff --fix（不含 --exclude src，因类型标注在源码）
    rc = subprocess.run(
        ["ruff", "check", "--fix", "."],
        cwd=ws, capture_output=True, text=True, timeout=60,
    )
    # 检查工作树是否有改动
    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=ws, capture_output=True, text=True, timeout=5,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ws, capture_output=True, text=True, timeout=5,
    )
    changed = (diff.stdout or "").strip() + (untracked.stdout or "").strip()
    if not changed:
        return {"ok": False, "commit": None, "error": "ruff 无改动"}
    
    # git commit
    subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True, timeout=5)
    msg = f"chore(audit): auto-fix {task['id']}"
    r = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=ws, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        return {"ok": False, "commit": None, "error": r.stderr[:100]}
    
    commit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ws, capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    
    return {"ok": True, "commit": commit_hash, "error": None}
```

### 3.3 `_run_quick_fix(task: dict) -> dict`

位置：`ccc-board.py`。

```python
def _run_quick_fix(task: dict) -> dict:
    """快修路径：executor（不给 plan）+ reviewer(small)

    和 dev_role 类似，只是：
    - 没有 product_role 写 plan
    - executor prompt 直接用 task description 做指令
    - reviewer 只做 small 检查（py_compile）
    """
    # 直接调 dev_role，但 task 已有 description（不用 plan）
    # cc: dev_role_launch(task_id)
    # 但需要改 dev_role_launch 支持无 plan 模式
    return dev_role_launch(task["id"], skip_plan=True)
```

这个函数依赖 `dev_role_launch` 支持 `skip_plan` 参数。如果不想改现有函数，也可以用独立实现：

```python
def _run_quick_fix(task: dict) -> dict:
    ws = get_workspace()
    prompt = task.get("description", task.get("title", ""))
    # 写临时 prompt 文件
    prompt_file = ws / ".ccc" / "prompts" / f"quick-{task['id']}.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(f"请执行以下改动：\n\n{prompt}\n\n完成后 git commit，不改动 scope 外文件。")
    # 调 executor（opencode run）
    from opencode_exec import run_opencode
    result = asyncio.run(run_opencode(
        phase_id=f"quick-{task['id']}",
        prompt_text=prompt_file.read_text(),
        timeout=300,
    ))
    prompt_file.unlink(missing_ok=True)
    return result
```

### 3.4 degraded mode

位置：`ccc-engine.py`。

新增全局状态：

```python
_degraded_mode = False
_degraded_since: float | None = None
_DEGRADED_QUARANTINE_THRESHOLD = 10   # 30min
_DEGRADED_FAIL_THRESHOLD = 10         # 30min
_DEGRADED_RECOVERY_SECONDS = 600      # 10min 无异常 → 自动恢复
```

每 tick 调用 `_check_degraded()`：

```python
def _check_degraded(ws: Path) -> None:
    global _degraded_mode, _degraded_since
    
    stats = aggregate_stats(ws)
    # 过去 30 分钟
    now = time.time()
    q_count = sum(1 for ev in _recent_events(ws, "quarantine", 1800)
                  if ev.get("t", 0) > now - 1800)
    f_count = sum(1 for ev in _recent_events(ws, "product_fail", 1800)
                  if ev.get("t", 0) > now - 1800)
    
    should_degrade = q_count > _DEGRADED_QUARANTINE_THRESHOLD or f_count > _DEGRADED_FAIL_THRESHOLD
    
    if should_degrade and not _degraded_mode:
        _degraded_mode = True
        _degraded_since = now
        engine_log(f"[degraded] 30min 内异常过高 (q={q_count}, f={f_count}), 进入 degraded 模式")
        engine_log("[degraded] 停止 backlog→planned intake, 只跑维护任务")
        _notify("CCC engine 进入 degraded 模式")
    
    if _degraded_mode and not should_degrade:
        recovery_ok = (now - _degraded_since) > _DEGRADED_RECOVERY_SECONDS
        if recovery_ok:
            _degraded_mode = False
            _degraded_since = None
            engine_log("[degraded] 异常率已恢复，退出 degraded 模式")
            _notify("CCC engine 退出 degraded 模式")
```

`_recent_events` — 从 events.jsonl 读最近事件：

```python
def _recent_events(ws: Path, event_type: str, window_sec: int) -> list[dict]:
    ev_file = ws / ".ccc" / "stats" / "events.jsonl"
    if not ev_file.exists():
        return []
    now = time.time()
    events = []
    try:
        for line in ev_file.read_text().splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("event") == event_type:
                ts = ev.get("t", 0)
                if ts > now - window_sec:
                    events.append(ev)
    except (json.JSONDecodeError, OSError):
        pass
    return events
```

在 engine 主循环的 intake 判断处插入：

```python
# 在 _try_launch_planned 开头
if _degraded_mode:
    engine_log(f"[degraded] intake 暂停: backlog→planned 跳过（degraded mode）")
    return False
```

### 3.5 intake failsafe (audit 侧)

在 `_audit_run_one` 中、投 decision 之前加检查：

```python
def _intake_failsafe(ws: Path, category: str) -> bool:
    """检查是否应该暂停 intake。返回 True = 允许投，False = 熔断。"""
    store = FileBoardStore(ws)
    abnormal_tasks = store.list_tasks("abnormal")
    audit_abnormal = [t for t in abnormal_tasks 
                      if t.get("id", "").startswith(f"audit-{category}")]
    all_audit = audit_abnormal + store.list_tasks("backlog") + store.list_tasks("planned") + store.list_tasks("in_progress") + store.list_tasks("testing")
    all_audit = [t for t in all_audit if t.get("id", "").startswith(f"audit-{category}")]
    
    if not all_audit:
        return True  # 没有同类 task，允许投
    fail_rate = len(audit_abnormal) / len(all_audit)
    if fail_rate > 0.6:
        return False  # 异常率 > 60%，熔断
    return True
```

在投 decision 前调用：

```python
if findings.get("decision") and _intake_failsafe(Path(ws), "decision"):
    posted_decision = _audit_post_backlog(ws, findings["decision"], "decision")
else:
    posted_decision = 0
    if findings.get("decision"):
        _log.warning("[audit] decision intake 熔断: abnormal 占比过高")
```

### 3.6 引擎主循环改动

engine_loop 中加 `_check_degraded` 调用，与现有逻辑并行：

```
# 现有代码: 每个 workspace 扫描
for ws in workspaces:
    _check_degraded(ws)       # ← 新增
    if _degraded_mode:
        # 维护任务照跑（audit, stale check, cleanup）
        _run_audit_if_due(ws)
        _check_stale(ws)
        continue              # ← 跳过 intake
    _try_launch_planned(ws)
    ...
```

---

## 四、验收标准

改动完成后，以下场景必须通过自动化测试或手动验证：

### 4.1 自动测试

| 测试 | 方法 | 通过标准 |
|------|------|---------|
| `classify_auto` | 输入 `{"tags":["audit","review"], "title":"..."}` | 返回 `"auto"` |
| `classify_quick` | 输入 `{"tags":[], "title":"fix typo", "description":"s"}` | 返回 `"quick"` |
| `classify_full` | 输入 `{"tags":["audit","decision"], "title":"..."}` | 返回 `"full"` |
| `intake_failsafe_allow` | abnormal 中 audit-decision 占比 0% | 返回 `True` |
| `intake_failsafe_block` | abnormal 中 audit-decision 占比 80% | 返回 `False` |
| `degraded_entry` | mock events 含 11 quarantine | `_degraded_mode == True` |
| `degraded_exit` | mock events 正常 + 已过 10min | `_degraded_mode == False` |

### 4.2 手动验证

1. audit_role 产生 `review` task → 不被投 backlog，而是直接 `ruff --fix + commit`
2. audit_role 产生 `decision` task → 正常投 backlog（受 intake failsafe 保护）
3. 手动往 abnormal 塞 10 个假 task → 引擎进入 degraded → 不再从 backlog 拿新 task → 等清理后恢复
4. `_classify_task_intake` 对已有 backlog task 的重新分类不破坏现有流程

---

## 五、不会做的（边界声明）

| 不做 | 原因 |
|------|------|
| 不改 `_config.py` 配置项 | degraded 阈值用常量（可后续参数化） |
| 不改 templates/ 模板 | 不影响 prompt 层 |
| 不改 `_board_store.py` | intake 和分类是 board 上层逻辑 |
| 不改 `tests/` 已有测试 | 只加新测试，不破旧 |
| 不改 ai-loop-router | 这是 CCC 内部架构，不涉及 proxy |
| 不加新的 `max_cost` 实时拦截 | 成本汇总 post-task，不实时阻断 |

---

## 六、部署步骤

1. Cursor 按本文件实现改动
2. 跑 `pytest tests/` 确认无回归
3. 手动验证 classify/intake/degraded 行为
4. 提交 PR，通知我 review
5. review 通过后合并到 main，杀引擎（launchd 自动重启）

---

## 七、评审要点（我 review 时会重点检查）

1. `_classify_task_intake` 是否有遗漏分类（catch-all 是否 safe）
2. degraded mode 是否与现有 engine 流程正确集成（不打断已有 task 执行）
3. intake failsafe 是否正确处理空 abnormal 列（0/0 不 crash）
4. `_run_auto_fix` 的 git add/commit 与 `ccc-exec-commit.sh` 是否会冲突（phase 不存在所以不冲突）
5. 异常恢复：degraded→normal 转换条件是否太紧/太松
