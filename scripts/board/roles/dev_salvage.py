"""board.roles.dev_salvage — try_complete / salvage → testing.

Extracted from board.roles.dev (min-pipeline v1.2 slim).
"""
from __future__ import annotations

import json
from pathlib import Path

from _config import get_logger
from _utils import sanitize_id
from board.context import get_workspace
from board.phase import (
    _apply_phase_status_updates,
    _current_running_phase,
    _load_phases,
    _mark_phase_done,
    _resolve_phase_dependencies,
)
from board.roles.common import list_tasks, move_task

_log = get_logger("board.roles")

def try_complete_if_gates_satisfied(task_id: str) -> dict | None:
    """门禁已满足时收口 → testing，禁止无意义 relaunch。

    Returns:
      success dict，或 None（未满足 / 不在 in_progress）。
    """
    from board.roles import dev as _dev

    _smoke_deliverable_satisfied = _dev._smoke_deliverable_satisfied
    _require_task_commit_for_testing = _dev._require_task_commit_for_testing
    _phase_scope = _dev._phase_scope

    task_id = sanitize_id(task_id)
    in_prog = list_tasks("in_progress")
    if not any(t["id"] == task_id for t in in_prog):
        return None

    from _opencode_quality_gate import (
        agent_declared_self_checks_passed,
        detect_hollow_opencode_run,
        report_has_self_checks_passed,
    )
    from _task_commit import ensure_task_commit, find_task_commit

    ws = get_workspace()
    commit = find_task_commit(ws, task_id)
    if not commit:
        # DoD：有交付物脏树时先补 task_id commit，再谈收口
        cur_phase = None
        try:
            cur_phase = _current_running_phase(task_id)
        except Exception:
            cur_phase = None
        ok_auto, why_auto, commit = ensure_task_commit(
            ws,
            task_id,
            phase_num=cur_phase if isinstance(cur_phase, int) else None,
            pre_head="",
        )
        if ok_auto and commit:
            _log.info(
                "[salvage] %s DoD auto-commit before gates: %s (%s)",
                task_id,
                why_auto,
                commit[:12],
            )
        else:
            commit = find_task_commit(ws, task_id) or ""
    if not commit:
        return None

    report_path = ws / ".ccc" / "reports" / f"{task_id}.report.md"
    result_path = ws / ".ccc" / "reports" / f"{task_id}.result.json"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    result_raw = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""

    # hollow 与正常完成路径对齐（salvage 不得绕过）
    try:
        _spath = None
        try:
            import json as _json

            _rd = _json.loads(result_raw) if (result_raw or "").strip().startswith("{") else {}
            if isinstance(_rd, dict):
                _spath = str(_rd.get("path") or "") or None
        except Exception:
            _spath = None
        hollow_reason = detect_hollow_opencode_run(
            result_raw, report, path=_spath
        )
    except Exception as exc:
        _log.warning("[salvage] %s hollow detect failed: %s", task_id, exc)
        hollow_reason = None
    if hollow_reason:
        _log.warning("[salvage] %s refused: hollow (%s)", task_id, hollow_reason[:160])
        return None

    # acceptance 关门：SELF-CHECKS 字符串不足以单独放行
    try:
        from _acceptance_gate import check_acceptance

        acc = check_acceptance(ws, task_id, commit=commit)
    except Exception as exc:
        _log.warning("[salvage] %s acceptance gate error: %s", task_id, exc)
        return None
    # OpenCode 已改工作树但未 commit：补 DoD commit 后再验一次
    if not acc.get("ok") and acc.get("reason") == "acceptance_uncommitted_vs_commit":
        cur_phase = None
        try:
            cur_phase = _current_running_phase(task_id)
        except Exception:
            cur_phase = None
        ok_auto, why_auto, new_c = ensure_task_commit(
            ws,
            task_id,
            phase_num=cur_phase if isinstance(cur_phase, int) else None,
            pre_head="",
        )
        if ok_auto and new_c and new_c != commit:
            _log.info(
                "[salvage] %s DoD recommit after uncommitted acceptance: %s (%s)",
                task_id,
                why_auto,
                new_c[:12],
            )
            commit = new_c
            try:
                acc = check_acceptance(ws, task_id, commit=commit)
            except Exception as exc:
                _log.warning("[salvage] %s acceptance recheck error: %s", task_id, exc)
                return None
        else:
            _log.warning(
                "[salvage] %s uncommitted acceptance but DoD recommit skipped: %s",
                task_id,
                why_auto,
            )
    if not acc.get("ok"):
        reason = str(acc.get("reason") or "acceptance_failed")
        _log.warning(
            "[salvage] %s refused: acceptance %s",
            task_id,
            reason,
        )
        # Surface to Engine acceptance_fail_budget (reopen≤2 → abnormal).
        # Returning None left cards stuck in salvage refuse loops while PID alive.
        return {
            "status": "acceptance_failed",
            "task_id": task_id,
            "error": f"acceptance-gate: {reason}",
            "reason": reason,
        }

    declared = agent_declared_self_checks_passed(report, result_raw)
    smoke_ok = _smoke_deliverable_satisfied(task_id)

    # 禁止用 missing-SELF-CHECKS stub 盖住已有标记；有标记则 materialize
    if declared and not report_has_self_checks_passed(report):
        body = (report or f"# {task_id} 执行报告\n").rstrip()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(body + "\n\nALL SELF-CHECKS PASSED\n", encoding="utf-8")
        _log.info(
            "[salvage] %s materialize SELF-CHECKS from agent evidence → report.md",
            task_id,
        )
    elif smoke_ok and not report.strip():
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            f"# {task_id} 执行报告\n\n"
            f"## 信息\n- 状态: salvage（commit+deliverable 已齐）\n"
            f"- commit: {commit[:12]}\n",
            encoding="utf-8",
        )

    cur_phase = _current_running_phase(task_id) or 1
    # hollow phase：salvage 不得绕过 scope 触碰检查
    try:
        from _opencode_quality_gate import detect_hollow_phase_scope

        _ph_hollow = detect_hollow_phase_scope(
            ws,
            phase_num=int(cur_phase),
            scope=_phase_scope(task_id, int(cur_phase)),
            task_commit=commit or "",
            phases=_load_phases(task_id),
        )
    except Exception as _ph_exc:
        _log.warning("[salvage] %s hollow-phase check error: %s", task_id, _ph_exc)
        _ph_hollow = None
    if _ph_hollow:
        _log.warning("[salvage] %s refused: %s", task_id, _ph_hollow)
        return None

    # 记录 commit 到 phases + mark done（仅当前 phase）
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if phases_file.is_file():
        try:
            lines = phases_file.read_text(encoding="utf-8").splitlines()
            updated: list[str] = []
            for line in lines:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                    if "schema_version" in d:
                        d["commit"] = commit
                    elif d.get("phase") == cur_phase:
                        d["status"] = "done"
                        d["commit"] = commit
                    updated.append(json.dumps(d, ensure_ascii=False))
                except json.JSONDecodeError:
                    updated.append(raw)
            phases_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
        except OSError as exc:
            _log.warning("[salvage] %s phases write failed: %s", task_id, exc)

    try:
        _mark_phase_done(task_id, cur_phase)
    except Exception as exc:
        _log.warning("[salvage] %s mark done failed: %s", task_id, exc)

    # 清 pid 标记；尽力杀残留
    pids_dir = ws / ".ccc" / "pids"
    pid_path = pids_dir / f"{task_id}.pid"
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text().strip())
            if pid > 0:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (OSError, ProcessLookupError) as exc:
                        _log.debug("[dev] kill %s: %s", pid, exc)
        except (ValueError, OSError) as exc:
            _log.debug("[dev] pid parse/kill %s: %s", pid, exc)

    for suffix in (
        ".done",
        ".exitcode",
        ".pid",
        ".prompt.md",
        ".pre_head",
        ".isolation.json",
    ):
        fp = pids_dir / f"{task_id}{suffix}"
        try:
            if fp.exists():
                fp.unlink()
        except OSError as exc:
            _log.debug("[dev] marker unlink %s/%s: %s", task_id, suffix, exc)

    # 若仍有后续 phase，不硬推 testing
    phases_now = _load_phases(task_id)
    executable, blocked, skipped = _resolve_phase_dependencies(phases_now)
    _apply_phase_status_updates(task_id, blocked, skipped)
    phases_now = _load_phases(task_id)
    executable, _blocked, _skipped = _resolve_phase_dependencies(phases_now)
    if executable:
        _log.info(
            "[salvage] %s gates ok but more phases %s — leave in_progress",
            task_id,
            executable,
        )
        return {
            "status": "phase_done",
            "task_id": task_id,
            "phase": cur_phase,
            "next_phase": min(executable),
            "salvaged": True,
        }

    ok_c, why_c, _ch = _require_task_commit_for_testing(task_id)
    if not ok_c:
        _log.warning("[salvage] %s commit-gate after mark: %s", task_id, why_c)
        return None

    move_task(task_id, "in_progress", "testing")
    _log.info(
        "[salvage] %s ✓ gates satisfied → testing (commit=%s declared=%s smoke=%s)",
        task_id,
        commit[:12],
        declared,
        smoke_ok,
    )
    return {
        "status": "success",
        "task_id": task_id,
        "salvaged": True,
        "commit": commit[:40],
    }

