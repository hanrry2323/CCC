"""Acceptance gate for salvage / enter-testing — 跑完 ≠ 做对。

读取 work plan → parent epic plan → epic description 的 ## 验收。
有可执行命令则跑白名单命令；否则核对交付路径是否落在 task commit。
契约：docs/product/loop-engineer-authority.md · 验收关门
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.acceptance_gate")

# Align with tester allowlist (subset safe for gate subprocess)
_VERIFY_CMD_ALLOW_PREFIXES = (
    "python3 -m pytest",
    "python -m pytest",
    "pytest ",
    "python3 -m py_compile",
    "python -m py_compile",
    "python3 -m ruff",
    "ruff check",
    "ruff format",
    "bash -n ",
    "swift build",
    "npm test",
    "npm run test",
    "cargo test",
    "go test",
    "test -",
    "ls ",
    "test !",
)

_PATH_IN_TEXT = re.compile(
    r"(?:`([^`]+)`|(?:^|\s)(\.ccc/[^\s,;]+|[A-Za-z0-9_.\-]+/[^\s,;]+\.(?:jsonl|md|json|py|swift|ts|tsx|js)))"
)

# 排除/禁止语境：整条验收 bullet 不抽 path（否则「勿入 warnings.json」会变成必碰 commit 路径）
_EXCLUDE_PATH_BULLET = re.compile(
    r"(显式排除|排除|勿入|不入|禁止入|禁止\s*add|不得入|不要入|勿\s*add|"
    r"exclude|do\s*not\s+add|never\s+add|must\s+not\s+(?:add|commit))",
    re.IGNORECASE,
)


def _is_allowed_verify_cmd(cmd: str) -> bool:
    c = (cmd or "").strip()
    if not c or "\n" in c or "\r" in c:
        return False
    for bad in (";", "&&", "||", "`", "$(", "${", ">", "<", "|"):
        if bad in c:
            return False
    low = c.lower()
    return any(low.startswith(p.lower()) for p in _VERIFY_CMD_ALLOW_PREFIXES)


def _filter_verify_commands(cmds: list[str]) -> list[str]:
    return [c.strip() for c in cmds if _is_allowed_verify_cmd(c)]


def _extract_acceptance_section(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    out: list[str] = []
    in_sec = False
    for line in lines:
        if line.startswith("## 验收") or line.startswith("## 验证"):
            in_sec = True
            continue
        if in_sec and line.startswith("## "):
            break
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


def _bullets_and_cmds(section: str) -> tuple[list[str], list[str]]:
    bullets: list[str] = []
    cmds: list[str] = []
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("```"):
            continue
        if s.startswith("- ") and not s.startswith("- 不"):
            item = s[2:].strip()
            bullets.append(item)
            # fenced-less command-looking lines
            if _is_allowed_verify_cmd(item):
                cmds.append(item)
        # bare command in section
        elif _is_allowed_verify_cmd(s):
            cmds.append(s)
    # also extract from ```bash blocks in original section
    in_code = False
    code_lang = ""
    for line in section.splitlines():
        if line.strip().startswith("```"):
            fence = line.strip()
            if not in_code:
                in_code = True
                code_lang = fence[3:].strip().lower()
            else:
                in_code = False
                code_lang = ""
            continue
        if in_code and (not code_lang or code_lang in ("bash", "sh", "shell", "")):
            if _is_allowed_verify_cmd(line.strip()):
                cmds.append(line.strip())
    return bullets, _filter_verify_commands(cmds)


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
        sec = _extract_acceptance_section(work_plan.read_text(encoding="utf-8", errors="replace"))
        if sec:
            return sec
    task = _load_task(ws, tid) or {}
    parent = str(task.get("parent_id") or "").strip()
    if parent:
        parent_plan = plans / f"{parent}.plan.md"
        if parent_plan.is_file():
            sec = _extract_acceptance_section(
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
                sec = _extract_acceptance_section(desc)
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
    ran: list[dict[str, Any]] = []
    for cmd in cmds[:12]:
        try:
            r = subprocess.run(
                cmd,
                cwd=ws,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            ran.append(
                {
                    "cmd": cmd,
                    "rc": r.returncode,
                    "ok": r.returncode == 0,
                }
            )
            if r.returncode != 0:
                return False, ran
        except (OSError, subprocess.TimeoutExpired) as exc:
            ran.append({"cmd": cmd, "rc": -1, "ok": False, "error": str(exc)[:120]})
            return False, ran
    return True, ran


def check_acceptance(
    ws: Path,
    tid: str,
    *,
    commit: str = "",
) -> dict[str, Any]:
    """Return {ok, reason, ran, bullets, cmds}.

    ok=False when: no acceptance text; commands fail; or file-only acceptance
    with no matching paths in commit.
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
            return {
                "ok": False,
                "reason": "acceptance_cmd_failed",
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
        # prose-only acceptance: require a task commit exists (caller ensures)
        if commit:
            return {
                "ok": True,
                "reason": "acceptance_prose_with_commit",
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
