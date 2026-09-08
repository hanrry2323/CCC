"""Single-source parser for audit verdict artifacts.

JSON is the current contract. Markdown remains a compatibility fallback for
older auditor wrappers; neither parser ever infers PASS from malformed input.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

VALID_VERDICTS = {"PASS", "REJECT"}
VALID_SEVERITIES = {"P0", "P1", "P2"}
PROTOCOL_JSON_REASON = "protocol：JSON verdict 缺失或非法"
PROTOCOL_MISSING_REASON = "protocol：无 verdict 工件"


def _invalid(reason: str = PROTOCOL_JSON_REASON) -> tuple[str, str, list[dict[str, Any]]]:
    return "REJECT", reason, []


def parse_json_verdict(raw: str | bytes | bytearray) -> tuple[str, str, list[dict[str, Any]]]:
    """Parse and validate one JSON verdict; invalid input is fail-closed REJECT."""
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).decode("utf-8")
        if isinstance(raw, str) and raw != raw.lstrip():
            return _invalid()
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return _invalid()
    if not isinstance(value, dict):
        return _invalid()
    verdict = value.get("verdict")
    reason = value.get("reason")
    findings = value.get("findings")
    if verdict not in VALID_VERDICTS or not isinstance(reason, str) or not reason.strip():
        return _invalid()
    if not isinstance(findings, list):
        return _invalid()
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            return _invalid()
        if not all(key in finding for key in ("id", "severity", "file", "line", "note")):
            return _invalid()
        if (
            not isinstance(finding["id"], str)
            or not finding["id"].strip()
            or finding["severity"] not in VALID_SEVERITIES
            or not isinstance(finding["file"], str)
            or not isinstance(finding["line"], int)
            or isinstance(finding["line"], bool)
            or finding["line"] < 0
            or not isinstance(finding["note"], str)
        ):
            return _invalid()
        normalized.append(
            {
                "id": finding["id"],
                "severity": finding["severity"],
                "file": finding["file"],
                "line": finding["line"],
                "note": finding["note"],
            }
        )
    return verdict, reason.strip(), normalized


def parse_markdown_verdict(raw: str | bytes | bytearray) -> tuple[str, str, list[dict[str, Any]]]:
    """Parse the legacy single-line markdown verdict format."""
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).decode("utf-8", errors="replace")
    except (UnicodeDecodeError, TypeError):
        return _invalid(PROTOCOL_MISSING_REASON)
    for line in str(raw).splitlines():
        line = line.strip()
        match = re.match(r"^机审：通过(?:\s*（([^）]*)）)?\s*$", line)
        if match:
            return "PASS", match.group(1) or "", []
        match = re.match(r"^机审：不通过(?:\s*（([^\n）]*)）)?\s*$", line)
        if match:
            return "REJECT", match.group(1) or "", []
    return _invalid(PROTOCOL_MISSING_REASON)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_verdict(log_dir: str | Path, work_id: str) -> tuple[str | None, str, list[dict[str, Any]]]:
    """Read JSON first, then legacy markdown, with fail-closed semantics."""
    directory = Path(log_dir)
    json_path = directory / f"{work_id}-audit-verdict.json"
    markdown_path = directory / f"{work_id}-audit-verdict.md"
    json_text = _read(json_path)
    if json_text is not None:
        parsed = parse_json_verdict(json_text)
        if parsed[0] == "PASS" or parsed[0] == "REJECT" and parsed[1] != PROTOCOL_JSON_REASON:
            return parsed
        markdown_text = _read(markdown_path)
        if markdown_text is not None:
            fallback = parse_markdown_verdict(markdown_text)
            if fallback[1] != PROTOCOL_MISSING_REASON:
                return fallback
        return parsed
    markdown_text = _read(markdown_path)
    if markdown_text is not None:
        parsed = parse_markdown_verdict(markdown_text)
        if parsed[1] != PROTOCOL_MISSING_REASON:
            return parsed
    return None, PROTOCOL_MISSING_REASON, []


