"""Derive a structured executor-result sidecar from the markdown contract."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def _section(text: str, start: str, end: str | None = None) -> str:
    marker = f"## {start}"
    if marker not in text:
        raise ValueError(f"missing {marker}")
    body = text.split(marker, 1)[1]
    if end is not None:
        body = body.split(f"## {end}", 1)[0]
    return body.strip()


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


_MAINT_NAMES = {1: "方案同步", 2: "教训沉淀", 3: "档案/README", 4: "线路图"}


def _maintenance_value(text: str, number: int, name: str) -> tuple[str, str]:
    match = re.search(
        rf"(?im)^\s*{number}\.\s+(?:\*\*)?{re.escape(name)}(?:\*\*)?：\s*\[([^]]+)\](.*)$",
        text,
    )
    if match:
        choice = match.group(1).strip()
        note = match.group(2).strip()
        return choice, note
    # 顺序兜底（2026-09-10 xy065 实证）：执行体可能抄四问的问题原文（行内无标准键名）。
    # 维护区四问语义按序——段内按出现顺序收集含 [选择] 的条目行，第 N 条即第 N 问。
    seq: list[tuple[str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or not re.search(r"\[([^\]]+)\]", s):
            continue
        if s.startswith("|") and set(s) <= {"|", "-", ":", " "}:
            continue  # 表格分隔行
        if not (s.startswith(("|", "-", "*", "•")) or re.match(r"^\d{1,2}[.、]", s) or re.match(r"^[①②③④]", s)):
            continue
        cm = re.search(r"\[([^\]]+)\]", s)
        if not cm:
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            note = cells[-1] if len(cells) >= 3 else ""
        elif "：" in s:
            note = s.split("：", 1)[1].strip()
        else:
            note = ""
        seq.append((cm.group(1).strip(), note))
    if len(seq) >= number:
        return seq[number - 1]
    raise ValueError(f"missing maintenance item {number}")


def _exit_code(name: str, text: str) -> int | None:
    patterns = (
        rf"(?im)^[^\n]*\b{name}\b[^\n]*(?:exit|rc|退出码)\s*[:=]\s*(-?\d+)",
        rf"(?im)^[^\n]*\b{name}\b[^\n]*\b(-?\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _evidence(text: str) -> dict[str, Any]:
    commits = re.findall(r"(?im)\bcommit\s*=\s*([0-9a-f]{7,40})\b", text)
    match = re.search(r"(?im)^diff[_ ]stat\s*[:=]\s*(.+)$", text)
    diff_stat = match.group(1).strip() if match else ""
    if not diff_stat:
        try:
            diff_stat = subprocess.run(
                ["git", "diff", "--stat", "HEAD^", "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            ).stdout.strip()
        except OSError:
            diff_stat = ""
    return {"commits": commits, "diff_stat": diff_stat}


def _annotation_fulfillment(text: str) -> str:
    """提取 `## 人工批注落实` 或 `## 批注落实` 段正文；无则空串。"""
    for heading in ("## 人工批注落实", "## 批注落实"):
        if heading in text:
            body = text.split(heading, 1)[1]
            for nxt in ("## 1. 探针输出", "## 2. 自测输出", "## 3. 维护区四问", "## 4. 变更证据"):
                if nxt in body:
                    body = body.split(nxt, 1)[0]
                    break
            return body.strip()
    return ""


def parse_result(text: str, work_id: str) -> dict[str, Any]:
    """Parse all required markdown sections; raise when the contract is incomplete."""
    title = _section(text, "0. 卡标题复述", "1. 探针输出")
    probe = _section(text, "1. 探针输出", "2. 自测输出")
    selftest = _section(text, "2. 自测输出", "3. 维护区四问")
    maintenance_text = _section(text, "3. 维护区四问", "4. 变更证据")
    plan_sync, plan_note = _maintenance_value(maintenance_text, 1, "方案同步")
    lesson, lesson_note = _maintenance_value(maintenance_text, 2, "教训沉淀")
    readme, readme_note = _maintenance_value(maintenance_text, 3, "档案/README")
    roadmap, roadmap_note = _maintenance_value(maintenance_text, 4, "线路图")
    evidence = _evidence(_section(text, "4. 变更证据"))
    return {
        "work_id": work_id,
        "card_title": _first_line(title),
        "probe_output": probe,
        "selftest_output": selftest,
        "exit_codes": {
            "test": _exit_code("test", selftest),
            "compile": _exit_code("compile", selftest),
            "lint": _exit_code("lint", selftest),
        },
        "maintenance": {
            "plan_sync": plan_sync,
            "lesson": lesson,
            "readme": readme,
            "roadmap": roadmap,
        },
        "maintenance_notes": {
            "plan_sync": plan_note,
            "lesson": lesson_note,
            "readme": readme_note,
            "roadmap": roadmap_note,
        },
        "annotation_fulfillment": _annotation_fulfillment(text),
        "evidence": evidence,
    }


def convert_file(source: str | Path, destination: str | Path, work_id: str) -> None:
    text = Path(source).read_text(encoding="utf-8", errors="replace")
    payload = parse_result(text, work_id)
    Path(destination).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
