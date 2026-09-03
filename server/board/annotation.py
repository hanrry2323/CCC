"""人工批注统一解析（P1：validate 与 observer 共用一处，消除 sentinel 漂移）。

契约：
- ``classify_annotation(text)`` 返回 ``NONE`` 或 ``REAL``。
  ``NONE``：无 ``## 人工批注`` 节 / 节内容为空 / 模板占位句 /
  「无」/「无批注」/「（无批注。）」等明确无批注意义表达。
  其余任何内容视为 ``REAL``（老板写了真实修订指示）。
- ``requires_fulfillment(text)``：卡含真实批注且不含 ``## 批注落实`` 段。
"""

from __future__ import annotations

import re

# 明确「无批注」的 sentinel：内容去掉空白后命中任一即 NONE
_NONE_ANNOTATION_MARKERS = {
    "无",
    "无批注",
    "（无批注。）",
    "无批注。",
    "暂无批注",
    "老板对打回卡/审核的批注意见写这里",  # 模板占位句
    "（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）",
}

_ANNOTATION_HEADING_RE = re.compile(r"^##\s*人工批注\s*$", flags=re.MULTILINE)
_FULFILLMENT_HEADING_RE = re.compile(r"^##\s*批注落实\s*$", flags=re.MULTILINE)


def _extract_annotation_content(text: str) -> str:
    """提取 ``## 人工批注`` 节到下一个 ``##`` 主节的内容（保留 strip 后原文）。"""
    m = _ANNOTATION_HEADING_RE.search(text)
    if not m:
        return ""
    tail = text[m.end() :]
    nxt = re.search(r"^##\s", tail, flags=re.MULTILINE)
    return (tail[: nxt.start()] if nxt else tail).strip()


def classify_annotation(text: str) -> str:
    """返回 ``NONE``（无真实人工批注）或 ``REAL``（有真实人工批注）。"""
    content = _extract_annotation_content(text)
    if not content:
        return "NONE"
    compact = "".join(content.split())
    if compact in _NONE_ANNOTATION_MARKERS:
        return "NONE"
    if any(marker in content for marker in ("老板对打回卡/审核的批注意见写这里", "无批注时保留本节即可")):
        return "NONE"
    return "REAL"


def requires_fulfillment(text: str) -> bool:
    """卡含真实人工批注、且未带非空「## 批注落实」段 → 需落实。"""
    if classify_annotation(text) != "REAL":
        return False
    m = _FULFILLMENT_HEADING_RE.search(text)
    if not m:
        return True
    tail = text[m.end() :]
    nxt = re.search(r"^##\s", tail, flags=re.MULTILINE)
    content = (tail[: nxt.start()] if nxt else tail).strip()
    return not content


__all__ = ["classify_annotation", "requires_fulfillment"]
