# Plan: state-md-auto-update — 每次任务流转后自动更新 state.md

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/_board_store.py`（~740 行）、`scripts/_config.py`（~270 行）
- **当前结构要点**：
  1. `FileBoardStore`（`_board_store.py:386`）管理看板底层操作——`move_task()`（L494）、`quarantine()`（L564）、`create_task()`（L408）。所有状态变更入都经过此层
  2. `ccc-engine.py` 有 8+ 处 `store.move_task()` 调用，`ccc-board.py` 有 7+ 处 `move_task()` 调用，`ccc-board-server.py` 也有 1 处——散布在各处
  3. `store.update_index()`（L548）已经做了类似的事（更新 `index.json`），但 `state.md` 无人维护——当前 state.md 的"当前状态"节是手写的，Engine 重启后过时
  4. `_board_store.py` 已拥有 `_atomic_write()`（L349）、`now_iso()`、`COLUMNS` 等全部基础工具
  5. `_utils.py` 提供 `now_iso()` 和 `sanitize_id()`——`_board_store.py` 已导入
  6. `_config.py`：当前没有 state.md 相关配置字段
- **待改动点**：
  - `scripts/_board_store.py`：新增 `_sync_state_md()` 方法 + `move_task()`/`quarantine()` 成功后调用

---

## 范围

- **目标**：每次看板 move_task / quarantine 操作后自动更新 `.ccc/state.md` 中的看板状态节（列名 + 任务数），确保 Engine 重启后 state.md 反映真实看板状态
- **只改文件**：`["scripts/_board_store.py"]`
- **不改文件**：`["scripts/ccc-engine.py", "scripts/ccc-board.py", "scripts/ccc-board-server.py", "scripts/_config.py"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：FileBoardStore 中 hook _sync_state_md 到 move_task / quarantine

### 做什么

当前看板状态完全靠手工维护在 `state.md` 中，Engine 启动后不知道哪些 task 在哪些列。改造为每次 `move_task()` 和 `quarantine()` 成功后自动写/更新 `state.md` 的"看板状态"节。

**核心设计**：在 `FileBoardStore` 内部 hook（而非在外层 15+ 个调用点逐个加），保证：
- Engine、board-server、board.py、手工脚本——所有通路都自动同步
- 零侵入调用方：无需改 engine.py/board.py
- `_sync_state_md()` 在锁释放后执行，不延长看板写锁持有时间

**state.md 格式**：用 `<!-- board-status -->` 和 `<!-- /board-status -->` HTML 注释作锚点标记，`_sync_state_md()` 找到标记后替换其间的全部内容。如果没有标记则追加到文件末尾。

### 怎么做

**1a. `scripts/_board_store.py:FileBoardStore`** — 新增 `_sync_state_md()` 方法（建议插入在 `_record_event()` 后、`get_timeline()` 前，约 L736）：

```python
def _sync_state_md(self) -> None:
    """更新 .ccc/state.md 看板状态节（move_task/quarantine 成功后自动触发）

    使用 <!-- board-status --> / <!-- /board-status --> 配对标记
    做确定性替换；无标记时追加末尾。
    """
    state_md = self.workspace / ".ccc" / "state.md"
    counts = {col: len(self.list_tasks(col)) for col in COLUMNS}
    now = now_iso()

    lines = [
        "<!-- board-status -->",
        "## 看板状态",
        "",
        f"> 自动更新 — 最后刷新时间：{now}",
        "",
        "| 列 | 任务数 |",
        "|---|------:|",
    ]
    for col in COLUMNS:
        lines.append(f"| {col} | {counts[col]} |")
    lines.append("")
    lines.append("<!-- /board-status -->")
    block = "\n".join(lines)

    if state_md.exists():
        content = state_md.read_text(encoding="utf-8")
        if "<!-- board-status -->" in content and "<!-- /board-status -->" in content:
            pre = content.split("<!-- board-status -->")[0]
            post = content.split("<!-- /board-status -->", 1)[1]
            new_content = pre + block + "\n" + post
        else:
            # 无标记：追加到末尾
            new_content = content.rstrip() + "\n\n" + block + "\n"
    else:
        new_content = block + "\n"

    try:
        _atomic_write(state_md, new_content)
    except OSError as exc:
        _log.warning("_sync_state_md: 写入 %s 失败: %s", state_md, exc)
```

**1b. `scripts/_board_store.py:FileBoardStore.move_task()`** — 成功路径后调用 `_sync_state_md()`。

在 L542-546 附近，将 `finally` 中的 `self._unlock(lock)` + 后续清理改为：

```python
success = False
lock = self._lock()
if lock is None:
    _log.error("move_task: lock unavailable; aborting")
    return False
try:
    # ... 现有 logic（L509-542），将 return True → success = True
    ...
    success = True
finally:
    self._unlock(lock)
if success:
    self._sync_state_md()  # 锁释放后执行，不延长锁持有时间
return success
```

注意：现有 `move_task()` 在 lock = None 时直接 return False（在 try 前），这部分不动。只重构 try 块内的 return 为 success 赋值。

**1c. `scripts/_board_store.py:FileBoardStore.quarantine()`** — 同样模式：

```python
success = False
lock = self._lock()
if lock is None:
    _log.error("quarantine: lock unavailable; aborting %s", task_id)
    return
try:
    # ... 现有 logic（L578-615），末尾加 success = True
    success = True
finally:
    self._unlock(lock)
if success:
    self._sync_state_md()
```

注意：quarantine 现有代码 L576 处的 `if lock is None: ... return` 在 try 前，不动；try 块内部原本无 return（quarantine 返回 None），所以只需在 try 块末尾加 `success = True`。

### 验收清单

- [ ] `_sync_state_md()` 在 move_task/quarantine 成功后自动写入 state.md
- [ ] state.md 标记 `<!-- board-status -->` 存在时，替换其间的全部内容
- [ ] state.md 无标记时，追加到末尾
- [ ] state.md 不存在时，创建新文件
- [ ] 写入内容符合预期格式（列名 + 任务数表格 + 更新时间）
- [ ] 看板写锁在 `_sync_state_md()` 调用前已释放（不延长锁持有）
- [ ] `_sync_state_md()` 写入失败（如权限不足）时仅 warn，不抛异常影响主流程
- [ ] `python3 -m compileall -q scripts/_board_store.py` 零错误
- [ ] 现有测试全部通过
- [ ] Engine 重启后，state.md 看板状态反映真实看板列

### 验收

- [编译检查] `python3 -m compileall -q scripts/_board_store.py` → 0 errors
- [集成检查] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过
- [引入 import ok] `python3 -c "import sys; sys.path.insert(0,'scripts/'); from _board_store import FileBoardStore; print('import ok')"` → import ok
- [state.md 格式] 任意 move 后 state.md 尾部出现 `## 看板状态` 节，包含 7 列计数 + `<!-- board-status -->` 标记
- [替换生效] 再次 move 后 `<!-- board-status -->` → `<!-- /board-status -->` 之间内容被新数据替换
- [锁时序验证] 走读 `move_task()` 中 `_sync_state_md()` 在 `self._unlock(lock)` 之后调用
- [错误容忍] `chmod 444 .ccc/state.md` 后触发 move → 日志 warn 而非 crash

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | FileBoardStore 新增 _sync_state_md() + move_task/quarantine 成功后自动写入 state.md | `feat(board): 每次 move_task/quarantine 后自动更新 state.md 看板状态 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/_board_store.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/_board_store.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

后续可考虑：
- 若 state.md 写入频率过高（高频 move 场景），可在 Config 中加 `state_md_sync_interval` 做节流
- 类似地，`create_task()` 也可 hook _sync_state_md()，但创建 backlog task 不变更列状态，当前不必要
- 将来 `update_index()` 和 `_sync_state_md()` 可统一为 `_sync_board_state()` 一次性完成 index.json + state.md 两份状态文件