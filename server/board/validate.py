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


def _header_line(card: Path) -> str:
    """取卡头 ``>`` 元数据行（首个以 ``>`` 开头且含「状态」的行）。"""
    for line in card.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(">") and "状态" in stripped:
            return stripped
    return ""


def _body_has(card: Path, marker: str) -> bool:
    text = card.read_text(encoding="utf-8")
    return marker in text


def validate_cards(dispatch_dir: str | Path) -> list[CardIssue]:
    """校验目录下全部任务卡，返回问题清单（空 = 全通过）。"""
    issues: list[CardIssue] = []
    d = Path(dispatch_dir)
    if not d.is_dir():
        return [CardIssue("?", str(d), "目录不存在")]
    for card in sorted(d.glob("T*.md")):
        header = _header_line(card)
        card_id = card.name.split(".")[0]
        if not header:
            issues.append(CardIssue(card_id, str(card), "缺少卡头元数据行（> 且含「状态」）"))
            continue
        missing = [k for k in REQUIRED_HEADER_KEYS if f"{k}：" not in header and f"{k}:" not in header]
        if missing:
            issues.append(CardIssue(card_id, str(card), f"卡头缺字段: {missing}"))
        state_raw = ""
        for seg in header.split("·"):
            seg = seg.strip()
            if seg.startswith("状态：") or seg.startswith("状态:"):
                state_raw = seg.split("：", 1)[-1].split(":", 1)[-1].strip()
                break
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
