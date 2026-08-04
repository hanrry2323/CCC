"""任务卡卡头校验器（2026-08-04 新增，填补「文件即事实源但无机器校验」缺口）。

扫描 ``docs/dispatch/*.md``，逐卡校验：

- 卡头 ``>`` 元数据行必含：关联 / 执行体 / 状态 / 日期；
- 状态值必须是五态之一（待分派 / 执行中 / 已回写 / 已关闭 / 打回）；
- 非「待分派」状态必须存在回写区（``## 回写区`` 且含执行体行）；
- 卡文件必须存在 ``## 目标`` 与 ``## 验收标准`` 节（格式最低要求）。

用法::

    $PYTHON_BIN -m server.board.validate [dispatch_dir]

返回码：0 = 全部通过；1 = 存在问题（逐条列出）。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from server.board.models import base_state

VALID_STATES = frozenset({"待分派", "执行中", "已回写", "已关闭", "打回"})
REQUIRED_HEADER_KEYS = ("关联", "执行体", "状态", "日期")


@dataclass
class CardIssue:
    """单张卡的一个问题。"""

    card_id: str
    path: str
    reason: str


def _header_lines(card: Path) -> list[str]:
    """取卡头全部 ``>`` 元数据行（与 loader 同款：多行合并解析）。"""
    return [
        ln.strip()
        for ln in card.read_text(encoding="utf-8").splitlines()
        if ln.strip().startswith(">")
    ]


def _header_metadata(card: Path) -> dict[str, str]:
    """用 loader 同款解析合并全部 ``>`` 行 → ``key: value`` 字典。

    历史卡把 关联/执行体/状态/日期 分布在多个 ``>`` 行，只查首行会误报；
    与 `server/board/loader._parse_metadata` 一致语义合并解析。
    """
    from server.board.loader import _parse_metadata  # noqa: PLC0415

    meta: dict[str, str] = {}
    for line in _header_lines(card):
        meta.update(_parse_metadata(line))
    return meta


def _body_has(card: Path, marker: str) -> bool:
    text = card.read_text(encoding="utf-8")
    return marker in text


def _card_number(path: Path) -> str:
    """取文件名数字编号（``T<N>-...`` → ``N``；``T90-test`` → ``90``）。"""
    m = re.match(r"T(\d+)", path.name)
    return m.group(1) if m else ""


def _header_card_id(card: Path) -> str:
    """取卡头 ``# 任务卡 T<N>[-slug]`` 的 ID（停在 ``·`` 或空白处）；未匹配返回空。

    历史卡两种写法并存：``# 任务卡 T1-server-skeleton``（含 slug）与
    ``# 任务卡 T52 · 自动化基建``（仅编号），统一取 ``T<N>`` 前缀即可。
    """
    m = re.search(r"#\s*任务卡\s+(T[^\s·]+)", card.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def _header_number(card: Path) -> str:
    """取卡头 ID 的数字部分（``T52`` / ``T1-server-skeleton`` → ``52`` / ``1``）。"""
    m = re.match(r"T(\d+)", _header_card_id(card))
    return m.group(1) if m else ""


def validate_cards(dispatch_dir: str | Path) -> list[CardIssue]:
    """校验目录下全部任务卡，返回问题清单（空 = 全通过）。

    T52 增强（出卡门禁）：
    - 编号一致性：卡头 ``# 任务卡 T<N>`` 的数字前缀与文件名 ``T<N>-...`` 必须一致
      （防止文件改名/复制后卡头编号错乱）；
    - 编号唯一：卡头 ID 重复（同编号两张卡，如复制卡只改文件名不改卡头）报重。
    注：R/X 变体卡（``T1`` 与 ``T1-R-...``）数字前缀允许共存，按卡头 ID 判重。
    """
    issues: list[CardIssue] = []
    d = Path(dispatch_dir)
    if not d.is_dir():
        return [CardIssue("?", str(d), "目录不存在")]
    cards = sorted(d.glob("T*.md"))

    # 编号唯一：卡头 ID 重复报重（R/X 变体卡卡头 ID 不同，不误伤）
    by_hdr_id: dict[str, list[Path]] = {}
    for card in cards:
        hdr_id = _header_card_id(card)
        if hdr_id:
            by_hdr_id.setdefault(hdr_id, []).append(card)
    for hdr_id, dupes in by_hdr_id.items():
        if len(dupes) > 1:
            for card in dupes[1:]:
                issues.append(
                    CardIssue(card.stem, str(card), f"编号 {hdr_id} 重复（与 {dupes[0].name} 冲突，编号必须唯一）")
                )

    for card in cards:
        card_id = card.name.split(".")[0]
        # 编号一致性：卡头数字前缀 == 文件名数字前缀
        hdr_num = _header_number(card)
        file_num = _card_number(card)
        if hdr_num and file_num and hdr_num != file_num:
            issues.append(
                CardIssue(card_id, str(card), f"卡头编号 T{hdr_num} 与文件名 T{file_num} 不一致")
            )
        meta = _header_metadata(card)
        if not meta:
            issues.append(CardIssue(card_id, str(card), "缺少卡头元数据行（> 且含 key：value）"))
            continue
        missing = [k for k in REQUIRED_HEADER_KEYS if not meta.get(k, "").strip()]
        if missing:
            issues.append(CardIssue(card_id, str(card), f"卡头缺字段: {missing}"))
        state_raw = meta.get("状态", "")
        base = base_state(state_raw)
        if base not in VALID_STATES:
            issues.append(CardIssue(card_id, str(card), f"状态值非法: {state_raw!r}（合法={sorted(VALID_STATES)}）"))
        if base in ("已回写", "已关闭", "打回") and not _body_has(card, "## 回写区"):
            issues.append(CardIssue(card_id, str(card), f"状态 {base} 但缺少 ## 回写区"))
        if not _body_has(card, "## 目标"):
            issues.append(CardIssue(card_id, str(card), "缺少 ## 目标"))
        if not _body_has(card, "## 验收标准"):
            issues.append(CardIssue(card_id, str(card), "缺少 ## 验收标准"))
    return issues


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    target = argv[0] if argv else "docs/dispatch"
    issues = validate_cards(target)
    if not issues:
        print(f"卡头校验通过：{target}（{len(list(Path(target).glob('T*.md')))} 张卡）")
        return 0
    print(f"卡头校验发现 {len(issues)} 个问题：")
    for it in issues:
        print(f"  [{it.card_id}] {it.path}: {it.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
