"""server/engine/result_contract.py — A1/A2 结果契约纯工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import re

def _executor_result_path(log_dir: Path, work_id: str) -> Path:
    """A1 执行结果文件路径（由 wrapper 从 worktree 传入 log_dir）。"""
    return log_dir / f"{work_id}-ccc-result.md"

def _executor_result_json_path(log_dir: Path, work_id: str) -> Path:
    """P1.3：结构化执行结果 sidecar 路径（优先于 markdown 兼容链）。"""
    return log_dir / f"{work_id}-ccc-result.json"

def _executor_result_required_headings() -> tuple[str, ...]:
    return ("## 0. 卡标题复述", "## 1. 探针输出", "## 2. 自测输出", "## 3. 维护区四问")

def _blocking_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """severity 阈值门：仅 P0/P1 阻断打回；P2 仅留档（与 phase2 侧口径一致）。"""
    return [f for f in findings if f.get("severity") in {"P0", "P1"}]

def _replace_card_section(text: str, heading: str, body: str) -> str:
    """替换卡内一个二级节的正文，保留节标题。

    锚定语义（2026-09-08 修复多层互斥）：
    - 替换「回写区」时，节边界锚定到 `## 维护区`（回写内容自身含 `## 0.` 等
      三级标题，若按 `\n## ` 截断会把旧层追加在后面，累积出互相否定的多层，
      被机审作为「新旧两层互斥」打回）。
    - 替换「维护区」时锚定到 `## 机审区`。
    - 找不到指定锚点时回退 `\n## ` 边界（兼容旧卡/缺尾节）。
    """
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return text.rstrip() + f"\n\n{marker}\n\n{body.strip()}\n"
    content_start = start + len(marker)
    end = content_start
    if heading == "回写区":
        anchor = "\n## 维护区"
    elif heading == "维护区":
        anchor = "\n## 机审区"
    else:
        anchor = None
    if anchor:
        a = text.find(anchor, content_start)
        if a != -1:
            end = a
    if end == content_start:
        next_match = re.search(r"\n## ", text[content_start:])
        end = content_start + (next_match.start() if next_match else len(text[content_start:]))
    return text[:content_start] + "\n\n" + body.strip() + "\n" + text[end:]
