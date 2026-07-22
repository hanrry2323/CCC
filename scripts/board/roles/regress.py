"""board.roles.regress — released → replay intent probes → regression epic.

LPSN · P: authority requires replaying ## 验收 probes (not only py_compile/diff).
"""
# TODO F4-1: migrate to build_role_context
from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from _executor import _sanitized_env
from _intent_probe import extract_probe_commands, run_probes
from board.context import get_workspace, board_dir
from board.roles.common import (
    _log,
    CCC_HOME,
    now_iso,
    list_tasks,
    move_task,
    create_task,
)


def _load_acceptance_for_task(ws: Path, tid: str) -> str:
    from _acceptance_gate import load_acceptance_text

    return load_acceptance_text(ws, tid)


def regress_role() -> dict:
    """回测工程师: 扫 released → 重放意图探针 (+ 辅检) → 失败建回归 epic。"""
    from _role_lock import assert_role_executor

    assert_role_executor("regress", "pytest")
    import subprocess as sp

    results: dict[str, Any] = {
        "checked": 0,
        "passed": 0,
        "failed": 0,
        "regressions": [],
        "probe_runs": 0,
        "skipped_no_probe": 0,
    }
    tasks = list_tasks("released")
    if not tasks:
        return {"role": "regress", "info": "无已发布任务", "results": results}

    today = date.today().isoformat()
    ws = get_workspace()
    scripts_dir = ws / "scripts"
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

        task_py_ok = py_ok
        if not py_check_available:
            results.setdefault("skipped_py_check", 0)
            results["skipped_py_check"] += 1

        # Primary: replay ## 验收 intent probes
        section = _load_acceptance_for_task(ws, tid)
        probes = extract_probe_commands(section)
        probe_ok = True
        probe_ran: list[dict[str, Any]] = []
        if probes:
            results["probe_runs"] += 1
            probe_ok, probe_ran = run_probes(ws, probes, timeout=120)
        else:
            results["skipped_no_probe"] += 1
            _log.info("[regress] %s no allowlisted probes — aux checks only", tid)

        # Aux: unexpected dirty tree
        diff_ok = True
        r = sp.run(
            ["git", "diff", "HEAD", "--stat"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.stdout.strip():
            diff_ok = False

        # Fail when probes fail, or (no probes and) compile/diff fail
        if probes:
            passed = probe_ok and task_py_ok
        else:
            passed = task_py_ok and diff_ok

        if passed:
            results["passed"] += 1
            _log.info("[regress] ✓ %s", tid)
            continue

        results["failed"] += 1
        today_compact = date.today().strftime("%Y%m%d")
        bug_id = f"regression-{tid}-{today_compact}-{results['failed']}"
        bug_title = f"回归: {task.get('title', tid)} ({today})"
        bug_desc = f"原任务 {tid} 在 {today} 回测失败\n\n## 验收\n"
        if probes:
            for pr in probe_ran:
                mark = "OK" if pr.get("ok") else "FAIL"
                bug_desc += f"- [{mark}] `{pr.get('cmd')}` rc={pr.get('rc')}\n"
                if pr.get("error"):
                    bug_desc += f"  error: {pr['error'][:200]}\n"
            bug_desc += (
                "\n```bash\n"
                + "\n".join(probes[:8])
                + "\n```\n"
            )
        if not task_py_ok:
            bug_desc += "- py_compile 失败：代码有语法错误\n"
        if not probes and not diff_ok:
            bug_desc += "- git diff 非空：代码有意外改动\n"
        create_task(
            {
                "id": bug_id,
                "title": bug_title,
                "description": bug_desc,
                "card_kind": "epic",
                "tags": ["regression", "lpsn-p"],
            }
        )
        results["regressions"].append(bug_id)
        _log.info("[regress] ✗ %s → %s", tid, bug_id)
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
            src_path.write_text("\n".join(_lines) + ("\n" if _lines else ""))
        move_task(tid, "released", "backlog")
        try:
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
        except (OSError, subprocess.TimeoutExpired):
            pass

    report_dir = ws / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"regression-{today}.md"
    report.write_text(
        f"# 回测日报 {today}\n\n"
        f"- 检查任务: {results['checked']}\n"
        f"- 通过: {results['passed']}\n"
        f"- 失败: {results['failed']}\n"
        f"- 探针回放: {results['probe_runs']}\n"
        f"- 无探针辅检: {results['skipped_no_probe']}\n"
        f"- 新建回归 bug: {len(results['regressions'])}\n",
        encoding="utf-8",
    )
    return {"role": "regress", "results": results, "report": str(report)}
