"""engine.gates — testing/verified 列门禁（reviewer/tester/pytest/kb）。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from _config import Config, get_logger
from _executor import _sanitized_env
from board.phase import _current_running_phase, _load_phases
from board.roles import kb_role, reviewer_role, tester_role
from engine.workspace import (
    _activate_workspace,
    _ensure_task_in_testing,
    _find_task_column,
    _get_store,
    _ws_label,
)

_log = get_logger("engine")
cfg = Config()

_PYTEST_FAIL_MAX = 3  # F-FLOW-01: pytest 连续失败上限 → abnormal


def _eng():
    for name in ("ccc_engine", "ccc_engine_test", "ccc_engine_parallel_test", "__main__"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "engine_log"):
            return m
    for m in sys.modules.values():
        f = getattr(m, "__file__", None)
        if f and str(f).endswith("ccc-engine.py") and hasattr(m, "engine_log"):
            return m
    return None


def _engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


def _verdict_file(ws: Path, tid: str) -> Path:
    return ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"


def _verdict_is_valid(ws: Path, tid: str) -> bool:
    """verdict 文件必须存在且非空（空文件视为未产出）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        return bool(vf.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _verdict_is_timeout(ws: Path, tid: str) -> bool:
    """检查 verdict 文件是否标记为 TIMEOUT（reviewer LLM 超时但未 quarantine）。"""
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


def _parse_verdict_status(content: str) -> str | None:
    """F-FLOW-03: 从 verdict 文件解析 **Verdict:** 字段，不使用裸子串。"""
    for line in content.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("**verdict:**") or low.startswith("verdict:"):
            raw = stripped.split(":", 1)[1].strip().strip("*").strip()
            return raw.split()[0].upper() if raw else None
    return None


def _run_pytest(ws: Path) -> tuple[int, str]:
    """在 workspace 跑 pytest tests/；有 .venv 则走 .venv/bin/pytest。"""
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]
    try:
        r = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=cfg.phase_timeout,
        )
        stdout = (
            r.stdout
            if isinstance(r.stdout, str)
            else (r.stdout.decode("utf-8", errors="replace") if r.stdout else "")
        )
        stderr = (
            r.stderr
            if isinstance(r.stderr, str)
            else (r.stderr.decode("utf-8", errors="replace") if r.stderr else "")
        )
        output = stdout + stderr
        return r.returncode, output
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout
            if isinstance(exc.stdout, str)
            else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        )
        stderr = (
            exc.stderr
            if isinstance(exc.stderr, str)
            else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
        )
        output = stdout + stderr
        return 1, output
    except OSError as exc:
        return 1, str(exc)


def _record_pytest_failure(ws: Path, tid: str, exit_code: int, output: str) -> None:
    """pytest 失败时写 verdict + pids 摘要（供 OpenCode relaunch 回灌）。"""
    vf = _verdict_file(ws, tid)
    vf.parent.mkdir(parents=True, exist_ok=True)
    snippet = output[-2000:] if output else "(无输出)"
    section = (
        f"\n\n## Engine pytest 检查\n\n"
        f"- **退出码**: {exit_code}\n\n"
        f"```\n{snippet}\n```\n"
    )
    try:
        if vf.is_file():
            vf.write_text(vf.read_text(encoding="utf-8") + section, encoding="utf-8")
        else:
            vf.write_text(
                f"# Verdict: {tid}\n\n**FAIL** (engine pytest)\n{section}",
                encoding="utf-8",
            )
    except OSError as exc:
        _engine_log(f"写入 pytest 失败记录到 verdict 失败: {exc}")
    try:
        pids = ws / ".ccc" / "pids"
        pids.mkdir(parents=True, exist_ok=True)
        (pids / f"{tid}.pytest_fail.md").write_text(
            f"exit_code={exit_code}\n\n{snippet}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _engine_log(f"写入 pytest_fail.md 失败: {exc}")


def _revert_task_commit(ws: Path, tid: str) -> bool:
    """Verdict FAIL 时回滚 task 的最后一个 commit。"""
    phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not phases_file.exists():
        return False
    try:
        phases_data = _load_phases(tid, ws)
        commits = [
            p.get("commit", "")
            for p in phases_data
            if p.get("commit") and p.get("commit") not in ("null", "None", "")
        ]
        if not commits:
            return False
        last_commit = commits[-1]
    except (OSError, json.JSONDecodeError) as exc:
        _engine_log(f"[verdict-gate] {tid} 读 commit hash 失败: {exc}")
        return False

    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", last_commit],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ws),
            env=_sanitized_env(),
        )
        if result.returncode != 0:
            _engine_log(
                f"[verdict-gate] {tid} revert {last_commit[:12]} 失败: "
                f"{result.stderr[:200]}"
            )
            return False
        _engine_log(f"[verdict-gate] {tid} 已 revert commit {last_commit[:12]}")
        return True
    except Exception as exc:
        _engine_log(f"[verdict-gate] {tid} revert 异常: {exc}")
        return False


