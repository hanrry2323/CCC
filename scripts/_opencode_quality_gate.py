"""OpenCode 质量门 — 挡住 exit_code=0 的空心/假 PASS。

根因（2026-07-19 实锤）：
OpenCode 拒读 ``~/.ccc/*``（external_directory auto-reject）后仍 exit 0；
dev 门禁又给 report 补写 ``ALL SELF-CHECKS PASSED`` → 假 PASS 进 testing。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_log = logging.getLogger("ccc.opencode_quality_gate")

# 权限拒读 / 越界目录（home 控制面、编排仓外）
_HOLLOW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"permission requested:\s*external_directory",
        re.IGNORECASE,
    ),
    re.compile(r"external_directory[^\n]{0,120}auto-rejecting", re.IGNORECASE),
    re.compile(r"auto-rejecting[^\n]{0,80}external_directory", re.IGNORECASE),
    re.compile(r"the user rejected permission", re.IGNORECASE),
    re.compile(r"rejected permission[^\n]{0,80}external_directory", re.IGNORECASE),
)

# 误读 home 控制面（相对工作区 .ccc 才是合法路径）
_HOME_CCC_READ = re.compile(
    r"(?:Read|read|Error|error|failed)[^\n]{0,40}"
    r"/(?:Users|home)/[^/\s]+/\.ccc/",
    re.IGNORECASE,
)


def _stdout_blob_from_result(result_raw: str) -> str:
    """Prefer current-run stdout from result.json; fall back to raw string."""
    blob = result_raw or ""
    if not blob.strip():
        return ""
    try:
        import json

        data = json.loads(blob)
        if isinstance(data, dict):
            path = str(data.get("path") or "").strip().lower()
            if path in ("script_seed", "board_ops", "python"):
                return ""  # short paths: hollow N/A (caller should skip)
            parts: list[str] = []
            for key in ("stdout", "stderr", "output", "message"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    parts.append(val)
            if parts:
                return "\n".join(parts)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        _log.debug("opencode_quality_gate extract_notes: %s", e)
    return blob


def detect_hollow_opencode_run(
    result_raw: str,
    report: str = "",
    *,
    path: str | None = None,
) -> str | None:
    """若运行日志显示空心成功，返回失败原因；否则 None。

    即使 report 已含 ``ALL SELF-CHECKS PASSED``，有拒读证据仍判空心
    （禁止用假 PASS 盖过工具失败）。

    适型（v0.60.2+）：
    - ``path`` 为 script_seed/board_ops/python → 不跑 hollow（确定性短路径）
    - 优先只扫 result 的 stdout（本 phase），避免历史 report 误伤文档 phase
    - result 无 stdout 时才回退拼接 report
    """
    p = (path or "").strip().lower()
    if not p:
        try:
            import json

            data = json.loads(result_raw or "")
            if isinstance(data, dict):
                p = str(data.get("path") or "").strip().lower()
        except (json.JSONDecodeError, TypeError, ValueError):
            p = ""
    if p in ("script_seed", "board_ops", "python"):
        return None

    blob = _stdout_blob_from_result(result_raw)
    if not blob.strip():
        # 无本 phase stdout 时才看 report（兼容旧 result）
        blob = f"{result_raw or ''}\n{report or ''}"
    if not blob.strip():
        return None

    for pat in _HOLLOW_PATTERNS:
        if pat.search(blob):
            return (
                "opencode blocked on external_directory "
                "(often ~/.ccc or out-of-cwd); treat as failed — "
                "do not invent ALL SELF-CHECKS PASSED"
            )

    if _HOME_CCC_READ.search(blob) and (
        "error" in blob.lower() or "reject" in blob.lower() or "failed" in blob.lower()
    ):
        return (
            "opencode tried home ~/.ccc paths and failed; "
            "use <workspace>/.ccc/ only"
        )

    return None


def _norm_repo_path(p: str) -> str:
    return (p or "").strip().replace("\\", "/").lstrip("./")


def _scope_intersects_names(scope: list[str], names: list[str]) -> bool:
    scopes = [_norm_repo_path(s) for s in scope if _norm_repo_path(s)]
    files = [_norm_repo_path(n) for n in names if _norm_repo_path(n)]
    if not scopes or not files:
        return False
    for s in scopes:
        for n in files:
            if n == s or n.startswith(s.rstrip("/") + "/") or s.startswith(n.rstrip("/") + "/"):
                return True
            # directory scope
            if s.endswith("/") and n.startswith(s):
                return True
    return False


def _git_show_names(workspace: Path, commit: str) -> list[str]:
    import subprocess

    try:
        r = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", commit],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        _log.debug("hollow_phase git show: %s", e)
        return []
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]


def _git_diff_names(
    workspace: Path, baseline: str, head: str, scope: list[str]
) -> list[str]:
    import subprocess

    paths = [_norm_repo_path(s) for s in scope if _norm_repo_path(s)]
    cmd = ["git", "diff", "--name-only", f"{baseline}..{head}", "--", *paths]
    try:
        r = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        _log.debug("hollow_phase git diff: %s", e)
        return []
    if r.returncode != 0:
        return []
    return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]


def detect_hollow_phase_scope(
    workspace: Path,
    *,
    phase_num: int,
    scope: list[str],
    task_commit: str,
    phases: list[dict] | None = None,
) -> str | None:
    """Fail when phase>1 is marked done without touching its scope.

    Desktop R5 (2026-07-28): phase 2 reused phase 1 commit; ``test_*.py`` unchanged
    but phases.json still ``status=done``.
    """
    ws = Path(workspace)
    scope_n = [_norm_repo_path(s) for s in (scope or []) if _norm_repo_path(s)]
    if not scope_n or int(phase_num) <= 1:
        return None
    commit = (task_commit or "").strip()
    if not commit:
        return f"hollow phase {phase_num}: no task commit while scope={scope_n}"

    prev_commit = None
    for p in phases or []:
        if not isinstance(p, dict) or "schema_version" in p:
            continue
        try:
            pn = int(p.get("phase", -1))
        except (TypeError, ValueError):
            continue
        if pn >= int(phase_num):
            continue
        c = str(p.get("commit") or "").strip()
        if c:
            prev_commit = c

    names = _git_show_names(ws, commit)
    in_commit = _scope_intersects_names(scope_n, names)

    if prev_commit and prev_commit == commit:
        if not in_commit:
            return (
                f"hollow phase {phase_num}: reused commit {commit[:12]} "
                f"without touching scope {scope_n}"
            )
        return None

    if prev_commit:
        changed = _git_diff_names(ws, prev_commit, "HEAD", scope_n)
        if not changed:
            return (
                f"hollow phase {phase_num}: no scope changes since "
                f"{prev_commit[:12]} for {scope_n}"
            )
        return None

    if not in_commit:
        return (
            f"hollow phase {phase_num}: commit {commit[:12]} "
            f"does not touch scope {scope_n}"
        )
    return None


def report_has_self_checks_passed(report: str) -> bool:
    return "ALL SELF-CHECKS PASSED" in (report or "")


def agent_declared_self_checks_passed(report: str = "", result_raw: str = "") -> bool:
    """True if agent already wrote the literal marker (report.md and/or result stdout).

    Not inventing: OpenCode often puts the line in chat stdout (``.result.json``)
    instead of writing ``.report.md``. Gate must accept either; still forbids
    synthesizing the marker when absent from both.
    """
    if report_has_self_checks_passed(report):
        return True
    blob = result_raw or ""
    # Prefer stdout field when result is JSON; fall back to raw blob.
    try:
        import json

        data = json.loads(blob)
        if isinstance(data, dict):
            for key in ("stdout", "output", "message"):
                val = data.get(key)
                if isinstance(val, str) and report_has_self_checks_passed(val):
                    return True
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        _log.debug("opencode_quality_gate result parse: %s", e)
    return report_has_self_checks_passed(blob)
