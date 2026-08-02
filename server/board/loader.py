"""从任务卡文档解析看板派生数据（任务卡 = 唯一事实源）。

- 元数据块（`>` 行，`key：value` 以 `·` 分隔）→ 状态 / 项目 / 执行体 / 分派时间。
- 回写区（`## 回写区` 后 `**日期**：`）→ 回写时间。
- 字段缺失容错：标「未知」不崩溃；无显式打回次数按 0。

用法：
    from server.board.loader import parse_card, load_dispatch_cards

    item = parse_card("docs/dispatch/T2-engine-core.md")
    items = load_dispatch_cards("docs/dispatch")
"""

from __future__ import annotations

import re
from pathlib import Path

from server.board.models import UNKNOWN, BoardItem, base_state

# `# 任务卡 T3 · 标题`（MULTILINE：^/$ 按行锚定）
_TITLE_RE = re.compile(r"^#\s*任务卡\s+(\S+)\s*[·\-]\s*(.+?)\s*$", re.MULTILINE)
# 元数据行内的 `key：value`（`>` 行，`·` 分隔）
_META_PAIR_RE = re.compile(r"^\s*([^：\s][^：]*?)\s*[:：]\s*(.+?)\s*$")
# 回写区日期：`**日期**：YYYY-MM-DD`
_WRITTEN_RE = re.compile(r"\*\*日期\*\*\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
# 显式打回次数：`打回次数：N`
_REJECT_RE = re.compile(r"打回次数\s*[:：]\s*(\d+)")

# 元数据键 → BoardItem 字段
_META_TO_FIELD: dict[str, str] = {
    "关联": "project",
    "执行体": "executor",
    "状态": "state",
    "日期": "dispatched_at",
}


def _strip_parenthetical(value: str) -> str:
    """取括号前部分（如 `INT-120（CCC 重构）` → `INT-120`）。"""
    return re.split(r"[（(]", value, maxsplit=1)[0].strip()


def _parse_metadata(text: str) -> dict[str, str]:
    """解析 `>` 元数据行的 `key：value` 对。"""
    meta: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(">"):
            continue
        body = line.lstrip(">").strip()
        for part in re.split(r"·", body):
            match = _META_PAIR_RE.match(part)
            if match:
                meta[match.group(1).strip()] = match.group(2).strip()
    return meta


def _parse_written_at(text: str) -> str:
    """从回写区取 `**日期**：YYYY-MM-DD`。"""
    match = _WRITTEN_RE.search(text)
    return match.group(1) if match else UNKNOWN


def parse_card(path: Path | str) -> BoardItem:
    """解析单张任务卡；字段缺失容错标「未知」。"""
    text = Path(path).read_text(encoding="utf-8")

    title_match = _TITLE_RE.search(text)
    if title_match:
        card_id, title = title_match.group(1), title_match.group(2).strip()
    else:
        card_id, title = Path(path).stem, UNKNOWN

    meta = _parse_metadata(text)

    reject_match = _REJECT_RE.search(text)
    reject_count = int(reject_match.group(1)) if reject_match else 0
    # 状态为「打回」（含括号变体如 `打回（原因）`）时隐含至少 1 次打回
    if reject_count == 0 and base_state(meta.get("状态", UNKNOWN)) == "打回":
        reject_count = 1

    return BoardItem(
        id=card_id,
        title=title,
        state=meta.get("状态", UNKNOWN),
        project=_strip_parenthetical(meta.get("关联", UNKNOWN)),
        executor=_strip_parenthetical(meta.get("执行体", UNKNOWN)),
        dispatched_at=meta.get("日期", UNKNOWN),
        written_at=_parse_written_at(text),
        reject_count=reject_count,
    )


def load_dispatch_cards(directory: Path | str) -> list[BoardItem]:
    """扫描目录下全部任务卡；单张失败跳过不崩。"""
    items: list[BoardItem] = []
    for path in sorted(Path(directory).glob("*.md")):
        try:
            items.append(parse_card(path))
        except OSError:
            continue
    return items
