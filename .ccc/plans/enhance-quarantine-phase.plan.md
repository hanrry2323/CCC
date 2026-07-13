# Plan: enhance-quarantine-phase — quarantine lessons 追加上报 phase 编号

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.py`（1023 行，多 workspace 并行执行引擎）
- **当前结构要点**：
  - `_quarantine_with_notify()`（行 124-141）负责将 task 移入 abnormal + 桌面通知 + 记录教训
  - 内部调用 `record_failure(ws, tid, 1, reason or "unknown", "")`（行 139）——第三参数 `1` 是硬编码 phase
  - `_lessons.py` 中 `record_failure()` 签名 `(ws_path, task_id, phase, error, analysis)` 已接受 `phase: str | int`
  - `_current_running_phase(task_id)`（ccc-board.py:508）可返回当前运行 phase 编号，各 quarantine 调用处存在不同 phase 上下文
  - `_quarantine_with_notify` 共 4 个调用点：`_run_reviewer_tester_gate`（行 305）、`_process_backlog`（行 514、541）、`_check_stale`（行 956）
- **待改动点**：`scripts/ccc-engine.py` 行 124-141（函数签名 + 内部 `record_failure` 调用）+ 4 个调用点

---

## 范围

- **目标**：`_quarantine_with_notify()` 记录教训时不再硬编码 phase=1，改为调用处传入实际 phase
- **只改文件**：`scripts/ccc-engine.py`
- **不改文件**：`.ccc/` 下任何文件、其他脚本、测试文件、`_lessons.py`、`_config.py`
- **执行方式**：`manual`
- **Phase 数**：1

---

## Phase 1：quarantine_with_notify 签名加 phase 参数 + 调用处

### 做什么

`_quarantine_with_notify()` 行 139 调用 `record_failure(ws, tid, 1, ...)` 中 `1` 是硬编码 phase。需要：
1. 函数签名增加 `phase: int = 1` 默认参数（向后兼容，现有调用若不传 phase 不崩）
2. 内部 `record_failure` 调用改为使用该参数
3. 每个调用点传入实际的 phase 值

各调用点解析：
- `_run_reviewer_tester_gate` 行 305：reviewer 门禁超时，是 dev 执行后阶段，调 `_current_running_phase(tid)` 获取当前 phase
- `_process_backlog` 行 514/541：product role 拆分失败，尚未进入任何 phase，传入 `phase=0`
- `_check_stale` 行 956：in_progress 滞留检测，调 `_current_running_phase(task["id"])` 获取卡住的 phase

### 怎么做

1. `scripts/ccc-engine.py:124` — 函数签名增加 `phase: int = 1`：
   ```python
   def _quarantine_with_notify(
       ws: Path, tid: str, reason: str, store: FileBoardStore | None = None,
       phase: int = 1,
   ) -> None:
   ```

2. `scripts/ccc-engine.py:139` — 将硬编码 `1` 改为变量：
   ```python
   record_failure(ws, tid, phase, reason or "unknown", "")
   ```

3. `scripts/ccc-engine.py:305` — reviewer 门禁失败处，加 `_current_running_phase(tid)` 调用：
   ```python
   cur_phase = _current_running_phase(tid)
   _quarantine_with_notify(ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase)
   ```

4. `scripts/ccc-engine.py:514,541` — product_role 失败，传入 `phase=0`：
   ```python
   _quarantine_with_notify(ws, tid, f"product_role 连续失败 {fail_count} 次", store, phase=0)
   ```
   以及另一处相同调用。

5. `scripts/ccc-engine.py:956` — stale 检测处，加 `_current_running_phase(task["id"])`：
   ```python
   tid = task["id"]
   cur_phase = _current_running_phase(tid)
   ...
   _quarantine_with_notify(ws, tid, reason, store, phase=cur_phase)
   ```

### 验收清单

- [ ] `_quarantine_with_notify` 签名含 `phase: int = 1`
- [ ] 内部 `record_failure` 使用传入的 phase 而非硬编码
- [ ] 4 个调用点均已传入实际 phase
- [ ] `_current_running_phase` 在 reviewer 门禁和 stale 处已调用
- [ ] product_role 失败处传入 `phase=0`
- [ ] 默认 `phase=1` 确保任何遗漏调用不崩

### 验收

- `python3 -m py_compile scripts/ccc-engine.py` 语法通过
- `grep -c 'record_failure.*, 1,' scripts/ccc-engine.py` 返回 0（无残留硬编码）
- `grep -c 'record_failure.*, phase,' scripts/ccc-engine.py` 至少 1（内部调用用 phase 变量）
- `grep -c 'phase=0' scripts/ccc-engine.py` 至少 2（两处 product_role 失败）
- `grep -c 'phase=cur_phase' scripts/ccc-engine.py` 至少 2（reviewer + stale 两处）
- `python3 -c "exec(open('scripts/ccc-engine.py').read()); import inspect; s=inspect.signature(_quarantine_with_notify); assert 'phase' in s.parameters; assert s.parameters['phase'].default == 1"` 通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 加 phase 参数 + 4 调用点 | `fix(engine): quarantine_with_notify 传实际 phase 而非硬编码 1 (phase 1/1)` |

---

## 全局验收清单

- [ ] `python3 -m py_compile scripts/ccc-engine.py` 通过
- [ ] diff 仅限 `scripts/ccc-engine.py`
- [ ] 1 个 phase 对应 1 个 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] 所有验收意图全部达成

---

## 后续步骤

无。此改动极轻，改为后 `_quarantine_with_notify` 记录的教训包含正确 phase 编号，便于 product 角色定位问题。