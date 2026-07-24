"""Intent probes — shared parse / allowlist / run for LPSN · P.

Authority: docs/product/loop-engineer-authority.md · 上线 ≠ 开发完成
Used by: acceptance gate, tester, regress, transfer_gate, phase_lint.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.intent_probe")

# Base command prefixes after stripping leading KEY=VAL assignments.
VERIFY_CMD_ALLOW_PREFIXES = (
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
    # Intent-probe shapes (authority LPSN · P)
    ".venv/bin/python",
    "python3 ",
    "python ",
)

_ENV_ASSIGN_RE = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)+")
_SHELL_META = (";", "&&", "||", "`", "$(", "${", ">", "<", "|")

HYGIENE_PIPELINES = frozenset({"ops", "hygiene", "board", "board_ops"})
HYGIENE_TITLE_MARKERS = (
    "看板卫生",
    "board hygiene",
    "归档产物",
    "回收 abnormal",
    "清空 abnormal",
    "对齐版本",
    "readme stamp",
    "flow-smoke",
)


def strip_env_prefix(cmd: str) -> tuple[str, str]:
    """Return (env_prefix_including_trailing_space_or_empty, remainder)."""
    c = (cmd or "").strip()
    m = _ENV_ASSIGN_RE.match(c)
    if not m:
        return "", c
    return m.group(0), c[m.end() :].strip()


def is_allowed_verify_cmd(cmd: str) -> bool:
    c = (cmd or "").strip()
    if not c or "\n" in c or "\r" in c:
        return False
    for bad in _SHELL_META:
        if bad in c:
            return False
    _, rem = strip_env_prefix(c)
    if not rem:
        return False
    low = rem.lower()
    return any(low.startswith(p.lower()) for p in VERIFY_CMD_ALLOW_PREFIXES)


def filter_verify_commands(cmds: list[str]) -> list[str]:
    return [c.strip() for c in cmds if is_allowed_verify_cmd(c)]


def extract_acceptance_section(text: str) -> str:
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


# bullet / numbered acceptance lines: "- cmd" · "1. cmd" · "1) cmd"
_LIST_ITEM_RE = re.compile(r"^(?:[-*]|\d+[.)])\s+")
# CJK + fullwidth punct — marks acceptance prose after a real command
_TRAILING_PROSE_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")


def _candidates_from_list_item(item: str) -> list[str]:
    """Allowlisted cmd from a list item; strip trailing Chinese / fullwidth prose."""
    item = (item or "").strip()
    if not item or item.startswith("不"):
        return []
    out: list[str] = []

    def _clean(cmd: str) -> str | None:
        cmd = (cmd or "").strip()
        if not cmd or not is_allowed_verify_cmd(cmd):
            return None
        # 验收常写「cmd 退出码 0…」；整行仍可能通过 allowlist，执行时必炸
        if _TRAILING_PROSE_RE.search(cmd):
            tokens = cmd.split()
            for i in range(len(tokens), 0, -1):
                cand = " ".join(tokens[:i])
                if is_allowed_verify_cmd(cand) and not _TRAILING_PROSE_RE.search(cand):
                    return cand
            return None
        return cmd

    if "`" in item:
        for m in re.finditer(r"`([^`]+)`", item):
            cleaned = _clean(m.group(1).strip())
            if cleaned:
                out.append(cleaned)
    cleaned = _clean(item)
    if cleaned:
        out.append(cleaned)
    elif not out:
        tokens = item.split()
        for i in range(len(tokens), 0, -1):
            cleaned = _clean(" ".join(tokens[:i]))
            if cleaned:
                out.append(cleaned)
                break
    return out


def extract_probe_commands(section_or_plan: str) -> list[str]:
    """Pull allowlisted commands from an acceptance section or full plan."""
    section = section_or_plan or ""
    if "## 验收" in section or "## 验证" in section:
        extracted = extract_acceptance_section(section)
        if extracted:
            section = extracted
    cmds: list[str] = []
    in_code = False
    code_lang = ""
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("```"):
            fence = s
            if not in_code:
                in_code = True
                code_lang = fence[3:].strip().lower()
            else:
                in_code = False
                code_lang = ""
            continue
        if in_code and (not code_lang or code_lang in ("bash", "sh", "shell", "")):
            cmds.extend(_candidates_from_list_item(s))
            continue
        m = _LIST_ITEM_RE.match(s)
        if m:
            cmds.extend(_candidates_from_list_item(s[m.end() :].strip()))
        else:
            cmds.extend(_candidates_from_list_item(s))
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return filter_verify_commands(out)


def looks_like_intent_probe(cmd: str) -> bool:
    """True if command matches authority intent-probe shape (not only pytest)."""
    c = (cmd or "").strip()
    if not is_allowed_verify_cmd(c):
        return False
    env, rem = strip_env_prefix(c)
    low = rem.lower()
    if env and ("DRY_RUN" in env.upper() or "dry_run" in env.lower()):
        return True
    if low.startswith(".venv/bin/python"):
        return True
    if "dry_run" in c.lower():
        return True
    # plain python3 script / -m module (not only pytest/py_compile/ruff)
    if low.startswith("python3 ") or low.startswith("python "):
        if any(
            tok in low
            for tok in ("-m pytest", "pytest", "-m py_compile", "-m ruff", "ruff ")
        ):
            return False
        return True
    return False


def extract_intent_probes(section_or_plan: str) -> list[str]:
    """Allowlisted cmds that look like product intent probes."""
    return [c for c in extract_probe_commands(section_or_plan) if looks_like_intent_probe(c)]


def has_replayable_intent_probe(text: str) -> bool:
    return bool(extract_intent_probes(text) or extract_probe_commands(text))


def is_hygiene_transfer(body: dict[str, Any] | None = None, *, blob: str = "") -> bool:
    body = body or {}
    pipeline = str(body.get("pipeline") or "").strip().lower()
    title = str(body.get("title") or "").strip().lower()
    goal = str(body.get("goal") or "").strip().lower()
    combined = blob or f"{pipeline} {title} {goal}"
    if pipeline in HYGIENE_PIPELINES:
        return True
    return any(k in combined for k in HYGIENE_TITLE_MARKERS)


# Hang / timeout signals from acceptance probes (stress hang cards, SIGALRM, wall timeout).
_HANG_TEXT_MARKERS = (
    "hang_detected",
    "hang detected",
    "timed out",
    "timeoutexpired",
)


def is_hang_probe_failure(entry: dict[str, Any] | None) -> bool:
    """True when a probe run looks like hang/timeout (not ordinary assert fail).

    Signals: exit 124 (convention), wall TimeoutExpired, or HANG_DETECTED in output.
    """
    if not entry or entry.get("ok"):
        return False
    rc = entry.get("rc")
    try:
        if int(rc) == 124:
            return True
    except (TypeError, ValueError):
        pass
    blob = " ".join(
        str(entry.get(k) or "")
        for k in ("error", "stdout", "stderr", "detail")
    ).lower()
    return any(m in blob for m in _HANG_TEXT_MARKERS)


def ran_has_hang(ran: list[dict[str, Any]] | None) -> bool:
    return any(is_hang_probe_failure(e) for e in (ran or []))


def run_probes(
    ws: Path,
    cmds: list[str],
    *,
    timeout: int = 120,
    max_cmds: int = 12,
) -> tuple[bool, list[dict[str, Any]]]:
    """Execute allowlisted probe cmds; stop on first failure."""
    ws = Path(ws)
    ran: list[dict[str, Any]] = []
    for cmd in cmds[:max_cmds]:
        if not is_allowed_verify_cmd(cmd):
            ran.append({"cmd": cmd, "rc": -1, "ok": False, "error": "not_allowlisted"})
            return False, ran
        try:
            r = subprocess.run(
                cmd,
                cwd=ws,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            entry = {
                "cmd": cmd,
                "rc": r.returncode,
                "ok": r.returncode == 0,
            }
            # Keep tails for hang classification even on success (cheap).
            out_tail = (r.stdout or "")[-400:]
            err_tail = (r.stderr or "")[-400:]
            if out_tail:
                entry["stdout"] = out_tail
            if err_tail:
                entry["stderr"] = err_tail
            if r.returncode != 0:
                err = (err_tail + out_tail)[-400:]
                if err:
                    entry["error"] = err
            ran.append(entry)
            if r.returncode != 0:
                return False, ran
        except subprocess.TimeoutExpired as exc:
            # Align with GNU timeout / stress SIGALRM convention: 124
            out_tail = ""
            err_tail = ""
            try:
                if getattr(exc, "stdout", None):
                    out_tail = (
                        exc.stdout.decode("utf-8", errors="replace")
                        if isinstance(exc.stdout, (bytes, bytearray))
                        else str(exc.stdout)
                    )[-400:]
                if getattr(exc, "stderr", None):
                    err_tail = (
                        exc.stderr.decode("utf-8", errors="replace")
                        if isinstance(exc.stderr, (bytes, bytearray))
                        else str(exc.stderr)
                    )[-400:]
            except Exception:
                pass
            entry: dict[str, Any] = {
                "cmd": cmd,
                "rc": 124,
                "ok": False,
                "error": f"TimeoutExpired:{timeout}s {str(exc)[:120]}",
                "detail": "hang_detected wall_timeout",
            }
            if out_tail:
                entry["stdout"] = out_tail
            if err_tail:
                entry["stderr"] = err_tail
            ran.append(entry)
            return False, ran
        except OSError as exc:
            ran.append({"cmd": cmd, "rc": -1, "ok": False, "error": str(exc)[:200]})
            return False, ran
    return True, ran


def require_intent_probe_text(text: str, *, hygiene: bool = False) -> tuple[bool, str]:
    """Gate helper: business work needs ≥1 allowlisted probe command."""
    if hygiene:
        return True, "hygiene_skip"
    cmds = extract_probe_commands(text)
    if cmds:
        return True, "ok"
    return False, "missing_intent_probe"
