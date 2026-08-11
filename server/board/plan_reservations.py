"""方案链编号保留表（2026-08-12 · 出卡/校验单一事实源）。

从 ``docs/projects/<prefix>/plans/*.md`` 的「关联卡：」行提取已规划的卡编号，
供出卡（new-card.sh 自动编号跳过）与校验（validate.py 一致性检查）共用，
消除「分配与校验两套语义」导致的生成后删除空转。

权威来源：方案文档（项目仓内白名单可信），非向量检索。
"""

from __future__ import annotations

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_CARD_ID_RE = re.compile(r"([a-z]{2,4}\d{3})")


def plan_reserved_ids(
    projects_dir: Path | str | None = None,
) -> dict[str, set[int]]:
    """扫描方案文档「关联卡」行，返回 {prefix: {被保留的三位序号}}。

    - 只认「关联卡：」行（中文冒号），与历史方案格式一致；
    - 解析失败/文件损坏按跳过处理，不抛异常（方案保护宁可放行不可误杀出卡）。
    """
    root = Path(projects_dir) if projects_dir else _PROJECT_ROOT / "docs" / "projects"
    out: dict[str, set[int]] = {}
    if not root.is_dir():
        return out
    for p in root.glob("**/plans/*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if "关联卡：" not in line:
                continue
            for cid in _CARD_ID_RE.findall(line.lower()):
                m = re.fullmatch(r"([a-z]{2,4})(\d{3})", cid)
                if not m:
                    continue
                pref, num = m.groups()
                out.setdefault(pref, set()).add(int(num))
    return out


def plan_reserved_card_titles() -> dict[str, str]:
    """返回 {card_id: 方案标题}，供校验报错时定位占用来源。"""
    root = _PROJECT_ROOT / "docs" / "projects"
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in root.glob("**/plans/*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        title_match = re.search(r"^#\s*方案\s*·\s*(.+)$", text, re.M)
        plan_title = title_match.group(1).strip() if title_match else p.stem
        for line in text.splitlines():
            if "关联卡：" not in line:
                continue
            for cid in _CARD_ID_RE.findall(line.lower()):
                m = re.fullmatch(r"([a-z]{2,4})(\d{3})", cid)
                if m:
                    out.setdefault(cid, plan_title)
    return out


def next_free_card_id(prefix: str, taken: set[int], max_num: int = 999) -> int | None:
    """从 1 起找第一个未被占用、未被方案保留的编号；找不到返回 None。

    ``taken``：已存在的卡编号（同前缀现有文件 + origin/main 已有卡）。
    """
    reserved = plan_reserved_ids().get(prefix, set())
    for n in range(1, max_num + 1):
        if n in taken or n in reserved:
            continue
        return n
    return None
