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
    verify_commands: list[str] = []
    if plan_file.exists():
        verify_commands = extract_probe_commands(
            plan_file.read_text(encoding="utf-8", errors="replace")
        )
    # fallback: 没有验收项，跑 pytest（卫生卡除外）
    skip_forced = False
    try:
        from _ccc_hygiene import task_skips_forced_pytest
        from _board_store import FileBoardStore

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
        except Exception:
            task_meta = None
        skip_forced = task_skips_forced_pytest(ws, task_id, task_meta)
    except Exception as exc:
        _log.warning("[tester] hygiene probe: %s", exc)

    if not verify_commands and not skip_forced:
        verify_commands = [
            f"python3 -m pytest {ws / 'tests' / 'scripts'} -q --tb=line --timeout=60"
        ]

    # 强制 baseline（业务卡）；ops/卫生 / .ccc-only 不追加全仓 pytest
    has_pyproject = (ws / "pyproject.toml").exists()
    if (
        has_pyproject
        and not skip_forced
        and not any("pytest" in c for c in verify_commands)
    ):
        verify_commands.append(
            "python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
        )

    verify_commands = _filter_verify_commands(verify_commands)
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
        except OSError:
            pass

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
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
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
        except OSError:
            pass


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
        except OSError:
            pass

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
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
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
        except OSError:
            pass


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
        skip_forced = False
        try:
            from _ccc_hygiene import task_skips_forced_pytest

            skip_forced = task_skips_forced_pytest(
                get_workspace(), task_id, task
            )
        except Exception as exc:
            _log.warning("[tester] hygiene probe: %s", exc)

        if not verify_commands and not skip_forced:
            verify_commands = [
                f"python3 -m pytest {get_workspace() / 'tests' / 'scripts'} -q --tb=line --timeout=60"
            ]

        # 强制 baseline（v0.21.3）：业务卡；ops/卫生不追加
        has_pyproject = (get_workspace() / "pyproject.toml").exists()
        if (
            has_pyproject
            and not skip_forced
            and not any("pytest" in c for c in verify_commands)
        ):
            verify_commands.append(
                "python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
            )

        verify_commands = _filter_verify_commands(verify_commands)
        if not verify_commands:
            if skip_forced:
                _log.info(
                    "[tester] %s ops/ccc-hygiene — 无白名单 cmd，视为通过",
                    task_id,
                )
                if move_task(task_id, "testing", "verified"):
                    moved.append(task_id)
                continue
            _log.warning("[tester] %s: no allowlisted cmds, skip", task_id)
            continue

        all_ok = True
        for cmd in verify_commands:
            if not all_ok:
                break
            r = sp.run(
                shlex.split(cmd),
                shell=False,
                capture_output=True,
                text=True,
                timeout=cfg.exec_timeout,
                cwd=get_workspace(),
            )
            if r.returncode != 0:
                all_ok = False
                _out = r.stdout[-300:] if isinstance(r.stdout, str) else r.stdout.decode("utf-8", errors="replace")[-300:] if r.stdout else ""
                _log.error(
                    "[tester] %s FAIL: %s... → %s",
                    task_id,
                    cmd[:80],
                    _out,
                )

        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            _log.info("[tester] %s ✓（验证 {len(verify_commands)} 项）", task_id)
    return {"role": "tester", "moved": moved, "counts": update_index()}

