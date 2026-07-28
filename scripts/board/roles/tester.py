"""board.roles.tester — extracted from ccc-board.py (behavior-preserving)."""
# TODO F4-1: migrate to build_role_context
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import uuid
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config, get_logger, parse_duration
from _executor import _claude_env, _sanitized_env
from _board_store import FileBoardStore, _atomic_write as _store_atomic_write
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _utils import sanitize_prompt_input as _sanitize_prompt_input
from _claude_cli import ClaudeCliMissing, resolve_claude_cli
import phase_lint

from board.context import get_workspace, set_workspace, board_dir, ccc_home
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import build_dev_phase_prompt
from board.phase import (
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _move_task_to_abnormal_if_all_terminal_failed,
)
from board.roles.common import (
    cfg,
    store,
    _log,
    CCC_HOME,
    MAX_RETRY,
    MAX_STALE_HOURS,
    sanitize_id,
    now_iso,
    _quarantine,
    list_tasks,
    move_task,
    create_task,
    update_index,
    _get_cfg,
    _get_store,
    _reset_lazy,
    _backoff_seconds,
    _load_timeout,
    _load_retry_cap,
    _load_retry_from_phases,
    _claude_bin,
    _get_relay_url,
    WORKSPACES,
)

# 验收命令白名单：共享 _intent_probe（LPSN · P，含 DRY_RUN / .venv）
from _intent_probe import (  # noqa: E402
    VERIFY_CMD_ALLOW_PREFIXES as _VERIFY_CMD_ALLOW_PREFIXES,
    extract_probe_commands,
    filter_verify_commands as _intent_filter,
    is_allowed_verify_cmd as _is_allowed_verify_cmd,
)


def _filter_verify_commands(cmds: list[str]) -> list[str]:
    out = _intent_filter(cmds)
    dropped = len(cmds) - len(out)
    if dropped:
        _log.warning("[tester] dropped %d non-allowlisted verify cmd(s)", dropped)
    return out


def _task_skips_forced_pytest(
    ws: Path, task_id: str, task_meta: dict | None
) -> bool:
    """Single source for skip: docs/doc_only/hygiene — never a partial path allowlist."""
    try:
        from _ccc_hygiene import task_skips_forced_pytest

        return bool(task_skips_forced_pytest(ws, task_id, task_meta))
    except Exception as exc:
        _log.warning("[tester] hygiene probe: %s", exc)
        return False


def build_tester_verify_commands(
    ws: Path,
    task_id: str,
    *,
    plan_commands: list[str] | None = None,
    task_meta: dict | None = None,
) -> tuple[list[str], bool]:
    """Resolve verify cmds + whether forced full-repo pytest was skipped.

    Forced ``pytest tests/ --cov-fail-under=80`` is appended only when the plan
    has **no** acceptance probes and the card does not already skip (doc_only /
    docs-only / hygiene / short path). Plan probes are authoritative — open-intent
    / script_seed cards with ``python3 -c`` asserts must not be failed by qb's
    full-suite cov gate (R7 ACCEPTANCE_FAIL after reviewer PASS).
    """
    plan_commands = list(plan_commands or [])
    verify_commands = list(plan_commands)
    skip_forced = _task_skips_forced_pytest(ws, task_id, task_meta)

    if not verify_commands and not skip_forced:
        verify_commands = [
            f"python3 -m pytest {ws / 'tests' / 'scripts'} -q --tb=line --timeout=60"
        ]

    has_pyproject = (ws / "pyproject.toml").exists()
    # Plan already listed probes → do not pile on full-repo cov (even if none
    # of the probes contain the substring "pytest").
    if (
        has_pyproject
        and not skip_forced
        and not plan_commands
        and not any("pytest" in c for c in verify_commands)
    ):
        verify_commands.append(
            "python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
        )

    return _filter_verify_commands(verify_commands), skip_forced


