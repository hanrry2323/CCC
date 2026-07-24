"""Acceptance gate for salvage / enter-testing — 跑完 ≠ 做对。

读取 work plan → parent epic plan → epic description 的 ## 验收。
有可执行命令则跑白名单命令；否则核对交付路径是否落在 task commit。
契约：docs/product/loop-engineer-authority.md · 验收关门 · LPSN · P
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from _intent_probe import (
    extract_acceptance_section,
    extract_probe_commands,
    filter_verify_commands,
    is_allowed_verify_cmd,
    run_probes,
)

_log = logging.getLogger("ccc.acceptance_gate")

# Re-export for tests / callers that imported private helpers
_VERIFY_CMD_ALLOW_PREFIXES = None  # legacy; use _intent_probe.VERIFY_CMD_ALLOW_PREFIXES
_is_allowed_verify_cmd = is_allowed_verify_cmd
_filter_verify_commands = filter_verify_commands
_extract_acceptance_section = extract_acceptance_section


_PATH_IN_TEXT = re.compile(
    r"(?:`([^`]+)`|(?:^|\s)(\.ccc/[^\s,;]+|[A-Za-z0-9_.\-]+/[^\s,;]+\.(?:jsonl|md|json|py|swift|ts|tsx|js)))"
)

# 排除/禁止语境：整条验收 bullet 不抽 path（否则「勿入 warnings.json」会变成必碰 commit 路径）
_EXCLUDE_PATH_BULLET = re.compile(
    r"(显式排除|排除|勿入|不入|禁止入|禁止\s*add|不得入|不要入|勿\s*add|"
    r"exclude|do\s*not\s+add|never\s+add|must\s+not\s+(?:add|commit))",
    re.IGNORECASE,
)


def _bullets_and_cmds(section: str) -> tuple[list[str], list[str]]:
    bullets: list[str] = []
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("```"):
            continue
        if s.startswith("- ") and not s.startswith("- 不"):
            bullets.append(s[2:].strip())
    cmds = extract_probe_commands(section)
    return bullets, cmds


def _paths_from_bullets(bullets: list[str]) -> list[str]:
    paths: list[str] = []
    for b in bullets:
        if _EXCLUDE_PATH_BULLET.search(b):
            continue
        for m in _PATH_IN_TEXT.finditer(b):
            p = (m.group(1) or m.group(2) or "").strip().strip("'\"")
            if p and not p.startswith("http"):
                while p.startswith("./"):
                    p = p[2:]
                paths.append(p)
    return paths


def _load_task(ws: Path, tid: str) -> dict[str, Any] | None:
    board = ws / ".ccc" / "board"
    for col in (
        "in_progress",
        "testing",
        "planned",
        "verified",
        "backlog",
        "released",
        "abnormal",
    ):
        p = board / col / f"{tid}.jsonl"
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError, IndexError):
            continue
    return None


def load_acceptance_text(ws: Path, tid: str) -> str:
    """Resolve acceptance prose: work plan → parent plan → epic description."""
    plans = ws / ".ccc" / "plans"
    work_plan = plans / f"{tid}.plan.md"
    if work_plan.is_file():
        sec = extract_acceptance_section(
            work_plan.read_text(encoding="utf-8", errors="replace")
        )
        if sec:
            return sec
    task = _load_task(ws, tid) or {}
    parent = str(task.get("parent_id") or "").strip()
    if parent:
        parent_plan = plans / f"{parent}.plan.md"
        if parent_plan.is_file():
            sec = extract_acceptance_section(
                parent_plan.read_text(encoding="utf-8", errors="replace")
            )
            if sec:
                return sec
        # epic description
        for col in ("backlog", "released", "planned"):
            ep = ws / ".ccc" / "board" / col / f"{parent}.jsonl"
            if not ep.is_file():
                continue
            try:
                data = json.loads(ep.read_text(encoding="utf-8").splitlines()[0])
                desc = str(data.get("description") or data.get("note") or "")
                sec = extract_acceptance_section(desc)
                if sec:
                    return sec
                if "## 验收" in desc or "验收" in desc[:400]:
                    return desc
            except (OSError, json.JSONDecodeError, IndexError):
                pass
    return ""


def _commit_touches_paths(ws: Path, commit: str, paths: list[str]) -> bool:
    if not commit or not paths:
        return False
    try:
        r = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", commit],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return False
        names = {
            (ln or "").strip().lstrip("./")
            for ln in (r.stdout or "").splitlines()
            if ln.strip()
        }
        for p in paths:
            pp = p.lstrip("./")
            if pp in names:
                return True
            # directory prefix
            if any(n == pp or n.startswith(pp.rstrip("/") + "/") for n in names):
                return True
        return False
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_cmds(ws: Path, cmds: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    return run_probes(ws, cmds)


def _allow_prose_acceptance(ws: Path, tid: str) -> bool:
    """业务卡禁止散文验收；仅 ops/卫生可 prose+commit。"""
    task = _load_task(ws, tid) or {}
    pipe = str(task.get("pipeline") or "").strip().lower()
    if pipe in ("ops", "hygiene", "board", "board_ops"):
        return True
    try:
        from _ccc_hygiene import task_skips_forced_pytest

        if task_skips_forced_pytest(ws, tid, task):
            return True
    except Exception:
        pass
    title = str(task.get("title") or "")
    if any(k in title for k in ("卫生", "清场", "看板卫生", "hygiene")):
        return True
    return False


def check_acceptance(
    ws: Path,
    tid: str,
    *,
    commit: str = "",
    allow_prose: bool | None = None,
) -> dict[str, Any]:
    """Return {ok, reason, ran, bullets, cmds}.

    ok=False when: no acceptance text; commands fail; or file-only acceptance
    with no matching paths in commit.

    业务卡（默认）：禁止 ``acceptance_prose_with_commit`` —— 必须有可执行命令
    或可核对路径。ops/卫生可通过 ``allow_prose=True`` 或自动判定保留散文门。
    """
    ws = Path(ws)
    section = load_acceptance_text(ws, tid)
    if not section.strip():
        return {
            "ok": False,
            "reason": "missing_acceptance",
            "ran": [],
            "bullets": [],
            "cmds": [],
        }
    bullets, cmds = _bullets_and_cmds(section)
    if cmds:
        ok, ran = _run_cmds(ws, cmds)
        if not ok:
            # KPI / reopen 口径：timeout·exit 124·HANG_DETECTED → hang_detected
            # （禁止只写 acceptance_cmd_failed 污染 abnormal 统计）
            from _intent_probe import ran_has_hang

            hang = ran_has_hang(ran)
            return {
                "ok": False,
                "reason": "hang_detected" if hang else "acceptance_cmd_failed",
                "ran": ran,
                "bullets": bullets,
                "cmds": cmds,
            }
        return {
            "ok": True,
            "reason": "acceptance_cmds_ok",
            "ran": ran,
            "bullets": bullets,
            "cmds": cmds,
        }
    paths = _paths_from_bullets(bullets)
    if paths and commit:
        if _commit_touches_paths(ws, commit, paths):
            return {
                "ok": True,
                "reason": "acceptance_paths_in_commit",
                "ran": [],
                "bullets": bullets,
                "cmds": [],
                "paths": paths,
            }
        return {
            "ok": False,
            "reason": "acceptance_paths_not_in_commit",
            "ran": [],
            "bullets": bullets,
            "cmds": [],
            "paths": paths,
        }
    if bullets:
        prose_ok = (
            allow_prose
            if allow_prose is not None
            else _allow_prose_acceptance(ws, tid)
        )
        if prose_ok and commit:
            return {
                "ok": True,
                "reason": "acceptance_prose_with_commit",
                "ran": [],
                "bullets": bullets,
                "cmds": [],
            }
        if not prose_ok:
            return {
                "ok": False,
                "reason": "acceptance_prose_forbidden_for_business",
                "ran": [],
                "bullets": bullets,
                "cmds": [],
            }
        return {
            "ok": False,
            "reason": "acceptance_prose_needs_commit",
            "ran": [],
            "bullets": bullets,
            "cmds": [],
        }
    return {
        "ok": False,
        "reason": "acceptance_empty_bullets",
        "ran": [],
        "bullets": [],
        "cmds": [],
    }
