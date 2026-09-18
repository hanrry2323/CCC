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

    锚定语义（2026-09-08 修复多层互斥 + 2026-09-19 F11 节序无关）：
    - 替换「回写区」时，节边界硬锚定到 `## 维护区`：回写内容自身含
      `## 0.` 等三级标题，若按 `\n## ` 边界截断会把旧层追加在新正文前，
      累积出互相否定的多层，被机审作为「新旧两层互斥」打回。此硬锚
      只服务「自身正文含子标题」的节——回写区是唯一特例。
    - 替换其他节（维护区/批注落实/人工批注）时，end 锚定到「下一个相邻
      `\n## ` 边界」而非写死的 `## 机审区`：卡节序偏离规范（如 xy079 维护区
      在回写区之前）时，写死锚点会越过中间节把回写区/批注一并吞掉，
      card-validate 以「状态已回写但缺 ## 回写区」拒提交 → 代写失败死循环。
      节序无关后，无论目标节之后紧邻哪一节都能正确切片。
    - 找不到相邻节边界时回退文件尾（兼容缺尾节/旧卡）。
    """
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return text.rstrip() + f"\n\n{marker}\n\n{body.strip()}\n"
    content_start = start + len(marker)
    end = content_start
    if heading == "回写区":
        anchor = "\n## 维护区"
        a = text.find(anchor, content_start)
        if a != -1:
            end = a
        else:
            # 回写区之后无维护区（xy079 非规范序：维护区在回写区之前）→ 跳过回写区
            # 自身正文的子标题（## 0./1./2.…），锚到下一个非数字二级节（机审区等）。
            # 若仍跳过数字子标题，则回退到真正的相邻 `\n## ` 边界。
            next_match = re.search(r"\n## (?!0\.|1\.|2\.|3\.|4\.|5\.)", text[content_start:])
            end = content_start + (next_match.start() if next_match else len(text[content_start:]))
    if end == content_start:
        # 通用节（维护区/批注落实/人工批注）：下一个 `\n## ` 边界（节序无关；
        # 对规范序卡即维护区→机审区，等价旧行为）。普通节正文不含数字子标题。
        next_match = re.search(r"\n## ", text[content_start:])
        end = content_start + (next_match.start() if next_match else len(text[content_start:]))
    return text[:content_start] + "\n\n" + body.strip() + "\n" + text[end:]