def launch_tester_async(task_id: str, ws: Path) -> dict:
    """异步启动 tester 验证子进程。

    从 plan 提取验证命令，写入 shell 脚本后 Popen bash 执行。

    Returns: {"ok": True, "pid": int, "cmds": int}
             {"error": str}
    """
    from _role_lock import assert_role_executor

    assert_role_executor("tester", "pytest")
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 1. 从 plan 提取验证命令（共享 intent probe 解析）
    plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
    plan_commands: list[str] = []
    if plan_file.exists():
        plan_commands = extract_probe_commands(
            plan_file.read_text(encoding="utf-8", errors="replace")
        )

    task_meta = None
    try:
        store = FileBoardStore(ws)
        for col in (
            "testing",
            "in_progress",
            "planned",
            "verified",
            "backlog",
        ):
            task_meta = next(
                (t for t in store.list_tasks(col) if t.get("id") == task_id),
                None,
            )
            if task_meta:
                break
    except Exception as exc:
        _log.debug("[tester] task meta: %s", exc)
        task_meta = None

    verify_commands, skip_forced = build_tester_verify_commands(
        ws, task_id, plan_commands=plan_commands, task_meta=task_meta
    )
    if not verify_commands:
        if skip_forced:
            _log.info(
                "[tester-async] %s ops/ccc-hygiene — 无白名单 cmd，跳过强制 pytest",
                task_id,
            )
            return {"ok": True, "pid": 0, "cmds": 0, "skipped_hygiene": True}
        return {"error": "no allowlisted verify commands (plan injection blocked)"}

    # 2. 写入 shell 脚本
    script_lines = ["#!/bin/bash", "set -e"]
    for cmd in verify_commands:
        script_lines.append(cmd)
    script_content = "\n".join(script_lines) + "\n"

    script_file = pids_dir / f"{task_id}.tester.sh"
    script_file.write_text(script_content)
    script_file.chmod(0o700)

    # 3. 清理残留标记
    for sfx in [".tester.done", ".tester.exitcode", ".tester.out", ".tester.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError as exc:
            _log.debug("[tester] marker unlink %s: %s", f, exc)

    # 4. Popen bash script
    result_file = pids_dir / f"{task_id}.tester.out"
    exitcode_file = pids_dir / f"{task_id}.tester.exitcode"

    try:
        with open(result_file, "w") as out_f:
            proc = subprocess.Popen(
                ["bash", str(script_file)],
                stdout=out_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=ws,
                env=_sanitized_env(),
            )
        pids_dir.joinpath(f"{task_id}.tester.pid").write_text(str(proc.pid))
        _log.info(
            "[tester-async] %s launched PID=%d, %d commands",
            task_id,
            proc.pid,
            len(verify_commands),
        )
        return {"ok": True, "pid": proc.pid, "cmds": len(verify_commands)}
    except Exception as exc:
        _log.error("[tester-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def check_tester_async(task_id: str, ws: Path) -> dict:
    """检查异步 tester 是否完成。

    Returns:
        {"status": "pass"} — 所有验证通过
        {"status": "failed", "exit_code": int, "output": str} — 验证失败
        {"status": "running"} — 仍在执行
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.tester.done"
    exitcode_file = pids_dir / f"{task_id}.tester.exitcode"
    result_file = pids_dir / f"{task_id}.tester.out"
    pid_file = pids_dir / f"{task_id}.tester.pid"

    # 检查是否完成
    is_done = done_file.exists() or exitcode_file.exists()

    if not is_done:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running"}
            except (ValueError, ProcessLookupError) as exc:
                _log.debug("[tester] pid probe parse/lost %s: %s", pid_file, exc)
            except OSError as exc:
                _log.debug("[tester] pid probe OSError %s: %s", pid_file, exc)
        return {"status": "failed", "exit_code": -1, "output": "process exited"}

    if exitcode_file.exists():
        try:
            exit_code = int(exitcode_file.read_text().strip())
        except (ValueError, OSError):
            exit_code = -1
    else:
        exit_code = 0

    output = result_file.read_text() if result_file.exists() else ""

    # 清理标记
    _cleanup_tester_markers(pids_dir, task_id)

    if exit_code == 0:
        return {"status": "pass"}
    return {"status": "failed", "exit_code": exit_code, "output": output[:2000]}


def _cleanup_tester_markers(pids_dir: Path, task_id: str) -> None:
    """清理 tester async 标记文件"""
    for sfx in [
        ".tester.done",
        ".tester.exitcode",
        ".tester.out",
        ".tester.pid",
        ".tester.sh",
    ]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError as exc:
            _log.debug("[tester] cleanup unlink %s: %s", f, exc)


def launch_pytest_async(task_id: str, ws: Path) -> dict:
    """异步启动 pytest 子进程。

    Popen pytest tests/，engine 下个 tick 用 check_pytest_async() 检查。

    Returns: {"ok": True, "pid": int}
             {"error": str}
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 判断是否有 tests/ 目录
    tests_dir = ws / "tests"
    if not tests_dir.is_dir():
        return {"error": "no tests/ directory, skipping pytest"}

    # 构建 pytest 命令
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]

    # 清理残留标记
    for sfx in [".pytest.done", ".pytest.exitcode", ".pytest.out", ".pytest.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError as exc:
            _log.debug("[tester] pytest marker unlink %s: %s", f, exc)

    # Popen pytest
    result_file = pids_dir / f"{task_id}.pytest.out"
    exitcode_file = pids_dir / f"{task_id}.pytest.exitcode"

    try:
        with open(result_file, "w") as out_f:
            proc = subprocess.Popen(
                cmd,
                stdout=out_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=ws,
                env=_sanitized_env(),
            )
        pids_dir.joinpath(f"{task_id}.pytest.pid").write_text(str(proc.pid))
        _log.info("[pytest-async] %s launched PID=%d", task_id, proc.pid)
        return {"ok": True, "pid": proc.pid}
    except Exception as exc:
        _log.error("[pytest-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def check_pytest_async(task_id: str, ws: Path) -> dict:
    """检查异步 pytest 是否完成。

    Returns:
        {"status": "pass"} — pytest 通过
        {"status": "failed", "exit_code": int, "output": str} — pytest 失败
        {"status": "running"} — 仍在执行
        {"status": "skipped", "reason": str} — 无 tests/ 目录
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.pytest.done"
    exitcode_file = pids_dir / f"{task_id}.pytest.exitcode"
    result_file = pids_dir / f"{task_id}.pytest.out"
    pid_file = pids_dir / f"{task_id}.pytest.pid"

    # 判断是否有 tests/ 目录（launch 时返回的错误，check 时检查）
    tests_dir = ws / "tests"
    if not tests_dir.is_dir():
        return {"status": "skipped", "reason": "no tests/ directory"}

    is_done = done_file.exists() or exitcode_file.exists()

    if not is_done:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running"}
            except (ValueError, ProcessLookupError) as exc:
                _log.debug("[tester] pid probe parse/lost %s: %s", pid_file, exc)
            except OSError as exc:
                _log.debug("[tester] pid probe OSError %s: %s", pid_file, exc)
        return {"status": "failed", "exit_code": -1, "output": "process exited"}

    if exitcode_file.exists():
        try:
            exit_code = int(exitcode_file.read_text().strip())
        except (ValueError, OSError):
            exit_code = -1
    else:
        exit_code = 0

    output = result_file.read_text() if result_file.exists() else ""

    # 清理标记
    _cleanup_pytest_markers(pids_dir, task_id)

    if exit_code == 0:
        return {"status": "pass"}
    return {"status": "failed", "exit_code": exit_code, "output": output[:2000]}


def _cleanup_pytest_markers(pids_dir: Path, task_id: str) -> None:
    """清理 pytest async 标记文件"""
    for sfx in [".pytest.done", ".pytest.exitcode", ".pytest.out", ".pytest.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError as exc:
            _log.debug("[tester] pytest marker unlink %s: %s", f, exc)


def _tester_verdict_allows_verified(task_id: str) -> bool:
    """缺 verdict 或非 PASS → 不得 verified（对齐红线 11 / engine gate）。"""
    try:
        vf = get_workspace() / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
        if not vf.is_file():
            _log.warning("[tester] %s skip verified — missing verdict", task_id)
            return False
        st = None
        for line in vf.read_text(encoding="utf-8", errors="replace").splitlines():
            low = line.strip().lower()
            if low.startswith("**verdict:**") or low.startswith("verdict:"):
                raw = line.split(":", 1)[1].strip().strip("*").strip()
                st = raw.split()[0].upper() if raw else None
                break
        if st == "PASS":
            return True
        _log.warning(
            "[tester] %s skip verified — verdict=%s",
            task_id,
            st or "unparsed",
        )
        return False
    except Exception as exc:
        _log.debug("[tester] verdict guard: %s", exc)
        return False


def tester_role() -> dict:
    """测试工程师: 扫 testing → 按 plan 跑验证 → 通过则挪 verified"""
    from _role_lock import assert_role_executor

    assert_role_executor("tester", "pytest")
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        plan_file = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
        verify_commands = []
        if plan_file.exists():
            content = plan_file.read_text()
            in_verify = False
            for line in content.split("\n"):
                if line.startswith("## 验收") or line.startswith("## 验证"):
                    in_verify = True
                    continue
                if in_verify and line.startswith("## "):
                    break
                if (
                    in_verify
                    and line.strip().startswith("- ")
                    and not line.strip().startswith("- 不")
                ):
                    cmd = line.strip()[2:].strip()
                    verify_commands.append(cmd)

        # fallback: 如果没有验收项，跑 pytest（卫生卡除外）
        verify_commands, skip_forced = build_tester_verify_commands(
            get_workspace(),
            task_id,
            plan_commands=verify_commands,
            task_meta=task,
        )
        if not verify_commands:
            if skip_forced:
                _log.info(
                    "[tester] %s ops/ccc-hygiene — 无白名单 cmd，视为通过",
                    task_id,
                )
                # 仍要求 PASS verdict（缺 verdict 不得 verified）
                if not _tester_verdict_allows_verified(task_id):
                    continue
                if move_task(task_id, "testing", "verified"):
                    moved.append(task_id)
                continue
            _log.warning("[tester] %s: no allowlisted cmds, skip", task_id)
            continue

        all_ok = True
        for cmd in verify_commands:
            if not all_ok:
                break
            # DRY_RUN=true python3 … 不能 shlex.split 当 argv[0]；走 shell 与 intent_probe 一致
            r = sp.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=cfg.exec_timeout,
                cwd=get_workspace(),
            )
            if r.returncode != 0:
                all_ok = False
                _out = (
                    r.stdout[-300:]
                    if isinstance(r.stdout, str)
                    else (
                        r.stdout.decode("utf-8", errors="replace")[-300:]
                        if r.stdout
                        else ""
                    )
                )
                _log.error(
                    "[tester] %s FAIL: %s... → %s",
                    task_id,
                    cmd[:80],
                    _out,
                )
                # R1: 验收失败 → fail pack + planned（勿晾在 testing）
                try:
                    from _failure_learning import (
                        align_phases_after_revert,
                        needs_plan_repair,
                        read_review_fail_pack,
                        repair_work_plan,
                        write_acceptance_fail_pack,
                    )

                    ws = get_workspace()
                    write_acceptance_fail_pack(
                        ws, task_id, cmd=cmd, output=_out or ""
                    )
                    fail_n = int(task.get("review_fail_loops") or 0) + 1
                    try:
                        from _board_store import FileBoardStore

                        FileBoardStore(ws).patch_task(
                            task_id, {"review_fail_loops": fail_n}
                        )
                    except Exception as exc:
                        _log.debug("[tester] patch_task fail_loops %s: %s", task_id, exc)
                    if fail_n >= 3:
                        try:
                            from engine.gates import _revert_task_commit
                        except Exception:
                            _revert_task_commit = None  # type: ignore
                        if _revert_task_commit:
                            try:
                                _revert_task_commit(ws, task_id)
                            except Exception as exc:
                                _log.warning(
                                    "[tester] %s revert on R3: %s", task_id, exc
                                )
                        _quarantine(
                            task_id,
                            f"tester_fail_loop_exhausted ({fail_n})",
                        )
                        _log.info(
                            "[tester] %s acceptance fail loops=%s → abnormal",
                            task_id,
                            fail_n,
                        )
                        break
                    pack = read_review_fail_pack(ws, task_id)
                    if needs_plan_repair(fail_loops=fail_n, fail_pack_text=pack):
                        repair_work_plan(
                            ws, task_id, fail_loops=fail_n, use_llm=False
                        )
                    try:
                        from engine.gates import _revert_task_commit

                        _revert_task_commit(ws, task_id)
                    except Exception as exc:
                        _log.warning("[tester] %s revert: %s", task_id, exc)
                    align_phases_after_revert(ws, task_id)
                    move_task(task_id, "testing", "planned")
                    _log.info(
                        "[tester] %s acceptance fail → planned (loops=%s)",
                        task_id,
                        fail_n,
                    )
                except Exception as exc:
                    _log.warning("[tester] %s fail→planned err: %s", task_id, exc)
                break

        if all_ok:
            if not _tester_verdict_allows_verified(task_id):
                continue
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            _log.info("[tester] %s ✓（验证 {len(verify_commands)} 项）", task_id)
    return {"role": "tester", "moved": moved, "counts": update_index()}

