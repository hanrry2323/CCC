"""engine._results_impl — acceptance budget + handle_task_result

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.results.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _acceptance_fail_file(ws: Path, tid: str) -> Path:
    return Path(ws) / ".ccc" / "pids" / f"{tid}.acceptance_fails"


def _bump_acceptance_fail(ws: Path, tid: str, why: str) -> int:
    p = _acceptance_fail_file(ws, tid)
    n = 0
    try:
        if p.is_file():
            raw = p.read_text(encoding="utf-8", errors="replace").strip()
            n = int(raw.split()[0]) if raw else 0
    except Exception:
        n = 0
    n += 1
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{n} {why[:200]}\n", encoding="utf-8")
    except Exception as exc:
        _log.warning("[acceptance_fail] marker write failed for %s: %s", tid, exc)
    return n


def _work_acceptance_is_weak_or_mixed(ws: Path, tid: str) -> bool:
    """True when work plan acceptance is weak/mixed — accelerate exhaust."""
    try:
        from _intent_probe import extract_probe_commands
        from _acceptance_strength import work_acceptance_gate_errors

        plan = Path(ws) / ".ccc" / "plans" / f"{tid}.plan.md"
        text = plan.read_text(encoding="utf-8", errors="replace") if plan.is_file() else ""
        cmds = extract_probe_commands(text) or []
        return bool(work_acceptance_gate_errors(cmds))
    except Exception:
        return False


def _handle_acceptance_fail_budget(
    ws: Path,
    tid: str,
    store,
    *,
    label: str,
    why: str,
) -> bool:
    """≥2 acceptance_cmd_failed (or weak plan) → abnormal + optimize. True=consumed."""
    n = _bump_acceptance_fail(ws, tid, why)
    weak = _work_acceptance_is_weak_or_mixed(ws, tid)
    _log_stats(
        ws,
        "acceptance_fail_retry",
        tid,
        n=n,
        max=_ACCEPTANCE_FAIL_MAX,
        why=str(why)[:200],
        weak_or_mixed=weak,
    )
    if n < _ACCEPTANCE_FAIL_MAX and not (weak and n >= 1):
        engine_log(
            f"[{label}] {tid} acceptance fail {n}/{_ACCEPTANCE_FAIL_MAX}: {why}"
        )
        return False
    engine_log(
        f"[{label}] {tid} acceptance fail budget {n}/{_ACCEPTANCE_FAIL_MAX}"
        f" weak={weak} → abnormal ({why})"
    )
    col_now = store.find_task(tid)[0]
    from_col = col_now
    # R-10: 补全 testing 列 — 旧版只处理 in_progress/planned，testing 列验收失败
    # 会导致 task 不移动但 note 已写，自愈扫不到
    if col_now in ("in_progress", "planned", "testing"):
        store.move_task(tid, col_now, "abnormal")
    try:
        store.patch_task(
            tid,
            {
                "note": (
                    ((store.find_task(tid)[1] or {}).get("note") or "")
                    + f"\n[{label}] acceptance_fail_budget n={n}: {why}"
                )[-2000:]
            },
        )
    except Exception as exc:
        _log.warning("[acceptance_fail] patch note: %s", exc)
    try:
        from _failure_ledger import record_failure, related_event_for_reason

        fail_reason = f"acceptance_fail_budget n={n}: {why}"
        record_failure(
            ws,
            task_id=tid,
            role="dev",
            reason=fail_reason,
            phase=1,
            from_col=from_col,
            to_col="abnormal",
            related_stats_event=related_event_for_reason(
                fail_reason, default="acceptance_fail"
            ),
            extra={"n": n, "weak_or_mixed": weak},
        )
    except Exception:
        engine_log(
            f"[failures] acceptance_fail record failed for {tid}: "
            f"{_traceback.format_exc()[:300]}"
        )
    store.update_index()
    try:
        _enqueue_post_exhaust_optimize(
            ws,
            tid,
            reason=f"acceptance_fail_budget n={n}: {why}",
            task=store.find_task(tid)[1] or {"id": tid},
        )
    except Exception as exc:
        _log.debug("[acceptance_fail] enqueue optimize: %s", exc)
    return True


def _short_path_fail_file(ws: Path, tid: str) -> Path:
    return Path(ws) / ".ccc" / "pids" / f"{tid}.short_path_fails"


def _bump_short_path_fail(ws: Path, tid: str, path: str, why: str) -> int:
    """Increment fail counter; return new count."""
    p = _short_path_fail_file(ws, tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    try:
        if p.is_file():
            n = int((p.read_text(encoding="utf-8").strip().splitlines() or ["0"])[0])
    except (OSError, ValueError):
        n = 0
    n += 1
    try:
        p.write_text(
            f"{n}\npath={path}\nwhy={str(why)[:300]}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _log.warning("[short_path_fail] marker write failed for %s: %s", path, exc)
    return n


def _clear_short_path_fail(ws: Path, tid: str) -> None:
    p = _short_path_fail_file(ws, tid)
    try:
        if p.is_file():
            p.unlink()
    except OSError as exc:
        _log.debug("[short_path_fail] clear unlink %s: %s", p, exc)


def _handle_short_path_failure(
    ws: Path,
    tid: str,
    store,
    *,
    label: str,
    path: str,
    why: str,
) -> bool:
    """On short-path fail: budgeted retry → abnormal. Returns True (tick consumed)."""
    n = _bump_short_path_fail(ws, tid, path, why)
    _log_stats(
        ws,
        "dev_path",
        tid,
        path=path,
        ok=False,
        why=str(why)[:200],
        short_path_fail_n=n,
    )
    _log_stats(
        ws,
        "short_path_retry",
        tid,
        path=path,
        n=n,
        max=_SHORT_PATH_FAIL_MAX,
        why=str(why)[:200],
    )
    col_now = store.find_task(tid)[0]
    if n >= _SHORT_PATH_FAIL_MAX:
        engine_log(f"[{label}] {tid} {path} fail budget {n}/{_SHORT_PATH_FAIL_MAX} → abnormal ({why})")
        from_col = col_now
        # R-TESTING: 增加 testing 列，与 _handle_acceptance_fail_budget 的 R-10 对齐
        if col_now in ("in_progress", "planned", "testing"):
            store.move_task(tid, col_now, "abnormal")
        try:
            store.patch_task(
                tid,
                {
                    "note": (
                        ((store.find_task(tid)[1] or {}).get("note") or "")
                        + f"\n[{label}] short_path_fail_budget path={path} n={n}: {why}"
                    )[-2000:]
                },
            )
        except Exception as exc:
            _log.warning("[short_path_fail] ledger write failed: %s", exc)
        # R1 pack：写入真实 why/stderr，供 L3b 优化 SOP 阅读
        try:
            from _failure_learning import write_review_fail_pack

            stderr_tail = ""
            rp = ws / ".ccc" / "reports" / f"{tid}.result.json"
            if rp.is_file():
                try:
                    stderr_tail = rp.read_text(encoding="utf-8", errors="replace")[:1500]
                except OSError:
                    stderr_tail = ""
            write_review_fail_pack(
                ws,
                tid,
                status="abnormal",
                extra=(
                    f"short_path_fail_budget path={path} n={n}\nwhy={why}\n"
                    f"result_tail:\n{stderr_tail}"
                )[:2500],
            )
        except Exception as exc:
            _log.debug("[short_path_fail] review_fail pack: %s", exc)
        # 与 quarantine 对齐：必入 failures.jsonl，清板后仍可复盘
        try:
            from _failure_ledger import record_failure, related_event_for_reason

            fail_reason = f"short_path_fail_budget path={path} n={n}: {why}"
            record_failure(
                ws,
                task_id=tid,
                role="dev",
                reason=fail_reason,
                phase=1,
                from_col=from_col,
                to_col="abnormal",
                related_stats_event=related_event_for_reason(fail_reason, default="short_path_fail"),
                extra={"path": path, "n": n},
            )
        except Exception:
            engine_log(f"[failures] short_path record_failure failed for {tid}: {_traceback.format_exc()[:300]}")
        store.update_index()
        # L3b：短路径预算耗尽 → 入队改大卡（不抬 Engine 同卡重试）
        try:
            _enqueue_post_exhaust_optimize(
                ws,
                tid,
                reason=f"short_path_fail_budget path={path} n={n}: {why}",
                task=store.find_task(tid)[1] or {"id": tid},
            )
        except Exception as exc:
            _log.debug("[short_path_fail] enqueue optimize: %s", exc)
        return True
    engine_log(f"[{label}] {tid} {path} FAILED ({n}/{_SHORT_PATH_FAIL_MAX}): {why}")
    if col_now == "in_progress":
        store.move_task(tid, "in_progress", "planned")
    store.update_index()
    return True


def _quarantine_with_notify(
    ws: Path,
    tid: str,
    reason: str,
    store: FileBoardStore | None = None,
    phase: int = 1,
    active_tasks: dict[str, dict] | None = None,
    *,
    role: str | None = None,
    exit_code: int | None = None,
    from_col: str | None = None,
) -> None:
    """移入 abnormal 并触发桌面通知。F-CON-02: 同时释放 opencode 槽位。"""
    _activate_workspace(ws)
    if store is None:
        store = _get_store(ws)
    store.quarantine(tid, reason)
    _log_stats(ws, "quarantine", tid, reason=reason)
    # v0.40: 统一失败账本（写失败必须可见，禁止静默）
    try:
        from _failure_ledger import (
            infer_role_from_reason,
            record_failure,
            related_event_for_reason,
        )

        stats_ev = related_event_for_reason(reason or "")
        if stats_ev != "quarantine":
            _log_stats(ws, stats_ev, tid, reason=reason)
        record_failure(
            ws,
            task_id=tid,
            role=role or infer_role_from_reason(reason or ""),
            reason=reason or "unknown",
            phase=phase,
            from_col=from_col,
            to_col="abnormal",
            exit_code=exit_code,
            related_stats_event=stats_ev,
        )
    except Exception:
        engine_log(f"[failures] record_failure failed for {tid}: {_traceback.format_exc()[:500]}")
    _ccc_notify("CCC", f"任务 {tid} 进入异常状态，原因：{reason}")
    store.update_index()
    # F-CON-02: 释放该 task 全部槽位
    _drop_active_task_and_slots(active_tasks, _task_key(ws, tid))
    # v0.31: 记录教训
    try:
        from _lessons import record_failure as _lesson_fail

        _lesson_fail(ws, tid, phase, reason or "unknown", "")
    except Exception as exc:
        engine_log(f"[lessons] record_failure failed for {tid}: {exc}")
    # v0.32: 自动追加到 docs/lessons.md
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(ws, tid, phase, reason or "unknown")
    except Exception as exc:
        engine_log(f"[lessons] auto_append failed for {tid}: {exc}")


def _handle_task_result(
    ws: Path,
    tid: str,
    result: dict,
    *,
    complexity: str = "medium",
    started_at: str | None = None,
) -> bool:
    """处理 dev_role_check_complete 结果。返回 True 表示从 active_tasks 移除。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    status = result.get("status", "unknown")
    err = str(result.get("error") or "")

    # 终态埋点（running / phase_done 再启另计 start）
    if status in ("success", "failed", "quarantined", "not_found"):
        try:
            _log_opencode_done(
                ws,
                tid,
                status=status,
                complexity=complexity,
                started_at=started_at,
                result=result,
            )
        except Exception as exc:
            engine_log(f"[{label}] opencode_done stats: {exc}")

    def _quarantine_keep_phases(reason: str) -> bool:
        """失败隔离：保留 phases/plan，禁止删图回 backlog 触发 product。"""
        col = _find_task_column(store, tid) or "in_progress"
        if col != "abnormal":
            try:
                store.move_task(tid, col, "abnormal")
            except Exception as exc:
                engine_log(f"[{label}] {tid} move→abnormal 失败: {exc}")
        try:
            _, task = store.find_task(tid)
            note = ((task or {}).get("note") or "") + f"\n[{label}] {reason}"
            store.patch_task(tid, {"note": note[-2000:]})
        except Exception as exc:
            engine_log("[%s] %s abnormal patch_task failed: %s", label, tid, str(exc))
        store.update_index()
        engine_log(f"[{label}] {tid} → abnormal（{reason}）")
        return True

    # commit-gate：有产出但无 task_id commit — 不得走 phase-regen/product
    if status in ("failed", "quarantined") and err.startswith("commit-gate"):
        return _quarantine_keep_phases(err)

    if status == "phase_done":
        # v0.38: 当前 phase 完成，仍有后续 phase → relaunch，留在 active_tasks
        next_phase = result.get("next_phase")
        engine_log(f"[{label}] {tid} phase {result.get('phase')} done → relaunch phase {next_phase}")
        try:
            relaunch = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} phase relaunch 异常: {exc}")
            return False
        if relaunch.get("ok") or relaunch.get("status") in ("launched", "ok", "running"):
            _note_relaunch(ws, tid, next_phase)
            return False
        # relaunch 失败：留给下一 tick / hang 恢复
        engine_log(f"[{label}] {tid} phase relaunch 未成功: {relaunch}，保留 active_tasks")
        return False

    if status == "success":
        # v0.33/v0.38: dev_role_check_complete 可能已移到 testing，避免双重 move
        col = _find_task_column(store, tid)
        if col == "in_progress":
            store.move_task(tid, "in_progress", "testing")
            _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
        elif col == "testing":
            _log_stats(ws, "move", tid, from_col="in_progress", to_col="testing")
        else:
            engine_log(f"[{label}] {tid} success 但列={col}，跳过 in_progress→testing")
        store.update_index()
        return True

    if status == "failed":
        retry = result.get("retry", 0)
        failure_summary = _check_phase_failures(tid)
        # v0.31 (P0.1): phase 图无法解析 → 仅对「无 parent 的遗留单卡」允许删 phases 回 backlog
        # epic 子卡（work+parent_id）禁止：否则会被 _process_backlog 误跑 product
        if failure_summary.get("unresolvable"):
            _, _task = store.find_task(tid)
            from _board_store import normalize_task_view as _ntv

            _task = _ntv(_task or {"id": tid}, column="in_progress")
            if _task.get("card_kind") == "work" and _task.get("parent_id"):
                detail = (
                    f"phase graph unresolvable（epic 子卡，禁止 product regen）; "
                    f"summary={failure_summary!r}; err={err[:300]}"
                )
                return _quarantine_keep_phases(detail[:500])
            # 读 regen 计数器，cap 2 次
            _regen_count = _read_regen_count(ws, tid)
            if _regen_count >= 2:
                engine_log(f"[{label}] {tid} phase 图无法解析，regen {_regen_count} 次 ≥ 2 → abnormal")
                _record_failure_pattern("phase-graph-regen")
                store.move_task(tid, "in_progress", "abnormal")
                store.update_index()
                return True
            # 删旧 phases.json（product_role 据此判断是否需要重新生成）
            _phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if _phases_file.exists():
                _phases_file.unlink()
                engine_log(f"[{label}] {tid} 删旧 phases.json，触发 regen #{_regen_count + 1}")
            # v0.37: 写 .regen 标记，防止 _process_backlog 因残留/竞态 phases.json 跳过 product
            try:
                _regen_mark = ws / ".ccc" / "pids" / f"{tid}.regen"
                _regen_mark.parent.mkdir(parents=True, exist_ok=True)
                _regen_mark.write_text(str(_regen_count + 1))
            except OSError as exc:
                _log.warning("[regen] marker write failed %s: %s", _regen_mark, exc)
            # reset 靠删除新 plan 自然归零，不调 _write_engine_iter_meta（文件已删=no-op）
            _record_regen(ws, tid)
            # 回 backlog（删 phases.json 后 product_role 会看到无 phases.json → 重生成）
            store.move_task(tid, "in_progress", "backlog")
            store.update_index()
            return True
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(f"[{label}] {tid} 所有 phase failed/skipped (skipped={failure_summary.get('skipped')})")
            store.update_index()
            return True
        cur = _current_running_phase(tid)
        err_l = str(err or result.get("error") or "").lower()
        if "acceptance-gate" in err_l or "acceptance_cmd_failed" in err_l:
            if _handle_acceptance_fail_budget(
                ws, tid, store, label=label, why=str(err or result.get("error") or "")[:300]
            ):
                return True
        engine_log(f"[{label}] {tid} 失败 (retry={retry}), relaunch phase {cur}")
        if not _relaunch_allowed(ws, tid, cur):
            return False
        _note_relaunch(ws, tid, cur)
        try:
            relaunch = dev_role_relaunch(tid)
        except Exception as exc:
            engine_log(f"[{label}] {tid} relaunch 异常: {exc}")
            return False
        if not (relaunch.get("ok") or relaunch.get("status") in ("launched", "ok", "running")):
            engine_log(f"[{label}] {tid} relaunch 未成功: {relaunch}")
        return False

    if status == "quarantined":
        failure_summary = _check_phase_failures(tid)
        # v0.31 (P0.1): phase 图无法解析 — epic 子卡禁止 product regen
        if failure_summary.get("unresolvable"):
            _, _task = store.find_task(tid)
            from _board_store import normalize_task_view as _ntv

            _task = _ntv(_task or {"id": tid}, column="in_progress")
            if _task.get("card_kind") == "work" and _task.get("parent_id"):
                detail = (
                    f"phase graph unresolvable（epic 子卡，禁止 product regen）; "
                    f"summary={failure_summary!r}; err={err[:300]}"
                )
                return _quarantine_keep_phases(detail[:500])
            # 读 regen 计数器，cap 2 次
            _regen_count = _read_regen_count(ws, tid)
            if _regen_count >= 2:
                engine_log(f"[{label}] {tid} phase 图无法解析（隔离中），regen {_regen_count} 次 ≥ 2 → abnormal")
                store.move_task(tid, "in_progress", "abnormal")
                store.update_index()
                return True
            _phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if _phases_file.exists():
                _phases_file.unlink()
                engine_log(f"[{label}] {tid} 删旧 phases.json（隔离），触发 regen #{_regen_count + 1}")
            _record_regen(ws, tid)
            store.move_task(tid, "in_progress", "backlog")
            store.update_index()
            return True
        if failure_summary.get("all_failed_or_skipped"):
            engine_log(
                f"[{label}] {tid} 所有 phase failed/skipped → abnormal "
                f"(skipped_downstream={failure_summary['skipped']})"
            )
        else:
            engine_log(f"[{label}] {tid} 重试耗尽, 已隔离, 移向下一个")
        store.update_index()
        return True

    if status == "not_found":
        engine_log(f"[{label}] {tid} 不在 in_progress (可能已被外部移走)")
    else:
        engine_log(f"[{label}] {tid} 未知状态: {status}")
    return True

