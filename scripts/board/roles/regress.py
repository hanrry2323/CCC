"""board.roles.regress — extracted from ccc-board.py (behavior-preserving)."""
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

def regress_role() -> dict:
    """回测工程师: 每日扫 released → py_compile + git diff → 发现回归→建 bug"""
    from _role_lock import assert_role_executor

    assert_role_executor("regress", "pytest")
    import subprocess as sp
    from datetime import date

    results = {"checked": 0, "passed": 0, "failed": 0, "regressions": []}
    tasks = list_tasks("released")
    if not tasks:
        return {"role": "regress", "info": "无已发布任务", "results": results}

    today = date.today().isoformat()
    scripts_dir = get_workspace() / "scripts"
    # v0.28.0 (N-004): scripts_dir 不存在时 rglob 返回空（不抛错）→ py_ok=True 假阳性。
    # 显式检查目录存在，缺失则降级：跳过 py_compile 标记 unknown，循环内按 unknown 处理。
    py_files: list[Path] = []
    py_check_available = False
    if scripts_dir.is_dir():
        py_files = list(scripts_dir.rglob("*.py"))
        py_check_available = True
    else:
        _log.warning(
            "regress: scripts_dir 不存在 (%s) — 跳过 py_compile 检查",
            scripts_dir,
        )

    # v0.28.0 (M-004): py_compile 是项目级检查，所有 .py 文件语法问题与 task 无关。
    # 提到循环外，只跑一次，结果在循环内复用。
    py_ok = True
    failed_py: list[Path] = []
    for py in py_files:
        r = sp.run(
            ["python3", "-m", "py_compile", str(py)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            py_ok = False
            failed_py.append(py)
    if not py_ok:
        _log.warning(
            "regress: 项目级 py_compile 失败 %d 个文件: %s",
            len(failed_py),
            [p.name for p in failed_py[:5]],
        )

    for task in tasks:
        tid = task["id"]
        results["checked"] += 1

        # 1. py_compile — 复用上面的项目级结果
        # v0.28.0 (N-004): scripts_dir 不存在时 py_check_available=False，
        # 跳过 py_compile 检查（task_py_ok=True 不归咎 task，但记 skipped_py_check）。
        task_py_ok = py_ok
        if not py_check_available:
            results.setdefault("skipped_py_check", 0)
            results["skipped_py_check"] += 1

        # 2. git diff 检查是否代码被意外改过
        diff_ok = True
        r = sp.run(
            ["git", "diff", "HEAD", "--stat"],
            cwd=get_workspace(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.stdout.strip():
            diff_ok = False

        if task_py_ok and diff_ok:
            results["passed"] += 1
            _log.info("[regress] ✓ %s", tid)
        else:
            results["failed"] += 1
            today_compact = date.today().strftime("%Y%m%d")
            bug_id = f"regression-{tid}-{today_compact}-{results['failed']}"
            bug_title = f"回归: {task.get('title', tid)} ({today})"
            bug_desc = f"原任务 {tid} 在 {today} 回测失败\n"
            if not task_py_ok:
                bug_desc += "- py_compile 失败：代码有语法错误\n"
            if not diff_ok:
                bug_desc += "- git diff 非空：代码有意外改动\n"
            create_task({"id": bug_id, "title": bug_title, "description": bug_desc})
            results["regressions"].append(bug_id)
            _log.info("[regress] ✗ %s → %s", tid, bug_id)
            # 把原任务移回 backlog 并加 regression 标签
            src_path = board_dir() / "released" / f"{tid}.jsonl"
            if src_path.exists():
                _lines = src_path.read_text().split("\n")
                for _i, _line in enumerate(_lines):
                    _ls = _line.strip()
                    if not _ls:
                        continue
                    try:
                        _obj = json.loads(_ls)
                        _tags = _obj.get("tags", [])
                        if "regression" not in _tags:
                            _tags.append("regression")
                        _obj["tags"] = _tags
                        _obj["updated_at"] = now_iso()
                        _lines[_i] = json.dumps(_obj, ensure_ascii=False)
                        break
                    except json.JSONDecodeError as e:
                        _log.warning(
                            "regress tag update JSON failed for %s: %s", tid, e
                        )
            move_task(tid, "released", "backlog")
            # macOS 桌面通知
            subprocess.run(
                [
                    "bash",
                    str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                    "L2",
                    bug_title,
                    bug_desc[:200],
                ],
                capture_output=True,
                timeout=10,
                env=_sanitized_env(),
            )

    # 写回测日报
    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"regression-{today}.md"
    report.write_text(
        f"# 回测日报 {today}\n\n"
        f"- 检查任务: {results['checked']}\n"
        f"- 通过: {results['passed']}\n"
        f"- 失败: {results['failed']}\n"
        f"- 新建回归 bug: {len(results['regressions'])}\n"
    )
    return {"role": "regress", "results": results, "report": str(report)}

