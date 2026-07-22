"""Defensive parse for ``.ccc/reports/<tid>.result.json``.

OpenCode / runner historically mixed stdout logs into result.json.
Prefer pure JSON; if polluted, extract first/last JSON object.
"""

from __future__ import annotations

import json
import re
from typing import Any

_OBJ_RE = re.compile(r"\{[\s\S]*\}")


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """Parse raw text as JSON object; tolerate leading/trailing noise.

    Strategy:
    1. Strip → json.loads whole
    2. Last ``{...}`` brace-balanced slice
    3. First ``{...}`` brace-balanced slice
    """
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    for candidate in (_last_balanced_object(text), _first_balanced_object(text)):
        if candidate is None:
            continue
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _first_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    return _balanced_from(text, start)


def _last_balanced_object(text: str) -> str | None:
    # Prefer the last top-level object (runner often appends final JSON)
    for i in range(len(text) - 1, -1, -1):
        if text[i] == "{":
            got = _balanced_from(text, i)
            if got is not None:
                return got
    return None


def _balanced_from(text: str, start: int) -> str | None:
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(text)):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def parse_result_file(path_or_text: str | Any, *, raw: str | None = None) -> tuple[dict[str, Any], bool]:
    """Return (obj, dirty).

    dirty=True when whole-file json.loads failed and recovery extracted an object.
    """
    if raw is None:
        from pathlib import Path

        p = Path(path_or_text)
        if not p.is_file():
            return {}, False
        raw = p.read_text(encoding="utf-8", errors="replace")
    text = raw or ""
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict):
            return obj, False
    except json.JSONDecodeError:
        pass
    recovered = extract_json_object(text)
    if recovered is not None:
        return recovered, True
    return {}, True
