"""engine/dispatch.py — 角色调度编排。

方案 1.1（2026-07-24）+ 2026-07-29 Wave C：
- 纯 helper：phase marker / top-level roots / wall clock
- try_launch_planned：从 planned 启 task（原 ccc-engine._try_launch_planned）

强耦合符号经 _eng() 回指 ccc_engine（与 gates/hang 同款），避免循环 import。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from board.phase import _load_phases
from board.roles.dev import dev_role_launch
from engine.workspace import _get_store, _ws_label, workspace_scope

# R-4: planned 跳过计数器 — 连续 N tick 缺文件/prepare 失败后挪 abnormal
# 模块级 dict，Engine 重启时重置（重启后 6 tick ≈ 1min 才会再挪，可接受）
_planned_skip_counter: dict[str, int] = {}


def _eng():
    # Prefer test module aliases first so pytest twins don't steal each other
    # (ccc_engine_test vs ccc_engine_parallel_test both may be loaded).
    for name in (
        "ccc_engine_parallel_test",
        "ccc_engine_test",
        "ccc_engine",
        "__main__",
    ):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "engine_log"):
            return mod
    import ccc_engine as mod  # noqa: PLC0415

    return mod


def _phase_market_subid(tid: str, phase_num: int) -> str:
    """Per-phase marker subid，避免并行 phase 写在同 task_id.{done,pid,exitcode}。

    用「task_id__p{N}」双下划线，与 ccc-board 的「task_id-p{N}」区分。
    """
    return f"{tid}__p{phase_num}"


def _top_level_roots(paths: list[str]) -> set[str]:
    """Distinct top-level path prefixes (skip .ccc hygiene)."""
    roots: set[str] = set()
    for raw in paths:
        s = str(raw or "").strip().lstrip("./")
        if not s or s.startswith(".ccc"):
            continue
        part = Path(s).parts[0] if Path(s).parts else ""
        if part:
            roots.add(part)
    return roots


def _phase_to_pgroup(p: int) -> str:
    """OpenCode pool / marker 用的 phase id（与 ccc-board 一致：task_id-pN）。"""
    return f"p{p}"


def _wall_seconds_from_started(started_at: str | None) -> float | None:
    """Parse active_tasks started_at → wall seconds; None if unparseable."""
    if not started_at:
        return None
    try:
        s = str(started_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds()), 2)
    except (TypeError, ValueError, OSError):
        return None


def try_launch_planned(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """从 planned 启动一个 task。返回 True 表示已启动。

    v0.28.2: 当 executable phase 数 >= 2 且未禁用并行时，走并行分支；
    失败时 fallback 到单 phase 串行 dev_role_launch。
    """
    with workspace_scope(ws):
        return try_launch_planned_unlocked(ws, active_tasks)


def try_launch_planned_unlocked(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """try_launch_planned 主体（已在 workspace_scope 内）。"""
    e = _eng()
    store = _get_store(ws)
    label = _ws_label(ws)
    planned = store.list_tasks("planned")
    for task in planned:
        tid = task["id"]
        try:
            from _board_garbage import is_garbage_board_card

            if is_garbage_board_card(tid, task):
                e.engine_log(f"[{label}] skip garbage planned {tid}")
                continue
        except ImportError:
            pass  # intentional — optional _board_garbage
        key = e._task_key(ws, tid)
        if key in active_tasks:
            # R-4 A2: 加 debug 日志（避免噪声，但可追踪残留 entry）
            e.engine_log(
                f"[{label}] {tid} 在 planned 但 active_tasks 残留 key={key}，跳过",
            )
            continue
        # 只调度 work 小卡（epic 永不进入 planned）
        from _board_store import normalize_task_view as _norm

        tview = _norm(task, column="planned")
        if tview.get("card_kind") == "epic":
            e.engine_log(f"[{label}] 跳过误入 planned 的 epic {tid}")
            continue
        plan_file = ws / ".ccc" / "plans" / f"{tid}.plan.md"
        phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
        if not plan_file.exists() or not phases_file.exists():
            # R-4 A1: 加日志 + 累计计数器，连续 6 tick（~1min）后挪 abnormal
            missing = "plan" if not plan_file.exists() else "phases"
            skip_n = _planned_skip_counter.get(tid, 0) + 1
            _planned_skip_counter[tid] = skip_n
            if skip_n >= 6:
                e.engine_log(
                    f"[{label}] {tid} 缺 {missing} 文件连续 {skip_n} tick → abnormal"
                )
                try:
                    store.move_task(tid, "planned", "abnormal")
                    store.patch_task(
                        tid,
                        {"note": f"engine: 缺 {missing} 文件连续 {skip_n} tick"},
                    )
                    store.update_index()
                    _planned_skip_counter.pop(tid, None)
                except Exception as exc:
                    e.engine_log(
                        f"[{label}] {tid} 缺文件挪 abnormal 失败: {exc}"
                    )
            else:
                e.engine_log(
                    f"[{label}] {tid} 缺 {missing} 文件 (skip={skip_n}/6) → 跳过"
                )
            continue
        # 文件存在则重置计数器
        _planned_skip_counter.pop(tid, None)

        phases = _load_phases(tid, ws)
        executable: set[int] = set()
        if phases:
            executable, blocked, skipped = e._resolve_phase_dependencies(phases)
            if blocked or skipped:
                e._apply_phase_status_updates(tid, blocked, skipped)
                e.engine_log(
                    f"[{label}] {tid} phase 依赖解析: executable={sorted(executable)} "
                    f"blocked={sorted(blocked)} skipped={sorted(skipped)}"
                )
            if phases and all(
                p.get("status") in ("skipped", "failed") or (p.get("phase") in skipped)
                for p in phases
            ):
                # R-4 A5: phases 全 skipped/failed → 挪 abnormal 触发自愈或人工介入
                e.engine_log(
                    f"[{label}] {tid} 所有 phase 被跳过（依赖失败链）→ abnormal"
                )
                try:
                    store.move_task(tid, "planned", "abnormal")
                    store.patch_task(
                        tid,
                        {"note": "engine: 所有 phase 被跳过（依赖失败链）"},
                    )
                    store.update_index()
                except Exception as exc:
                    e.engine_log(
                        f"[{label}] {tid} phases 全 skipped 挪 abnormal 失败: {exc}"
                    )
                continue

        complexity = task.get("complexity", "medium")
        # F-FLOW-05: task 级 depends_on_tasks — 依赖未 released 则跳过
        deps = task.get("depends_on_tasks") or []
        if isinstance(deps, str):
            deps = [deps]
        if deps:
            released_ids = {t["id"] for t in store.list_tasks("released")}
            blocked = [d for d in deps if d not in released_ids]
            if blocked:
                e.engine_log(
                    f"[{label}] {tid} 等待 task 依赖: {blocked}（未 released）"
                )
                continue
        if not e._can_accept_dev(active_tasks):
            return False
        e.engine_log(f"[{label}] 取新 task: {tid} (complexity={complexity})")

        force_serial = False
        if phases and executable and len(executable) >= 2:
            force_serial = e._force_serial_multi_root(
                phases, executable, ws=ws, tid=tid
            )
            if force_serial:
                e.engine_log(
                    f"[{label}] {tid} multi-root scope/acceptance → 强制串行 (skip phase parallel)"
                )
        if (
            phases
            and executable
            and len(executable) >= 2
            and not e.PHASE_PARALLEL_DISABLED
            and not force_serial
        ):
            groups = e._group_parallel_phases(phases, executable)
            if groups and len(groups[0]) >= 2:
                plan_content = plan_file.read_text(encoding="utf-8")
                timeout_s = e._lookup_phase_timeout(tid, phases)
                ok = e._try_launch_planned_parallel(
                    ws, tid, groups, plan_content, timeout_s
                )
                if ok:
                    if not store.move_task(tid, "planned", "in_progress"):
                        e.engine_log(
                            f"[engine] [{_ws_label(ws)}] move {tid} planned→in_progress 失败，不注册 active_task"
                        )
                        continue
                    if not e._register_active(
                        active_tasks,
                        ws,
                        tid,
                        complexity=complexity,
                        mode="parallel",
                    ):
                        e.engine_log(
                            f"[{label}] {tid} 并行已启动但槽满，无法登记（异常）"
                        )
                        continue
                    store.update_index()
                    return True
                e.engine_log(
                    f"[{label}] {tid} 并行启动失败，回退 dev_role_launch 串行"
                )

        _abnormal_tasks = store.list_tasks("abnormal")
        _prefix = "-".join(tid.split("-")[:3])
        _similar_failures = sum(
            1
            for t in _abnormal_tasks
            if isinstance(t.get("id"), str) and t["id"].startswith(_prefix)
        )
        if _similar_failures >= 5:
            e.engine_log(
                f"[{label}] {tid} 同类任务已有 {_similar_failures} 个在 abnormal，系统性失败 → 直接熔断，不重试"
            )
            store.move_task(tid, "planned", "abnormal")
            store.update_index()
            continue

        if e._check_abnormal_traffic(tid, "executor"):
            e.engine_log(
                f"[{label}] {tid} executor 调用过于频繁（1h>20），疑似死循环 → abnormal"
            )
            e._record_failure_pattern("abnormal-traffic-executor")
            store.move_task(tid, "planned", "abnormal")
            store.update_index()
            continue

        tkey = e._task_key(ws, tid)
        short_path: str | None = None
        try:
            from board.roles.board_ops import run_board_ops, should_use_board_ops
            from board.roles.script_seed import (
                run_feature_seed,
                run_script_seed,
                should_use_feature_seed,
                should_use_script_seed,
            )

            task_meta = next(
                (t for t in store.list_tasks("planned") if t.get("id") == tid),
                None,
            )
            if task_meta and should_use_script_seed(ws, task_meta):
                short_path = "script_seed"
                e.engine_log(
                    f"[{label}] {tid} script_seed short path (intent probe, no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                seed_r = run_script_seed(ws, tid)
                if not seed_r.get("ok"):
                    return e._handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="script_seed",
                        why=str(
                            seed_r.get("error") or seed_r.get("why") or seed_r
                        )[:300],
                    )
                e._clear_short_path_fail(ws, tid)
                e._log_stats(ws, "dev_path", tid, path="script_seed", ok=True)
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    e.engine_log(f"[{label}] {tid} script_seed OK → testing")
                store.update_index()
                return True
            if task_meta and should_use_feature_seed(ws, task_meta):
                short_path = "feature_seed"
                e.engine_log(
                    f"[{label}] {tid} feature_seed short path (feature probe, no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                feat_r = run_feature_seed(ws, tid)
                if not feat_r.get("ok"):
                    return e._handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="feature_seed",
                        why=str(
                            feat_r.get("error") or feat_r.get("why") or feat_r
                        )[:300],
                    )
                e._clear_short_path_fail(ws, tid)
                e._log_stats(ws, "dev_path", tid, path="feature_seed", ok=True)
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    e.engine_log(f"[{label}] {tid} feature_seed OK → testing")
                store.update_index()
                return True
            if task_meta and should_use_board_ops(ws, task_meta):
                short_path = "board_ops"
                e.engine_log(
                    f"[{label}] {tid} board_ops short path (no opencode; bypass same-ws mutex)"
                )
                if store.find_task(tid)[0] == "planned":
                    store.move_task(tid, "planned", "in_progress")
                ops_r = run_board_ops(ws, tid)
                if not ops_r.get("ok"):
                    return e._handle_short_path_failure(
                        ws,
                        tid,
                        store,
                        label=label,
                        path="board_ops",
                        why=str(ops_r.get("why") or ops_r)[:300],
                    )
                e._clear_short_path_fail(ws, tid)
                e._log_stats(ws, "dev_path", tid, path="board_ops", ok=True)
                col_now = store.find_task(tid)[0]
                if col_now == "in_progress":
                    store.move_task(tid, "in_progress", "testing")
                    e.engine_log(f"[{label}] {tid} board_ops OK → testing")
                store.update_index()
                return True
        except Exception as _bo_exc:
            if short_path:
                return e._handle_short_path_failure(
                    ws,
                    tid,
                    store,
                    label=label,
                    path=short_path,
                    why=str(_bo_exc)[:300],
                )
            e.engine_log(
                f"[{label}] {tid} board_ops/script_seed probe error: {_bo_exc}"
            )

        if e._workspace_blocks_new_opencode(ws, active_tasks):
            e.engine_log(
                f"[engine] [{label}] 同仓已有 active opencode，延后启动 {tid}"
            )
            continue

        if not e._try_acquire_opencode_slot(tkey):
            e.engine_log(
                f"[engine] opencode 槽忙（全局 {e._GLOBAL_OPENCODE_COUNT}/{e._GLOBAL_OPENCODE_MAX} 或同仓互斥），等待"
            )
            continue
        launch_r = dev_role_launch(tid)
        if "error" in launch_r:
            e._release_opencode_slot(tkey, 1)
            skip_tag = "（非重试性）" if launch_r.get("skip_retry") else ""
            e.engine_log(
                f"[{label}] 启动 {tid} 失败: {launch_r['error']}{skip_tag}"
            )
            err_s = str(launch_r.get("error") or "")
            if (
                launch_r.get("skip_retry")
                and "无待执行 phase" in err_s
                and "done" in err_s
            ):
                e._salvage_phases_done_planned(ws, tid, store, label=label)
            elif launch_r.get("skip_retry"):
                # R-4 A4: 非重试性失败（prepare_role_call 失败等）→ 挪 abnormal
                # 避免留 planned 导致 1Hz storm 空转
                e.engine_log(
                    f"[{label}] {tid} 启动非重试性失败 → abnormal: {err_s[:200]}"
                )
                try:
                    store.move_task(tid, "planned", "abnormal")
                    store.patch_task(
                        tid,
                        {"note": f"engine: prepare_role_call fail: {err_s[:300]}"},
                    )
                    store.update_index()
                except Exception as exc:
                    e.engine_log(
                        f"[{label}] {tid} skip_retry 挪 abnormal 失败: {exc}"
                    )
            continue
        if not e._register_active(
            active_tasks, ws, tid, complexity=complexity
        ):
            e._release_opencode_slot(tkey, 1)
            e.engine_log(f"[{label}] {tid} launch 成功但槽满，拒绝登记")
            continue
        e._log_stats(
            ws,
            "opencode_start",
            tid,
            complexity=complexity,
            pid=launch_r.get("pid"),
            mode="serial",
            path="opencode",
        )
        e._log_stats(ws, "dev_path", tid, path="opencode", ok=True)
        store.update_index()
        return True
    return False
