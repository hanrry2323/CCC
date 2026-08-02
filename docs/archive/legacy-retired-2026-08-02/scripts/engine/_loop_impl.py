"""engine._loop_impl — engine_loop main poll

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.loop.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def engine_loop(workspaces: list[Path]) -> None:
    """引擎主循环：多 workspace 轮询，全局 MAX_CONCURRENT 共享。"""
    global MAX_RETRY
    global _engine_shutdown
    global _intake_bypass_ticks_left, _intake_bypass_degraded

    # v0.39.2: 仅 control=enabled 才进业务循环；ui/disabled 均 idle
    try:
        from _ccc_control import get_mode, may_start_engine
    except ImportError:

        def may_start_engine() -> bool:
            return not (Path.home() / ".ccc" / "DISABLED").is_file()

        def get_mode() -> str:
            return "enabled" if may_start_engine() else "disabled"

    if not may_start_engine():
        engine_log(f"CCC control={get_mode()} — idle hold (full: python3 scripts/_ccc_control.py enable)")
        while not _engine_shutdown and not may_start_engine():
            time.sleep(60)
        if _engine_shutdown:
            return
        engine_log("CCC control=enabled — entering normal loop")

    # 启动即消费 wake（须在 recover 之前：ccc-demo testing recover 可堵数分钟，否则人下达饿死）
    try:
        if _apply_dispatch_wake(workspaces):
            workspaces[:] = _prioritize_wake_workspace(workspaces, _wake_priority_workspace)
            engine_log("[wake] applied before recover — priority intake armed")
    except Exception as exc:
        engine_log(f"[wake] pre-recover apply failed: {exc}")

    program_dir = Path.home() / "program"
    labels = [_ws_label(w, program_dir) for w in workspaces]
    engine_log(f"CCC Engine 启动 ({len(workspaces)} workspace)")
    engine_log(f"  workspaces={labels}")
    engine_log(f"  poll_interval={cfg.engine_poll_interval}s, idle_sleep={cfg.engine_idle_sleep}s")
    engine_log(f"  max_retry={MAX_RETRY}, max_concurrent={MAX_CONCURRENT}")
    engine_log(f"  max_product_inflight={MAX_PRODUCT_INFLIGHT}, max_product_per_ws={MAX_PRODUCT_PER_WS}")

    _write_engine_restart("started")

    active_tasks: dict[str, dict] = {}
    iteration = 0

    # R4: 从持久化文件恢复 active_tasks，避免重启丢上下文
    active_tasks = _load_active_tasks()
    # 持久化可能超过并发上限（旧 bug）；裁到 MAX_CONCURRENT
    if len(active_tasks) > MAX_CONCURRENT:
        overflow = list(active_tasks.keys())[MAX_CONCURRENT:]
        for k in overflow:
            info = active_tasks.pop(k)
            _enqueue_pending_relaunch(
                info.get("workspace") or Path(k.split("|")[0]),
                info.get("task_id") or k.split("|")[-1],
                complexity=info.get("complexity", "medium"),
                reason="trim_overflow",
            )
        _save_active_tasks(active_tasks)
        engine_log(f"[slot] 启动裁剪 active_tasks → {MAX_CONCURRENT}，溢出 {len(overflow)} 入 pending_relaunch")
    _load_hang_retry_counter()

    # v0.36: 启动时先采样内存（在 recover 之前，避免 recover 间隔拖慢 heartbeat）
    try:
        _cleanup_global_opencode_pids()
    except Exception as exc:
        engine_log(f"[pids] global opencode-pids cleanup failed: {exc}")
    for ws in workspaces:
        try:
            _check_process_memory(ws)
            _cleanup_zombie_pid_refs(ws)
        except Exception as exc:
            engine_log(f"[mem] startup sample failed for {_ws_label(ws)}: {exc}")

    _rebuild_product_inflight(workspaces)

    for ws in workspaces:
        _recover_tasks(ws, active_tasks)

    _start_tick_watchdog()

    while not _engine_shutdown:
        # 运行中也能响应 disable/ui：否则 control 切换后仍继续拉任务吃内存
        if not may_start_engine():
            engine_log(
                f"CCC control={get_mode()} — mid-loop idle hold (resume: python3 scripts/_ccc_control.py enable)"
            )
            while not _engine_shutdown and not may_start_engine():
                time.sleep(15)
            if _engine_shutdown:
                break
            engine_log(f"CCC control={get_mode()} — resume engine loop")
            continue

        iteration += 1
        _mark_engine_tick()
        _maybe_sample_host_resources(active_tasks)
        tick_start = time.time()
        # 非深睡时也消费 wake：人下达立刻优先 intake，不等人空闲
        try:
            if _apply_dispatch_wake(workspaces):
                workspaces[:] = _prioritize_wake_workspace(workspaces, _wake_priority_workspace)
                # 即使 degraded_mode 也强制 bypass 让新卡进 product
                _intake_bypass_degraded = True
                _intake_bypass_ticks_left = _INTAKE_BYPASS_TICKS
        except Exception as exc:
            engine_log(f"[wake] apply dispatch wake failed: {exc}")
        if _intake_bypass_ticks_left > 0:
            _intake_bypass_ticks_left -= 1
            if _intake_bypass_ticks_left <= 0:
                _intake_bypass_degraded = False
        any_active = bool(active_tasks)

        first_task = next(iter(active_tasks.values()), {})
        first_task_id = first_task.get("task_id")
        first_task_ws = first_task.get("workspace")
        current_phase = None
        if first_task_id and first_task_ws:
            try:
                _activate_workspace(first_task_ws)
                current_phase = _current_running_phase(first_task_id)
            except Exception as exc:
                engine_log(f"stats phase lookup failed for {first_task_id}: {exc}")
        _update_stats(
            active_count=len(active_tasks),
            current_task=first_task_id,
            current_phase=current_phase,
            phase_status="running" if any_active else "done",
            workspace_name=first_task_ws.name if first_task_ws else None,
        )

        try:
            completed_tasks: list[str] = []
            if active_tasks:
                # v0.31+: hang 自动重启（Phase 4 + Phase 5 联合投递）
                # Phase 4 先检测并写 .hung marker，Phase 5 再消费 marker 触发
                # kill+stash+relaunch，最后再做完成判定。
                hang_freed_ws: list[Path] = []
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_and_mark_hung(ws, active_tasks)
                    if _run_hang_auto_restart(ws, active_tasks):
                        hang_freed_ws.append(ws)
                # 方案 A：hang 释槽后同 tick 优先 launch 该仓 planned（不放开同仓双 OpenCode）
                if hang_freed_ws:
                    seen: set[Path] = set()
                    prioritized: list[Path] = []
                    for ws in hang_freed_ws + list(workspaces):
                        if ws in seen:
                            continue
                        seen.add(ws)
                        prioritized.append(ws)
                    workspaces[:] = prioritized
                for key, info in list(active_tasks.items()):
                    ws = info["workspace"]
                    tid = info["task_id"]
                    label = _ws_label(ws, program_dir)
                    _activate_workspace(ws)
                    mode = info.get("mode", "serial")
                    if mode == "parallel":
                        # v0.28.2: 并行 task 走专用检查器
                        par_state = _check_parallel_task_complete(ws, tid)
                        if par_state == "still_running":
                            if iteration % 60 == 0:
                                engine_log(f"[parallel] [{label}] {tid} 执行中")
                            any_active = True
                            continue
                        # task_complete_ok / task_complete_fail → 包装成 result
                        if par_state == "task_complete_ok":
                            result = {"status": "success", "retry": 0}
                        else:
                            result = {"status": "failed", "retry": 0}
                    else:
                        result = dev_role_check_complete(tid)
                    status = result.get("status", "unknown")
                    complexity = info.get("complexity", "medium")

                    if status == "running":
                        if iteration % 60 == 0:
                            engine_log(f"[{label}] {tid} 执行中")
                        any_active = True
                        continue

                    if _handle_task_result(
                        ws,
                        tid,
                        result,
                        complexity=complexity,
                        started_at=info.get("started_at"),
                    ):
                        # P1: 任意终态统一释槽（serial；parallel 在 group 完成时已递减）
                        if mode != "parallel":
                            _release_dev_slot(None, ws, tid, reap=True)
                            # active_tasks pop 仍由下方 completed_tasks 负责，避免双重 save 竞态
                            # 槽位已在 release_dev_slot(None) 释放；此处只 pop dict
                        completed_tasks.append(key)

                for key in completed_tasks:
                    active_tasks.pop(key, None)
                if completed_tasks:
                    _save_active_tasks(active_tasks)
                # tick 边界重置 fallback 标志
                _reset_parallel_disabled_after_tick()

            # product 不占 dev 槽：先 GC 孤儿 inflight，再 backlog intake（自有 cap）
            try:
                _gc_product_inflight(workspaces)
            except Exception as exc:
                engine_log(f"[product] inflight GC error: {exc}")
            for ws in workspaces:
                _activate_workspace(ws)
                if _process_backlog(ws):
                    any_active = True

            # P4: 先 launch planned，再跑 testing 门禁（禁止「先测完全列才 launch」）
            while len(active_tasks) < MAX_CONCURRENT and not _engine_shutdown:
                did_something = False
                if _try_fill_pending_relaunch(active_tasks):
                    did_something = True
                    any_active = True
                for ws in workspaces:
                    if len(active_tasks) >= MAX_CONCURRENT:
                        break
                    if _try_launch_planned(ws, active_tasks):
                        did_something = True
                        any_active = True
                if not did_something:
                    break

            # 每 tick：testing → verify 一扇门（内部可复用 reviewer/tester）
            for ws in workspaces:
                try:
                    _activate_workspace(ws)
                    _store = _get_store(ws)
                    if _store.list_tasks("testing"):
                        _run_testing_tasks_gate(ws)
                except Exception as exc:
                    engine_log(f"[verify-gate] {_ws_label(ws)}: {exc}")

            # 每 tick：verified → done（min-pipeline kb 快通）
            for ws in workspaces:
                try:
                    _activate_workspace(ws)
                    _store2 = _get_store(ws)
                    if _store2.list_tasks("verified"):
                        _run_verified_kb_gate(ws)
                except Exception as exc:
                    engine_log(f"[verify→done] {_ws_label(ws)}: {exc}")

            # 每 6 轮（~60s）跑一次 degraded 检测 + stale check + 统计聚合
            if iteration % 6 == 0:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_degraded(ws)
                    _store = _get_store(ws)
                    _check_stale(ws, active_tasks)
                    # enabled 下：瞬态 abnormal work 有限自动 reopen（非 invent）
                    try:
                        _retry_abnormal_failures(ws)
                    except Exception as exc:
                        engine_log(f"[abnormal-refeed] {_ws_label(ws)}: {exc}")
                    # 编排自愈 L1：pending_no_fanout 有限重扇出 + 沉底孤儿 running
                    try:
                        from chat_server.services.board_repair import auto_heal_workspace

                        pid = _ws_label(ws)
                        heal = auto_heal_workspace(ws, pid, reason="engine_auto_heal")
                        att = (heal.get("pending_heal") or {}).get("attempted") or []
                        settled_n = (heal.get("settled_stuck") or {}).get("count") or 0
                        if att or settled_n:
                            engine_log(
                                f"[auto-heal] [{pid}] refanout={len(att)} "
                                f"settled_stuck={settled_n} needs_agent={heal.get('needs_agent')}"
                            )
                    except Exception as exc:
                        engine_log(f"[auto-heal] {_ws_label(ws)}: {exc}")
                    # v0.36: 每 36 tick (~6min) 内存监控 + 残影 PID 清理
                    if iteration % 36 == 0:
                        try:
                            _cleanup_global_opencode_pids()
                        except Exception as exc:
                            engine_log(f"[pids] global opencode-pids cleanup 异常: {exc}")
                        try:
                            _check_process_memory(ws)
                        except Exception as exc:
                            engine_log(f"[mem] {_ws_label(ws)} 异常: {exc}")
                        try:
                            _cleanup_zombie_pid_refs(ws)
                        except Exception as exc:
                            engine_log(f"[pids] {_ws_label(ws)} cleanup 异常: {exc}")
                    # v0.30: 定期统计聚合（即使系统忙）
                    try:
                        aggregate_stats(ws)
                        # v0.31: 自适应调参 — 最小路径跳过（非热路径）
                        _skip_tune = False
                        try:
                            from engine.min_pipeline import enabled as _mp

                            _skip_tune = bool(_mp())
                        except Exception:
                            _skip_tune = True
                        if not _skip_tune:
                            try:
                                summary = load_summary(ws)
                                if summary and summary.get("total_events", 0) > 5:
                                    task_stats = summary.get("task_stats", {})
                                    total = task_stats.get("total", 0)
                                    failed = task_stats.get("failed", 0)
                                    if total > 0:
                                        fail_rate = failed / total
                                        if fail_rate > 0.4 and MAX_RETRY < 5:
                                            engine_log(
                                                f"[auto-tune] fail_rate={fail_rate:.0%}, MAX_RETRY={MAX_RETRY} (adjusting)"
                                            )
                                            MAX_RETRY = min(MAX_RETRY + 1, 5)
                                            ccc_board.MAX_RETRY = MAX_RETRY  # F-ROLE-04
                                        elif fail_rate < 0.1 and MAX_RETRY > 2:
                                            engine_log(
                                                f"[auto-tune] fail_rate={fail_rate:.0%}, MAX_RETRY={MAX_RETRY} (reducing)"
                                            )
                                            MAX_RETRY = max(MAX_RETRY - 1, 2)
                                            ccc_board.MAX_RETRY = MAX_RETRY  # F-ROLE-04
                            except Exception as exc:
                                engine_log(f"[auto-tune] error: {exc}")
                    except Exception as exc:
                        engine_log(f"[stats] periodic aggregate error for {ws.name}: {exc}")
            ws_first_running: dict[str, str | None] = {}
            ws_active_counts: dict[str, int] = {}
            for info in active_tasks.values():
                ws_key = str(info["workspace"])
                if ws_key not in ws_first_running:
                    ws_first_running[ws_key] = info["task_id"]
                ws_active_counts[ws_key] = ws_active_counts.get(ws_key, 0) + 1
            for ws in workspaces:
                ws_key = str(ws)
                running_task_id = ws_first_running.get(ws_key)
                ws_count = ws_active_counts.get(ws_key, 0)
                ws_pids = _get_running_pids(ws) if running_task_id else []
                try:
                    testing_n = len(_get_store(ws).list_tasks("testing"))
                except Exception:
                    testing_n = 0
                _write_heartbeat(
                    ws,
                    running_task_id,
                    ws_count,
                    ws_pids,
                    testing_count=testing_n,
                    global_active_count=len(active_tasks),
                )

            if not active_tasks:
                for ws in workspaces:
                    _activate_workspace(ws)
                    _check_stale(ws, active_tasks)
                    # 空闲时立即处理 testing 任务（仍限预算）
                    _store2 = _get_store(ws)
                    test_tasks = _store2.list_tasks("testing")
                    if test_tasks:
                        label = _ws_label(ws)
                        engine_log(
                            f"[{label}] idle: testing 列有 {len(test_tasks)} 个任务，跑 verify 门禁（限预算）"
                        )
                        _run_testing_tasks_gate(ws)
                    if _store2.list_tasks("verified"):
                        _run_verified_kb_gate(ws)
                    _write_heartbeat(
                        ws,
                        None,
                        0,
                        [],
                        testing_count=len(test_tasks),
                        global_active_count=0,
                    )

                    # v0.40: enabled=只消费；invent 才允许 audit/evolve/replenish/abnormal
                    # v0.51.0 P2-1: _may_invent() 恒 False（INVENT_HARD_DISABLED），化简为仅检查 consumable
                    _has_consumable = _queue_has_consumable_work(_store2)
                    if not _has_consumable:
                        continue

                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 audit_role 自动触发（永不触发）
                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 evolve-on-idle 块（永不触发）
                    # v0.51.0 P2-1: 删除 _may_invent() 守护的 _auto_replenish_backlog / _retry_abnormal_failures 块（永不触发）

                    _check_new_reviews(ws)

                    # v0.30: 空闲时聚合统计 → 反馈回路（学习飞轮）
                    try:
                        summary = aggregate_stats(ws)
                        if summary:
                            insights = summary.get("perf_insights", [])
                            recs = summary.get("recommendations", [])
                            for ins in insights:
                                if ins.get("severity") == "warning":
                                    engine_log(
                                        "[stats] %s — %s",
                                        ws.name,
                                        ins.get("label", ""),
                                    )
                            for rec in recs:
                                if rec.get("action") != "system_healthy":
                                    engine_log(
                                        "[stats-recommend] %s: %s",
                                        rec.get("action", "?"),
                                        rec.get("suggestion", ""),
                                    )
                    except Exception as exc:
                        engine_log(f"[stats] aggregate error for {ws.name}: {exc}")

            # v0.40: 无可消费队列 → 深睡（≥60s），避免空转造功
            any_consumable = False
            for ws in workspaces:
                try:
                    if _queue_has_consumable_work(_get_store(ws)):
                        any_consumable = True
                        break
                except Exception as exc:
                    _log.debug("[idle_check] consumable probe %s: %s", ws, str(exc))
            if not any_active and not any_consumable and not _may_invent():
                if iteration % 12 == 1:
                    engine_log(f"CCC control={get_mode()} — queue empty, deep sleep 60s (wake: ~/.ccc/engine.wake)")
                # v0.41: 可被下任务 wake 文件打断
                wake_payload = _sleep_until_wake(60)
                if wake_payload is not None:
                    engine_log("[wake] 收到 engine.wake，立即进入下一 tick")
                    # 唤醒后必须重扫 registry：新 register 的 app 否则永远 invisible
                    # （曾导致 clawmed-ccc epic 在 backlog，Engine 只盯 ccc-demo 报 queue empty）
                    workspaces[:] = _rediscover_workspaces(workspaces)
                    try:
                        _apply_dispatch_wake(workspaces, already_consumed=wake_payload)
                        workspaces[:] = _prioritize_wake_workspace(workspaces, _wake_priority_workspace)
                    except Exception as exc:
                        engine_log(f"[wake] post-deep-sleep apply failed: {exc}")
                elif iteration % 12 == 0:
                    # 深睡满轮也轻量重扫，覆盖「只 register 未 wake」
                    workspaces[:] = _rediscover_workspaces(workspaces)
                continue

            if not any_active:
                time.sleep(cfg.engine_tick_interval)
                continue

        except KeyboardInterrupt:
            engine_log("收到 SIGINT, 优雅关闭")
            break
        except Exception as e:
            engine_log(f"异常: {e}")
            tb_text = _traceback.format_exc()
            engine_log(f"{tb_text[:2000]}")
            # 末行上下文（勿用未定义的 _tb）
            last = next(
                (ln for ln in reversed(tb_text.splitlines()) if ln.strip()),
                "",
            )
            if last:
                engine_log(f"  {last[:300]}")
            time.sleep(cfg.engine_idle_sleep)
            continue

        _wait_tick(tick_start)

    engine_log("收到关闭信号，停止接收新任务")