def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。"""
    eng = _eng()
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    task_meta = next((t for t in store.list_tasks("testing") if t["id"] == tid), None)
    if task_meta and task_meta.get("complexity") == "small":
        verdict_dir = ws / ".ccc" / "verdicts"
        verdict_dir.mkdir(parents=True, exist_ok=True)
        (verdict_dir / f"{tid}.verdict.md").write_text(
            f"# {tid} Verdict\n\n**Verdict:** PASS\n\n"
            f"complexity=small: skipped reviewer+tester per STARTUP-BRIEF\n",
            encoding="utf-8",
        )
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            if eng:
                eng._log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        _engine_log(f"[{label}] {tid} complexity=small → verified (skip gate)")
        return _find_task_column(store, tid) == "verified"

    timeout_retries = cfg.reviewer_retry_on_timeout
    timeout_count = 0
    verdict_ok = False
    max_attempts = max(2, timeout_retries)

    for attempt in range(max_attempts):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            if _verdict_is_timeout(ws, tid):
                timeout_count += 1
                if timeout_count >= timeout_retries:
                    _engine_log(
                        f"[{label}] {tid} reviewer 超时重试 {timeout_count}/{timeout_retries} 耗尽 → abnormal"
                    )
                    cur_phase = _current_running_phase(tid)
                    if eng:
                        eng._quarantine_with_notify(
                            ws, tid, "reviewer 超时重试耗尽", store, phase=cur_phase
                        )
                    return False
                _clear_verdict(ws, tid)
                _ensure_task_in_testing(store, tid)
                _engine_log(
                    f"[{label}] {tid} reviewer 超时，等待重试 (attempt {attempt + 1}/{timeout_retries})"
                )
                time.sleep(30)
                continue
            verdict_ok = True
            break

        _engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/{max_attempts})"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == max_attempts - 1 and not verdict_ok:
            _engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            cur_phase = _current_running_phase(tid)
            if eng:
                eng._quarantine_with_notify(
                    ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase
                )
            store.update_index()
            return False

    _ensure_task_in_testing(store, tid)

    try:
        tester_role()
    except Exception as exc:
        _engine_log(f"[{label}] {tid} tester_role 异常: {exc}")

    _ensure_task_in_testing(store, tid)

    tests_dir = ws / "tests"
    if tests_dir.is_dir():
        exit_code, output = _run_pytest(ws)
        if eng:
            eng._log_stats(ws, "pytest", tid, exit_code=exit_code, output_len=len(output))
        if exit_code != 0:
            _record_pytest_failure(ws, tid, exit_code, output)
            pids_dir = ws / ".ccc" / "pids"
            pids_dir.mkdir(parents=True, exist_ok=True)
            fail_marker = pids_dir / f"{tid}.pytest_fails"
            try:
                fails = int(fail_marker.read_text().strip() or "0")
            except (OSError, ValueError):
                fails = 0
            fails += 1
            fail_marker.write_text(str(fails))
            if fails >= _PYTEST_FAIL_MAX:
                _engine_log(
                    f"[{label}] {tid} pytest 连续失败 {fails}/{_PYTEST_FAIL_MAX} → abnormal"
                )
                cur_phase = _current_running_phase(tid)
                if eng:
                    eng._quarantine_with_notify(
                        ws,
                        tid,
                        f"pytest 连续失败 {fails} 次 (exit={exit_code})",
                        store,
                        phase=cur_phase,
                    )
                try:
                    fail_marker.unlink(missing_ok=True)
                except OSError:
                    pass
                return False
            _engine_log(
                f"[{label}] {tid} pytest 失败 (exit={exit_code}) "
                f"count={fails}/{_PYTEST_FAIL_MAX}，留在 testing"
            )
            if eng:
                eng._ccc_notify(
                    "CCC",
                    f"任务 {tid} pytest 未通过 (exit={exit_code}) "
                    f"{fails}/{_PYTEST_FAIL_MAX}",
                )
            store.update_index()
            return False
        fail_marker = ws / ".ccc" / "pids" / f"{tid}.pytest_fails"
        fail_summary = ws / ".ccc" / "pids" / f"{tid}.pytest_fail.md"
        try:
            fail_marker.unlink(missing_ok=True)
            fail_summary.unlink(missing_ok=True)
        except OSError:
            pass
    else:
        _engine_log(f"[{label}] {tid} 无 tests/ 目录，跳过 engine pytest")

    if _verdict_is_valid(ws, tid):
        _vf = _verdict_file(ws, tid)
        try:
            _vcontent = _vf.read_text()
            status = _parse_verdict_status(_vcontent)
            if status in ("FAIL", "FALLBACK", "QUARANTINED"):
                _engine_log(
                    f"[verdict-gate] [{_ws_label(ws)}] {tid} "
                    f"verdict={status} — 触发回滚"
                )
                _revert_task_commit(ws, tid)
                store.move_task(tid, "testing", "planned")
                _clear_verdict(ws, tid)
                return False
        except OSError:
            pass

    if verdict_ok:
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            if eng:
                eng._log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        return _find_task_column(store, tid) == "verified"

    store.update_index()
    return False


def _refresh_parent_epic(ws: Path, work_tid: str) -> None:
    """子卡进入 verified/released 后立刻刷新 parent epic 五态。"""
    try:
        store = _get_store(ws)
        _col, task = store.find_task(work_tid)
        parent = (task or {}).get("parent_id")
        if not parent:
            from _board_store import normalize_task_view as _ntv

            task = _ntv(task or {"id": work_tid}, column=_col or "testing")
            parent = task.get("parent_id")
        if not parent:
            return
        from _product_fanout import refresh_epic_lifecycle

        new = refresh_epic_lifecycle(store, str(parent))
        if new:
            _engine_log(f"[{_ws_label(ws)}] epic {parent} refresh → {new}")
    except Exception as exc:
        _engine_log(f"[{_ws_label(ws)}] refresh parent epic for {work_tid}: {exc}")


def _run_verified_kb_gate(ws: Path) -> None:
    """v0.38: 扫 verified → kb_role → released（补齐 7 角色闭环）。"""
    eng = _eng()
    _activate_workspace(ws)
    store = _get_store(ws)
    verified = store.list_tasks("verified")
    if not verified:
        return
    label = _ws_label(ws)
    _engine_log(f"[{label}] verified 列有 {len(verified)} 个任务，跑 kb_role")
    try:
        result = kb_role()
        moved = (result or {}).get("moved") or []
        for tid in moved:
            if eng:
                eng._log_stats(ws, "move", tid, from_col="verified", to_col="released")
            _engine_log(f"[{label}] {tid} ✓ kb → released")
            _refresh_parent_epic(ws, tid)
        store.update_index()
    except Exception as exc:
        _engine_log(f"[{label}] kb_role 异常: {exc}")


def _run_testing_tasks_gate(ws: Path) -> None:
    """对 testing 列每个 task 跑 reviewer/tester 门禁。"""
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    for task in store.list_tasks("testing"):
        tid = task["id"]
        _engine_log(f"[{label}] testing 门禁: {tid}")
        try:
            ok = _run_reviewer_tester_gate(ws, tid)
            if ok:
                _refresh_parent_epic(ws, tid)
        except Exception as exc:
            _engine_log(f"[{label}] {tid} reviewer/tester 门禁异常: {exc}")
