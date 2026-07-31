"""engine._backlog_impl — epic refresh + process_backlog

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.backlog.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _refresh_epic_statuses(ws: Path) -> None:
    """扫 backlog epic：按子卡列推导五态（pending/planned/running/done/failed）。"""
    try:
        from _product_fanout import refresh_epic_lifecycle
    except ImportError:
        return
    store = _get_store(ws)
    for task in store.list_tasks("backlog"):
        if task.get("card_kind") != "epic":
            continue
        try:
            refresh_epic_lifecycle(store, task["id"])
        except Exception as exc:
            engine_log(f"[fanout] refresh {task.get('id')}: {exc}")


def _process_backlog(ws: Path) -> bool:
    """消费 backlog：只对 pending epic 调 Claude 扇出；epic 永不 move 出待办。

    work 误落 backlog：
    - plan+phases 齐全 → planned
    - 有 parent_id（epic 子卡）且缺 phases → abnormal（禁止 product 重拆）
    - 无 parent 的遗留单卡 → 可走 product 补 phases（兼容）
    """
    global _degraded_mode, _intake_bypass_degraded, _intake_bypass_ticks_left
    if _degraded_mode and not (_intake_bypass_degraded or _intake_bypass_ticks_left > 0):
        return False

    with workspace_scope(ws):
        return _process_backlog_unlocked(ws)


def _process_backlog_unlocked(ws: Path) -> bool:
    store = _get_store(ws)
    label = _ws_label(ws)
    from _board_store import normalize_task_view

    _refresh_epic_statuses(ws)

    backlog = store.list_tasks("backlog")
    if not backlog:
        return False

    did_something = False
    for task in backlog:
        tid = task["id"]
        try:
            from _board_garbage import is_garbage_board_card

            if is_garbage_board_card(tid, task):
                engine_log(f"[product] [{label}] skip garbage epic/work {tid}")
                continue
        except ImportError:
            pass  # intentional — optional _board_garbage
        key = _task_key(ws, tid)
        _task_data = normalize_task_view(task, column="backlog")
        kind = _task_data.get("card_kind") or "epic"
        split = _task_data.get("split_status") or "pending"

        # Epic：仅 pending 走 product；其余五态不自动重拆
        if kind == "epic":
            if split in ("planned", "running", "done", "failed"):
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                continue
            # pending（含存量 active 已被 refresh 精算）→ 下方走 product fanout
        else:
            # work 兼容：plan+phases 齐全 → planned
            phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
            parent_id = _task_data.get("parent_id")
            if phases_file.exists() and plan_file.exists():
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                # phases 全 done → 直接 testing，禁止丢回 planned 空转
                try:
                    from _role_tool import _read_phases_json

                    _ph = _read_phases_json(ws, tid) or []
                    _st = {str(p.get("status") or "?") for p in _ph}
                except Exception:
                    _st = set()
                if _st and not (_st - {"done"}):
                    if store.move_task(tid, "backlog", "testing"):
                        engine_log(
                            f"[product] [{label}] work {tid} phases done → testing（跳过 planned）"
                        )
                        _log_stats(ws, "move", tid, from_col="backlog", to_col="testing")
                        did_something = True
                    continue
                if store.move_task(tid, "backlog", "planned"):
                    engine_log(f"[product] [{label}] work {tid} → planned（兼容单卡）")
                    _log_stats(ws, "move", tid, from_col="backlog", to_col="planned")
                    did_something = True
                continue
            # epic 子卡禁止走 Claude product 扇出（扇出只服务 pending epic）
            if parent_id:
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                engine_log(
                    f"[product] [{label}] work {tid} parent={parent_id} 缺 phases → abnormal（禁止 product 重拆）"
                )
                store.quarantine(
                    tid,
                    "epic child missing phases; refuse product regen",
                )
                store.update_index()
                did_something = True
                continue
            # 无 parent 的遗留 work：下方可走 product 补 phases

        # v0.35: auto/quick 仅对非 epic（或显式）—— epic 不做 auto
        if kind != "epic":
            try:
                _pipeline_class = ccc_board._classify_task_intake(_task_data)
            except Exception:
                _pipeline_class = "full"
            if _pipeline_class in ("auto", "quick"):
                if key in _product_inflight:
                    _finalize_or_gc_product_key(ws, tid, key)
                if _pipeline_class == "auto":
                    result = ccc_board._run_auto_fix(_task_data)
                    if result.get("ok"):
                        store.move_task(tid, "backlog", "released")
                    else:
                        store.move_task(tid, "backlog", "abnormal")
                else:
                    result = ccc_board._run_quick_fix(_task_data)
                    if result.get("ok"):
                        store.move_task(tid, "backlog", "testing")
                    else:
                        store.move_task(tid, "backlog", "abnormal")
                store.update_index()
                did_something = True
                continue

        # 2. 上游健康检测(2026-07-25 fail-open 共识:relay 不可达不 skip,任务走直连继续)
        if not _is_upstream_healthy():
            engine_log(
                f"[product] [{label}] {tid} relay 不可达 → 切 fail-open 直连继续(不 skip,不计数)"
            )
            # 不 continue,让 _claude_env 拿不到 relay_url 时走 fail-open 直连

        # 3. 失败计数器（step decay；禁止 15min 清零 — 否则 smoke 死循环）
        _COUNTER_DECAY_SEC = 900  # 15 分钟最多减 1，不归零
        fail_counter_dir = ws / ".ccc" / ".product-fail-counter"
        fail_counter_path = fail_counter_dir / f"{tid}.json"
        from _product_fail_counter import (
            clear_product_fail_count,
            load_product_fail_count,
            write_product_fail_count,
        )

        fail_count, _decay_msg = load_product_fail_count(
            fail_counter_path,
            decay_sec=_COUNTER_DECAY_SEC,
            max_retries=_MAX_PRODUCT_RETRIES,
        )
        if _decay_msg:
            engine_log(f"[product] [{label}] {tid} {_decay_msg}")

        def _mark_product_exhausted(reason: str) -> None:
            """epic 留 backlog 标 failed；work 才可 quarantine。"""
            if kind == "epic":
                store.patch_task(
                    tid,
                    {
                        "split_status": "failed",
                        "note": (_task_data.get("note") or "") + f"\n[product] {reason}",
                    },
                )
                # 冻结算失败次数，防止衰减后重新 launch
                write_product_fail_count(fail_counter_path, max(fail_count, _MAX_PRODUCT_RETRIES))
                engine_log(f"[product] [{label}] epic {tid} → failed（{reason}），仍留待办")
            else:
                _quarantine_with_notify(ws, tid, reason, store, phase=0, role="product", from_col="backlog")
                clear_product_fail_count(fail_counter_path)
            _ccc_notify("CCC", f"product 拆分 {tid}: {reason[:120]}")

        if fail_count >= _MAX_PRODUCT_RETRIES:
            engine_log(f"[product] [{label}] {tid} 已失败 {fail_count} 次 >= {_MAX_PRODUCT_RETRIES}")
            _mark_product_exhausted(f"product_role 连续失败 {fail_count} 次")
            did_something = True
            continue

        # 3. 检查 inflight 异步 product
        if key in _product_inflight:
            engine_log(f"[product] [{label}] {tid} 异步 product 检查...")
            result = ccc_board.check_product_async(tid)
            if result["status"] == "success":
                _product_inflight.pop(key, None)
                clear_product_fail_count(fail_counter_path)
                _log_stats(ws, "product_done", tid, fail_count=fail_count)
                kids = result.get("child_ids") or []
                if kids:
                    engine_log(f"[product] [{label}] {tid} ✓ fanout {len(kids)} work → planned")
                else:
                    engine_log(f"[product] [{label}] {tid} ✓ 异步 product 完成")
                did_something = True
                continue
            elif result["status"] == "failed":
                _product_inflight.pop(key, None)
                err = result.get("error", "")[:200]
                if result.get("fatal") or str(err).startswith("auth:"):
                    fail_count = _MAX_PRODUCT_RETRIES
                else:
                    fail_count += 1
                write_product_fail_count(fail_counter_path, fail_count)
                _log_stats(
                    ws,
                    "product_fail",
                    tid,
                    fail_count=fail_count,
                    error=err,
                )
                try:
                    from _failure_ledger import record_failure

                    record_failure(
                        ws,
                        task_id=tid,
                        role="product",
                        reason=err or "product_fail",
                        phase=0,
                        from_col="backlog",
                        to_col=None,
                        related_stats_event="product_fail",
                    )
                except Exception:
                    engine_log(f"[failures] product_fail ledger: {_traceback.format_exc()[:300]}")
                engine_log(
                    f"[product] [{label}] product_role({tid}) 异步失败 #{fail_count}: {result.get('error', '?')}"
                )
                if fail_count >= _MAX_PRODUCT_RETRIES:
                    _q_reason = (
                        f"product_role 致命失败: {err}"
                        if result.get("fatal") or str(err).startswith("auth:")
                        else f"product_role 连续失败 {fail_count} 次"
                    )
                    _mark_product_exhausted(_q_reason)
                did_something = True
                continue
            engine_log(f"[product] [{label}] {tid} 异步 product 执行中...")
            continue

        # 4. Hub 定稿已挂 plan+phases → 跳过 Claude，本地扇出 work
        if kind == "epic":
            plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
            phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
            if plan_file.is_file() and phases_file.is_file() and not (_task_data.get("child_ids") or []):
                try:
                    from _product_fanout import fanout_from_seeded_epic

                    seed_r = fanout_from_seeded_epic(store, _task_data, max_phases=cfg.max_phases)
                except Exception as exc:
                    seed_r = {"ok": False, "error": str(exc)}
                if seed_r.get("ok"):
                    engine_log(
                        f"[product] [{label}] epic {tid} seeded fanout → {seed_r.get('child_ids')}（跳过 Claude）"
                    )
                    clear_product_fail_count(fail_counter_path)
                    _log_stats(ws, "product_done", tid, fail_count=0, seeded=True)
                    did_something = True
                    continue
                engine_log(
                    f"[product] [{label}] epic {tid} seeded fanout 失败: "
                    f"{seed_r.get('error', '?')} — 回退 Claude product"
                )

        # 5. 启动异步 product（epic 扇出 / work 单卡）
        if not _can_launch_product(ws):
            engine_log(
                f"[product] [{label}] cap 已满 "
                f"(global={len(_product_inflight)}/{MAX_PRODUCT_INFLIGHT}, "
                f"ws={_product_inflight_for_ws(ws)}/{MAX_PRODUCT_PER_WS})，"
                f"跳过 launch {tid}"
            )
            continue

        engine_log(f"[product] [{label}] backlog 异步拆分: {tid} kind={kind} (此前失败 {fail_count} 次)")
        _log_stats(ws, "product_start", tid, fail_count=fail_count)
        launch_r = ccc_board.launch_product_async(tid)
        if launch_r.get("ok"):
            _product_inflight[key] = {
                "tid": tid,
                "started_at": now_iso(),
                "workspace": ws,
            }
            did_something = True
            continue

        # 6. 启动失败
        fail_count += 1
        write_product_fail_count(fail_counter_path, fail_count)
        err = launch_r.get("error", "")[:200]
        _log_stats(
            ws,
            "product_fail",
            tid,
            fail_count=fail_count,
            error=err,
        )
        try:
            from _failure_ledger import record_failure

            record_failure(
                ws,
                task_id=tid,
                role="product",
                reason=err or "product launch failed",
                phase=0,
                from_col="backlog",
                to_col=None,
                related_stats_event="product_fail",
            )
        except Exception:
            engine_log(f"[failures] product_fail ledger: {_traceback.format_exc()[:300]}")
        engine_log(f"[product] [{label}] product_role({tid}) 启动失败 #{fail_count}: {launch_r.get('error', '')}")
        if fail_count >= _MAX_PRODUCT_RETRIES:
            _mark_product_exhausted(f"product_role 连续失败 {fail_count} 次")
        did_something = True

    return did_something


def _auto_replenish_backlog(ws: Path, store, program_dir: Path) -> bool:
    """backlog + planned 都为空时，立即触发 audit_role 补充新任务。

    v0.42.4: **永久禁用**（自动识别投入会吃爆内存）。恒返回 False。
    """
    return False


# ═══════════════════════════════════════════════════════════════
# v0.28.2: Phase 并行调度（plan: engine-phase-parallel-dispatch）
# ═══════════════════════════════════════════════════════════════

