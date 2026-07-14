# Plan: reviewer-retry-timeout — reviewer 门禁超时后自动重试

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.py`（1885 行）、`scripts/ccc-board.py`（~2440 行）、`scripts/_config.py`（267 行）
- **当前结构要点**：
  1. `_review_with_llm()`（`ccc-board.py:1965-2146`）调 claude CLI 审查代码，用 `cfg.reviewer_timeout`（600s）。超时后内部已重试 3 次（间隔 10s），第 3 次仍超时则返回 `{"verdict": "fallback", "reason": "timeout(300s)"}`
  2. `_review_one_task()`（`ccc-board.py:2273-2436`）对 `verdict == "fallback"` 的分支：**写 verdict 文件 + quarantine**（L2407-2414）。quarantine 把 task 移出 testing → abnormal。**这意味着 engine 层失去 retry 机会**——task 已不在 testing
  3. `_run_reviewer_tester_gate()`（`ccc-engine.py:337-396`）有 2 次 attempt 的 retry 循环，但 `_verdict_is_valid()` 只检查 verdict 文件存在且非空——TIMEOUT 情况也返回 True——导致 `verdict_ok = True` 后立即 break，但实际上 task 已被 quarantine，后续 move_testing_to_verified 失败
  4. 超时后 task 进入 abnormal，只能等 `_retry_abnormal_dev_failures()` 冷却 15min 后自动移回，**但该函数只处理 dev 执行失败类**（`"重试" in reason`），reviewer 超时的 quarantine reason 不含"重试"，所以永不被自动恢复
  5. `_config.py:119` 已有 `reviewer_timeout` 配置，但无 reviewer 重试相关字段
- **待改动点**：
  - `_config.py`：新增 `reviewer_retry_on_timeout` 字段和环境变量覆盖
  - `ccc-board.py`：`_review_one_task()` 中 timeout 情况不 quarantine，写 "TIMEOUT" verdict
  - `ccc-engine.py`：`_run_reviewer_tester_gate()` 增加 timeout 检测 + 自动重试 + 重试超限后 quarantine

---

## 范围

- **目标**：reviewer LLM 调用超时后，engine 层自动重试（最多 N 次），重试耗尽后再 quarantine
- **只改文件**：`["scripts/_config.py", "scripts/ccc-board.py", "scripts/ccc-engine.py"]`
- **不改文件**：`["scripts/_board_store.py", "scripts/_executor.py", "scripts/ccc-board-server.py", "templates/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：reviewer 超时后 engine 层自动重试

### 做什么

当前 reviewer LLM 调用超时后，`_review_one_task()` 立即 quarantine 把 task 移出 testing 列，engine 失去重试机会。改造为三层缓冲：

1. **`_review_one_task()`** 对 timeout 时不 quarantine，只写 "TIMEOUT" 状态 verdict，task 留在 testing
2. **`_run_reviewer_tester_gate()`** 增加 timeout 检测：读到 "TIMEOUT" verdict 时清掉继续重试
3. **`_config.py`** 新增 `reviewer_retry_on_timeout` 控制最大重试次数

### 怎么做

#### 1a. `scripts/_config.py` — 新增 reviewer_retry_on_timeout 配置

在 `ccc-board.py:2050` 注释附近的 Config 区域（约 L138 `max_phases` 后面、L142 `model_tiers` 前面）新增：

```python
    # ── reviewer 超时重试（v0.31+）──
    reviewer_retry_on_timeout: int = 3  # reviewer LLM 超时最大重试次数（含首次），超过则 quarantine
```

在 `__post_init__()` 中（约 L206，在 `_env_override_int(self, "max_phases", "CCC_MAX_PHASES")` 之后）新增：

```python
    _env_override_int(self, "reviewer_retry_on_timeout", "CCC_REVIEWER_RETRY")
```

#### 1b. `scripts/ccc-board.py` — _review_one_task 对超时不 quarantine

修改 `_review_one_task()` verdict 判断分支（L2395-2436）。当前：

```python
    if verdict == "pass":
        ...
        return True
    if verdict == "fail":
        ...
        return False

    # v0.24.5 (A24-03/A24-04): medium/large fallback 一律 quarantine
    reason = ...
    _quarantine(task_id, reason=reason)
    ...
    return False
```

改为：

```python
    if verdict == "pass":
        move_task(task_id, "testing", "verified")
        _log.info("[reviewer] %s  LLM pass", task_id)
        return True
    if verdict == "fail":
        _log.error(
            "[reviewer] %s  LLM fail（%d issues），留在 testing",
            task_id,
            len(verdict_data.get("findings", [])),
        )
        return False

    # ── fallback / timeout 分类处理（v0.31+）──
    fallback_reason = verdict_data.get("reason", "").lower()
    if "timeout" in fallback_reason:
        # 超时情形：不 quarantine，写 "TIMEOUT" verdict，让 engine 层重试
        _log.warning(
            "[reviewer] %s  LLM timeout（reason=%s），留在 testing 等待 engine 重试",
            task_id,
            verdict_data.get("reason", "unknown"),
        )
        # verdict 文件写 "TIMEOUT" 状态（engine 层靠此检测）
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n"
            f"**Verdict:** TIMEOUT\n\n"
            f"**Size Class:** {size_class}\n\n"
            f"**Reason:** {verdict_data.get('reason', 'unknown')}\n"
        )
        return False

    # 非超时 fallback（API crash / JSON 解析失败等）→ 保留原有 quarantine 行为
    reason = (
        f"v0.24.5 fallback quarantine: {size_class}-class LLM 不可用，"
        f"reason={verdict_data.get('reason', 'unknown')}；"
        f"放弃静默 verified，强制人工介入"
    )
    _quarantine(task_id, reason=reason)
    ...
    # 原有 notify + return False 保持不变
```

注意：
- 原有的 verdict 写入（L2387-2393）在判断分支之前已执行——TIMEOUT 分支会再次写入覆盖为 "TIMEOUT"。也可以将 verdict 写入移到分支内部。**建议**：将原有 L2387-2393 的通用 verdict 写入移到 pass/fail/timeout/quarantine 各自分支内部，避免 TIMEOUT 分支先写一次 "FALLBACK" 再覆盖。
- 更简洁的方式：将 L2387-2393 的通用 verdict 写入保留，但 TIMEOUT 分支在 `verdict_path.write_text(...)` 时覆盖。这样改动最小。

**稳妥方案**（改动最小）：在 L2395 通用的 verdict 写入之后，分支判断时 TIMEOUT 分支用 `verdict_path.write_text(...)` 覆盖——这只需新增一个分支覆盖写入，不影响现有 pass/fail/quarantine 分支的 verdict 内容。

#### 1c. `scripts/ccc-engine.py` — _run_reviewer_tester_gate 增加 timeout 检测 + 重试

新增两个辅助函数（在 `_run_reviewer_tester_gate` 之前，约 L335）：

```python
def _verdict_is_timeout(ws: Path, tid: str) -> bool:
    """检查 verdict 文件是否标记为 TIMEOUT（非 pass/fail 超时情形）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        content = vf.read_text(encoding="utf-8")
        return "**Verdict:** TIMEOUT" in content
    except OSError:
        return False


def _clear_verdict(ws: Path, tid: str) -> None:
    """删除 verdict 文件，使 _verdict_is_valid 返回 False，触发 engine 重试。"""
    vf = _verdict_file(ws, tid)
    try:
        vf.unlink(missing_ok=True)
    except OSError:
        pass
```

修改 `_run_reviewer_tester_gate()`（L337-396）。完整替换为：

```python
def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。

    v0.31+: 超时情形 engine 层自动重试（不 quarantine），
    reviewer_retry_on_timeout 次超时后再 quarantine。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    timeout_retries = cfg.reviewer_retry_on_timeout
    timeout_count = 0
    verdict_ok = False

    for attempt in range(max(2, timeout_retries)):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            if _verdict_is_timeout(ws, tid):
                timeout_count += 1
                if timeout_count >= timeout_retries:
                    engine_log(
                        f"[{label}] {tid} reviewer 超时重试 {timeout_count}/{timeout_retries} 耗尽 → abnormal"
                    )
                    cur_phase = _current_running_phase(tid)
                    _quarantine_with_notify(
                        ws, tid, "reviewer 超时重试耗尽", store, phase=cur_phase
                    )
                    return False
                _clear_verdict(ws, tid)
                _ensure_task_in_testing(store, tid)
                engine_log(
                    f"[{label}] {tid} reviewer 超时，等待重试 (attempt {attempt + 1}/{timeout_retries})"
                )
                time.sleep(30)
                continue
            verdict_ok = True
            break

        engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/{max(2, timeout_retries)})"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == max(2, timeout_retries) - 1 and not verdict_ok:
            engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            cur_phase = _current_running_phase(tid)
            _quarantine_with_notify(
                ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase
            )
            store.update_index()
            return False

    _ensure_task_in_testing(store, tid)

    try:
        tester_role()
    except Exception as exc:
        engine_log(f"[{label}] {tid} tester_role 异常: {exc}")

    _ensure_task_in_testing(store, tid)

    tests_dir = ws / "tests"
    if tests_dir.is_dir():
        exit_code, output = _run_pytest(ws)
        _log_stats(ws, "pytest", tid, exit_code=exit_code, output_len=len(output))
        if exit_code != 0:
            _record_pytest_failure(ws, tid, exit_code, output)
            engine_log(
                f"[{label}] {tid} pytest 失败 (exit={exit_code})，留在 testing 等待人工确认"
            )
            _ccc_notify(
                "CCC", f"任务 {tid} pytest 未通过 (exit={exit_code})，已留在 testing"
            )
            store.update_index()
            return False
    else:
        engine_log(f"[{label}] {tid} 无 tests/ 目录，跳过 engine pytest")

    if verdict_ok:
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            _log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        return _find_task_column(store, tid) == "verified"

    store.update_index()
    return False
```

### 验收清单

- [ ] Config 新增 `reviewer_retry_on_timeout`，默认值 3
- [ ] 环境变量 `CCC_REVIEWER_RETRY=5` 可覆盖
- [ ] `_review_one_task()` 超时时不 quarantine，写 "TIMEOUT" 状态 verdict
- [ ] `_review_one_task()` 非超时 fallback（API crash/JSON 解析失败）保留原 quarantine 行为
- [ ] `_run_reviewer_tester_gate()` 检测 "TIMEOUT" verdict 后清除并重试
- [ ] 重试超限后 quarantine，reason 含"reviewer 超时重试耗尽"
- [ ] reviewer 正常 pass/fail 路径不受影响
- [ ] `python3 -m compileall -q scripts/_config.py scripts/ccc-board.py scripts/ccc-engine.py` 零错误
- [ ] 现有测试全部通过

### 验收

- [编译检查] `python3 -m compileall -q scripts/_config.py scripts/ccc-board.py scripts/ccc-engine.py` → 0 errors
- [config 默认值] `python3 -c "from _config import Config; print(Config().reviewer_retry_on_timeout)"` → 3
- [env 覆盖] `CCC_REVIEWER_RETRY=5 python3 -c "from _config import Config; print(Config().reviewer_retry_on_timeout)"` → 5
- [timeout 不 quarantine] 走读 `_review_one_task()` 中 "timeout" 分支：确认 `_quarantine()` 不被调用，verdict 写 "TIMEOUT"
- [engine 重试逻辑] 走读 `_run_reviewer_tester_gate()`：确认 TIMEOUT 时 `_clear_verdict` + continue 循环，耗尽后 `_quarantine_with_notify`
- [regression] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | reviewer 超时 engine 层自动重试：config + timeout verdict（不 quarantine）+ engine 重试循环 | `feat(engine): reviewer 超时自动重试（最多 3 次）后再 quarantine (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/_config.py scripts/ccc-board.py scripts/ccc-engine.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限白名单文件（`scripts/_config.py`、`scripts/ccc-board.py`、`scripts/ccc-engine.py`）
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] reviewer 正常 pass/fail 流程无影响（非 timeout 分支不做任何变更）

---

## 后续步骤

可考虑后续将 `_retry_abnormal_dev_failures()` 也支持 reviewer 超时类 quarantine 恢复（当前只匹配 "重试" 关键字），但本次不做：超时重试耗尽后应人工介入，自动恢复可能掩盖基础设施问题。