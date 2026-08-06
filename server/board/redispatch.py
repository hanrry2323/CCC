"""打回卡人工重新分派（打回 → 待分派）。

人审入口：老板先在卡上 ``## 人工批注`` 写审核意见，再一键把卡放回「待分派」。

- 只允许「打回 → 待分派」；写纯「待分派」（不带 ``重试n`` 标记）→ 引擎重试计数归零。
- 保留 ``打回次数`` 字段与 ``## 人工批注`` 作历史，不越权删改正文。
- 原子写（tmp → rename）+ 失效后重建索引，与 ``engine.store.save_work`` 同款安全。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from server.board.loader import parse_card
from server.board.models import base_state
from server.engine.store import _replace_state_in_metadata

logger = logging.getLogger("ccc.board.redispatch")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DISPATCH_DIR = _PROJECT_ROOT / "docs" / "dispatch"


def redispatch_card(
    card_path: str | Path,
    dispatch_dir: str | Path | None = None,
) -> tuple[bool, str]:
    """将打回卡置回「待分派」，返回 (ok, message)。

    非打回态 → 拒绝（不越权改状态）；卡不存在 → 报错。
    """
    path = Path(card_path)
    if not path.is_file():
        return False, f"卡文件不存在: {path}"
    try:
        item = parse_card(path)
    except Exception as exc:
        return False, f"解析卡失败: {exc}"

    if base_state(item.state) != "打回":
        return False, f"{item.id} 当前状态「{item.state}」，仅「打回」卡可重新分派"

    text = path.read_text(encoding="utf-8")
    try:
        new_text = _replace_state_in_metadata(text, "待分派")
    except ValueError as exc:
        return False, f"卡头未找到「状态」段: {exc}"

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, path)

    if dispatch_dir:
        try:
            from server.board.loader import load_dispatch_cards

            load_dispatch_cards(Path(dispatch_dir))
        except Exception:
            logger.exception("重新分派后索引刷新失败（不影响卡已置待分派）")
    return True, f"{item.id} 打回 → 待分派（重试计数归零，打回次数与批注保留）"


def _find_card_file(dispatch_dir: Path, card_id: str) -> Path | None:
    """按卡 ID 找任务卡文件（与 web `_find_card_file` 同款宽容匹配）。"""
    candidates = sorted(dispatch_dir.glob(f"{card_id}-*.md"))
    if not candidates:
        candidates = sorted(dispatch_dir.glob(f"*/{card_id}-*.md"))
    if not candidates:
        candidates = sorted(dispatch_dir.glob(f"*{card_id}*.md"))
    return candidates[0] if candidates else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ccc-redispatch",
        description="打回卡一键重新分派（打回 → 待分派，重试计数归零）",
    )
    parser.add_argument("card", help="卡 ID（如 ccc042）或卡文件路径")
    parser.add_argument(
        "--dispatch-dir",
        default=str(_DEFAULT_DISPATCH_DIR),
        help="任务卡目录（默认 docs/dispatch）",
    )
    args = parser.parse_args(argv)

    dispatch_dir = Path(args.dispatch_dir)
    card_path = Path(args.card)
    if not card_path.is_file():
        found = _find_card_file(dispatch_dir, args.card)
        if found is None:
            print(f"[ERROR] 未找到卡: {args.card}", file=sys.stderr)
            return 1
        card_path = found

    ok, msg = redispatch_card(card_path, dispatch_dir=dispatch_dir)
    if not ok:
        print(f"[ERROR] {msg}", file=sys.stderr)
        return 1
    print(f"[OK] {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
