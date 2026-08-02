"""engine._recover_impl — recover_tasks + startup scan

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.recover.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _recover_tasks(ws: Path, active_tasks: dict[str, dict]) -> None:
    """Engine 启动后扫描 board，恢复 in_progress/testing 列的 task 上下文。

    验收点：
      - in_progress 列 task: 调 dev_role_check_complete 恢复 phase 执行状态
      - running → 登记 active_tasks（满槽则只告警 + pending，不超 MAX_CONCURRENT）
      - failed/not running → 不立即 relaunch，写入 pending_relaunch
      - testing 列 task: 调 `_run_reviewer_tester_gate`（small 不跳过审测）
      - 每恢复一个 task 间隔 5s，避免并发重启风暴
      - board 为空时静默跳过，无日志噪声
    """
    _activate_workspace(ws)
    try:
        ccc_board.clear_stale_review_locks()
    except Exception as exc:
        engine_log(f"[recover] [{_ws_label(ws)}] clear_stale_review_locks: {exc}")
    store = _get_store(ws)
    label = _ws_label(ws)

    in_prog = store.list_tasks("in_progress")
    testing = store.list_tasks("testing")

    if not in_prog and not testing:
        engine_log(f"[{label}] board 为空，跳过 task 恢复")
        return

    if in_prog:
        engine_log(
            f"[recover] [{label}] 恢复 {len(in_prog)} 个 in_progress task "
            f"（间隔 5s 避免并发；dev_slots={len(active_tasks)}/{MAX_CONCURRENT}）"
        )

    for idx, task in enumerate(in_prog):
        tid = task["id"]
        complexity = task.get("complexity", "medium")
        cur_phase = _current_running_phase(tid)
        engine_log(f"[recover] [{label}] Recovered task {tid} at phase {cur_phase} （in_progress → dev 检查）")
        try:
            result = dev_role_check_complete(tid)
            status = result.get("status", "unknown")
            if status == "running":
                if _register_active(active_tasks, ws, tid, complexity=complexity):
                    engine_log(f"[recover] [{label}] {tid} PID 仍存活，继续监控")
                else:
                    engine_log(f"[recover] [{label}] {tid} PID 存活但槽已满，排入 pending_relaunch")
                    _enqueue_pending_relaunch(
                        ws,
                        tid,
                        complexity=complexity,
                        reason="recover_running_wait_slot",
                    )
            elif status == "success":
                _handle_task_result(ws, tid, result, complexity=complexity)
                _release_dev_slot(None, ws, tid)
            elif status in ("failed", "quarantined", "not_found"):
                # P1: 有 .done 优先收口，禁止无脑 pending_relaunch 占槽
                done_marker = ws / ".ccc" / "pids" / f"{tid}.done"
                if done_marker.is_file() or status in ("quarantined", "not_found"):
                    _handle_task_result(ws, tid, result, complexity=complexity)
                    _release_dev_slot(None, ws, tid)
                elif status == "failed":
                    failure_summary = _check_phase_failures(tid)
                    if failure_summary.get("unresolvable") or failure_summary.get("all_failed_or_skipped"):
                        _handle_task_result(ws, tid, result, complexity=complexity)
                        _release_dev_slot(None, ws, tid)
                    else:
                        _enqueue_pending_relaunch(ws, tid, complexity=complexity, reason="recover")
            elif status == "phase_done":
                _enqueue_pending_relaunch(ws, tid, complexity=complexity, reason="phase_done")
            else:
                # unknown — 走原结果处理（无强制 relaunch）
                _handle_task_result(ws, tid, result, complexity=complexity)
                _release_dev_slot(None, ws, tid)
        except Exception as exc:
            engine_log(f"[recover] [{label}] {tid} in_progress 恢复异常: {exc}")

        if idx < len(in_prog) - 1:
            time.sleep(5)

    if testing:
        engine_log(f"[recover] [{label}] 恢复 {len(testing)} 个 testing task （限预算门禁，不堵后续 launch）")
        try:
            _run_testing_tasks_gate(ws)
        except Exception as exc:
            engine_log(f"[recover] [{label}] testing 恢复异常: {exc}")


def _try_fill_pending_relaunch(active_tasks: dict[str, dict]) -> bool:
    """消费 pending_relaunch 填空槽。返回是否启动/登记了至少一个。"""
    if not _pending_relaunch or not _can_accept_dev(active_tasks):
        return False
    did = False
    for key, item in list(_pending_relaunch.items()):
        if not _can_accept_dev(active_tasks):
            break
        if key in active_tasks:
            _pending_relaunch.pop(key, None)
            continue
        ws = item["workspace"]
        tid = item["task_id"]
        complexity = item.get("complexity", "medium")
        reason = item.get("reason", "recover")
        label = _ws_label(ws)
        try:
            _activate_workspace(ws)
            phase = _current_running_phase(tid)
            if reason == "recover_running_wait_slot":
                result = dev_role_check_complete(tid)
                if result.get("status") == "running":
                    if _register_active(active_tasks, ws, tid, complexity=complexity):
                        _pending_relaunch.pop(key, None)
                        did = True
                        engine_log(f"[slot] [{label}] {tid} 补槽登记（仍在跑）")
                    continue
                # 已不在跑 → 走 relaunch
            if not _relaunch_allowed(ws, tid, phase):
                continue
            _note_relaunch(ws, tid, phase)
            relaunch = dev_role_relaunch(tid)
            ok = relaunch.get("ok") or relaunch.get("status") in (
                "launched",
                "ok",
                "running",
            )
            if not ok:
                engine_log(f"[slot] [{label}] pending_relaunch {tid} 失败: {relaunch}")
                continue
            if _register_active(active_tasks, ws, tid, complexity=complexity):
                _pending_relaunch.pop(key, None)
                did = True
                engine_log(f"[slot] [{label}] pending_relaunch {tid} 已启动 ({reason})")
        except Exception as exc:
            engine_log(f"[slot] [{label}] pending_relaunch {tid} 异常: {exc}")
    return did


def _startup_scan_workspace(ws: Path, active_tasks: dict[str, dict]) -> None:
    """兼容旧调用：委托 _recover_tasks（含槽位上限）。"""
    _recover_tasks(ws, active_tasks)

