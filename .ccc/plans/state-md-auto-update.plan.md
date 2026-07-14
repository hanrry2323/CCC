# Plan: state-md-auto-update — Engine 每次任务流转后自动更新 state.md 看板快照

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/_board_store.py`（FileBoardStore 核心）、`scripts/ccc-engine.py`（Engine 主循环）
- **当前结构要点**：
  1. `_board_store.py` 的 `FileBoardStore.update_index()`（L548-562）已计算全列计数（`counts = {col: len(self.list_tasks(col)) for col in COLUMNS}`），但只写 `index.json`，不写 `.ccc/state.md`
  2. `FileBoardStore.move_task()`（L494-546）执行列迁移后调 `update_index()`，数据链完整：`move_task` → `update_index` → 计数就绪但未写入 state.md
  3. `ccc-engine.py` 有 11+ 处 `store.update_index()` 调用点（L184/382/392/395/442/465/476/492/1028/1043/1626），覆盖所有 task 流转路径（含 quarantine / 恢复 / 自动重试）
  4. `.ccc/state.md` 是手动维护的接力索引文件（红线 10），Engine 重启后看板列计数不反映当前状态
  5. `FileBoardStore` 有 `self.workspace` 属性（L389）可直接定位 `.ccc/state.md`
- **待改动点**：
  - `_board_store.py:update_index()` 末尾追加写入 `.ccc/state.md` 看板快照段，幂等替换

---

## 范围

- **目标**：Engine 每次 update_index（即每次任务流转）后自动更新 `.ccc/state.md` 的看板列任务计数快照
- **只改文件**：`scripts/_board_store.py`
- **不改文件**：`scripts/ccc-engine.py`、`scripts/ccc-board.py`、`.ccc/state.md`（快照段由引擎自动维护，不手动改）
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：update_index() 追加 state.md 看板快照

### 做什么

Engine 重启后 `.ccc/state.md` 不反映当前看板状态，因为 state.md 是手动维护的。改为让 `update_index()` 在写完 `index.json` 后自动更新 `.ccc/state.md` 末尾的"看板自动快照"段。

HTML 注释标记包围确保幂等替换：标记已存在时原地覆盖，不存在时追加到文件末尾。利用 `update_index()` 中已计算的 `counts` dict，避免二次扫描。

格式：
```
<!-- AUTO-BOARD-SNAPSHOT-START -->

## 看板自动快照（Engine 自动维护）

**最后更新**: 2026-07-14T20:00:00+08:00

| 列 | 任务数 |
|---|------:|
| backlog | 0 |
| planned | 0 |
| in_progress | 0 |
| testing | 0 |
| verified | 0 |
| released | 0 |
| abnormal | 0 |

<!-- AUTO-BOARD-SNAPSHOT-END -->
```

### 怎么做

**`scripts/_board_store.py`**：

**1. 在文件底部新增模块级函数 `_update_state_md_board_snapshot()`**（before EOF，L906 `quarantine_store_content.base_name = ""` 之后）：

```python
def _update_state_md_board_snapshot(workspace: Path, counts: dict) -> None:
    """更新 .ccc/state.md 看板自动快照段（幂等替换，不抛异常）。

    Args:
        workspace: 项目根路径
        counts: {列名: 任务数} dict，来自 update_index 已计算的 COLUMNS 计数
    """
    state_md = workspace / ".ccc" / "state.md"
    if not state_md.is_file():
        return

    start_marker = "<!-- AUTO-BOARD-SNAPSHOT-START -->"
    end_marker = "<!-- AUTO-BOARD-SNAPSHOT-END -->"
    now = now_iso()
    lines = [f"\n\n{start_marker}\n"]
    lines.append("## 看板自动快照（Engine 自动维护）\n")
    lines.append(f"\n**最后更新**: {now}\n")
    lines.append("\n| 列 | 任务数 |")
    lines.append("\n|---|------:|")
    for col in COLUMNS:
        lines.append(f"\n| {col} | {counts.get(col, 0)} |")
    lines.append(f"\n\n{end_marker}\n")
    snapshot = "".join(lines)

    try:
        content = state_md.read_text(encoding="utf-8")
        if start_marker in content and end_marker in content:
            si = content.index(start_marker)
            ei = content.index(end_marker) + len(end_marker)
            new_content = content[:si] + snapshot + content[ei:]
        else:
            new_content = content.rstrip() + "\n\n---\n" + snapshot
        state_md.write_text(new_content, encoding="utf-8")
    except OSError:
        _log.warning("state.md board snapshot update failed: %s", state_md)
```

**2. 修改 `update_index()` 方法末尾**（`_atomic_write(index_file, ...)` 之后、`return counts` 之前）：

原代码（约 L557-559）：
```python
            _atomic_write(
                index_file, json.dumps(counts, indent=2, ensure_ascii=False) + "\n"
            )
            return counts
```

改为：
```python
            _atomic_write(
                index_file, json.dumps(counts, indent=2, ensure_ascii=False) + "\n"
            )
            _update_state_md_board_snapshot(self.workspace, counts)
            return counts
```

这样每次 Engine 内部或外部经 `update_index()` 的任意流转都会自动反映到 state.md。

### 验收清单

- [ ] `update_index()` 调用后 `.ccc/state.md` 末尾出现看板快照段，列计数正确
- [ ] 二次调用时快照段被原地替换（不追加副本），计数更新
- [ ] `.ccc/state.md` 不存在时 `update_index()` 不抛异常
- [ ] 非 `COLUMNS` 的目录（如 `events/`）不出现在快照中
- [ ] 某列为空 → 计数显示 0
- [ ] `state.md` 文件不可写 → 静默忽略，不影响 index.json 写入
- [ ] `scripts/_board_store.py` 编译无错误

### 验收

- [快照标记] `grep -c 'AUTO-BOARD-SNAPSHOT' .ccc/state.md` = 2（start+end marker 各 1）
- [列完整性] `python3 -c "import json; d=json.load(open('.ccc/board/index.json')); assert set(d.keys())=={'backlog','planned','in_progress','testing','verified','released','abnormal'}; print({k: d[k] for k in sorted(d)})"` — 7 列非负整数
- [一致性与幂等性] `python3 -c "from pathlib import Path; import sys; sys.path.insert(0,'scripts'); from _board_store import FileBoardStore; f=FileBoardStore(Path('.')); f.update_index(); f.update_index()"` → `grep -c 'AUTO-BOARD-SNAPSHOT' .ccc/state.md` 仍为 2
- [编译] `python3 -m compileall -q scripts/_board_store.py` → 0

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | update_index() 追加 .ccc/state.md 看板自动快照段 | `feat(engine): update_index 自动更新 state.md 看板快照 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/_board_store.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q`）
- [ ] diff 范围仅限 `scripts/_board_store.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
