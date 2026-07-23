"""OpenCode 质量门 — 挡住 exit_code=0 的空心/假 PASS。

根因（2026-07-19 实锤）：
OpenCode 拒读 ``~/.ccc/*``（external_directory auto-reject）后仍 exit 0；
dev 门禁又给 report 补写 ``ALL SELF-CHECKS PASSED`` → 假 PASS 进 testing。
"""

from __future__ import annotations

import re

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
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
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
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return report_has_self_checks_passed(blob)
