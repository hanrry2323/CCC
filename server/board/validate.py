"""任务卡卡头校验器（2026-08-04 新增，填补「文件即事实源但无机器校验」缺口）。

扫描 ``docs/dispatch``（根平铺旧卡 + 一层子目录新卡），逐卡校验：

- 卡头 ``>`` 元数据行必含：关联 / 执行体 / 状态 / 日期；
- 状态值必须是五态之一（待分派 / 执行中 / 已回写 / 已关闭 / 打回）；
- 非「待分派」状态必须存在回写区（``## 回写区`` 且含执行体行）；
- 卡文件必须存在 ``## 目标`` 与 ``## 验收标准`` 节（格式最低要求）。

T54 命名规则（新卡强制，旧卡仅提示）：
- 新卡文件名 ``<前缀><三位序号>-<slug>.md`` 且必须位于 ``docs/dispatch/<前缀>/`` 子目录；
- 前缀必须在项目前缀表（``server.board.models.PREFIXES``）内；子目录名必须等于前缀；
- ``<前缀><NNN>`` 全目录唯一（编号跨项目唯一）；
- 旧卡（根目录 ``T*.md``）零拦截：仅提示迁移建议，不阻断；
- 非任务卡文档（无 ``# 任务卡`` 卡头，如 ``T-mapping.md``）不参与校验。

用法::

    $PYTHON_BIN -m server.board.validate [dispatch_dir]

返回码：0 = 无 error 问题（warn 提示不影响退出码）；1 = 存在 error 问题。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from server.board.models import PREFIXES, base_state

VALID_STATES = frozenset({"待分派", "执行中", "已回写", "已关闭", "打回"})
REQUIRED_HEADER_KEYS = ("关联", "执行体", "状态", "日期")

# T54 新卡文件名：`<前缀><三位序号>-<slug>.md`（前缀 2-4 位小写字母；slug 小写字母数字 + 单连字符）
NEW_CARD_RE = re.compile(
    r"^(?P<prefix>[a-z]{2,4})(?P<num>\d{3})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
# 旧卡：`T<N>-...`（根目录平铺）
OLD_CARD_RE = re.compile(r"^T\d")


@dataclass
class CardIssue:
    """单张卡的一个问题。"""

    card_id: str
    path: str
    reason: str
    severity: str = "error"  # error=阻断（退出码 1）；warn=提示（退出码 0）


# 卡头标题行（``# 任务卡 <ID>``），须行首锚定——正文/说明里出现 ``# 任务卡`` 字面量不算
_CARD_TITLE_LINE_RE = re.compile(r"^#\s*任务卡\s", re.MULTILINE)


def _has_card_title(path: Path) -> bool:
    """是否任务卡（行首含 ``# 任务卡`` 卡头标题）；排除 T-mapping.md 等说明文档。"""
    return bool(_CARD_TITLE_LINE_RE.search(path.read_text(encoding="utf-8")))


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


def _classify_card(path: Path) -> tuple[str, str, str]:
    """按文件名分类：``(类型, 前缀, 编号)``。类型: new|old|other。"""
    stem = path.stem
    m = NEW_CARD_RE.match(stem)
    if m:
        return "new", m.group("prefix"), m.group("num")
    if OLD_CARD_RE.match(stem):
        return "old", "", ""
    return "other", "", ""


def _card_number(path: Path) -> str:
    """取文件名编号（``T<N>-...`` → ``N``；``<prefix><NNN>-...`` → ``NNN``）。"""
    stem = path.stem
    if OLD_CARD_RE.match(stem):
        m = re.match(r"T(\d+)", stem)
        return m.group(1) if m else ""
    m = NEW_CARD_RE.match(stem)
    return m.group("num") if m else ""


def _header_card_id(card: Path) -> str:
    """取卡头 ``# 任务卡 <ID>`` 的 ID（停在 ``·`` 或空白处）；未匹配返回空。

    旧卡两种写法并存：``# 任务卡 T1-server-skeleton``（含 slug）与
    ``# 任务卡 T52 · 自动化基建``（仅编号），统一取 ``T<N>`` 前缀即可；
    新卡取 ``<prefix><NNN>``（可带 ``-<slug>``，数字部分一致）。
    """
    m = re.search(r"#\s*任务卡\s+([^\s·]+)", card.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def _header_number(card: Path) -> str:
    """取卡头 ID 的数字部分（``T52`` → ``52``；``ccc064`` / ``ccc064-foo`` → ``064``）。"""
    m = re.search(r"(\d+)", _header_card_id(card))
    return m.group(1) if m else ""


def _scan_cards(dispatch_dir: Path) -> list[tuple[Path, str]]:
    """扫描任务卡：根目录平铺（旧卡）+ 一层子目录（``<prefix>/`` 下新卡）。

    只认带 ``# 任务卡`` 卡头标题的 .md；``T-mapping.md`` 等说明文档被跳过。
    返回 ``(path, location)``，location ∈ root | subdir。
    """
    cards: list[tuple[Path, str]] = []
    if not dispatch_dir.is_dir():
        return cards
    for p in sorted(dispatch_dir.glob("*.md")):
        if _has_card_title(p):
            cards.append((p, "root"))
    for p in sorted(dispatch_dir.glob("[!.]*/[!.]*.md")):
        if _has_card_title(p):
            cards.append((p, "subdir"))
    return cards


def _validate_new_naming(
    path: Path,
    loc: str,
    prefix: str,
    num: str,
) -> list[CardIssue]:
    """新规则卡命名校验（错误命名即拦截）。"""
    issues: list[CardIssue] = []
    card_id = path.stem
    name = path.name
    m = NEW_CARD_RE.match(path.stem)
    if not m:
        issues.append(
            CardIssue(card_id, str(path), f"子目录卡文件名不符合新命名规则 <前缀><三位序号>-<slug>.md: {name}")
        )
        return issues
    prefix, num, slug = m.group("prefix"), m.group("num"), m.group("slug")
    if prefix not in PREFIXES:
        issues.append(
            CardIssue(card_id, str(path), f"未知前缀 {prefix!r}（合法前缀: {sorted(PREFIXES)}）")
        )
    if loc != "subdir":
        issues.append(CardIssue(card_id, str(path), f"新规则卡 {card_id} 必须位于子目录 {prefix}/ 下"))
    elif path.parent.name != prefix:
        issues.append(
            CardIssue(card_id, str(path), f"新规则卡 {card_id} 所在子目录 {path.parent.name!r} 与前缀 {prefix!r} 不符")
        )
    # 卡头编号与文件名一致（防复制卡只改文件名不改卡头）
    hdr_id = _header_card_id(path)
    hdr_num = _header_number(path)
    if hdr_num and hdr_num != num:
        issues.append(CardIssue(card_id, str(path), f"卡头编号 {hdr_id} 与文件名 {card_id} 不一致"))
    return issues


def validate_cards(dispatch_dir: str | Path) -> list[CardIssue]:
    """校验目录下全部任务卡，返回问题清单（error 空 = 门禁通过，warn 仅提示）。

    T52 增强（出卡门禁）：
    - 编号一致性：卡头 ``# 任务卡 T<N>`` 的数字前缀与文件名 ``T<N>-...`` 必须一致
      （防止文件改名/复制后卡头编号错乱）；
    - 编号唯一：卡头 ID 重复（同编号两张卡，如复制卡只改文件名不改卡头）报重。
    T54 增强（命名规则）：
    - 新卡必须 ``<前缀><NNN>-<slug>.md`` 且位于对应子目录；编号跨项目唯一；
    - 旧卡（根目录 ``T*.md``）仅提示不拦截；非任务卡文档（如 T-mapping.md）跳过。
    注：R/X 变体卡（``T1`` 与 ``T1-R-...``）数字前缀允许共存，按卡头 ID 判重。
    """
    issues: list[CardIssue] = []
    d = Path(dispatch_dir)
    if not d.is_dir():
        return [CardIssue("?", str(d), "目录不存在")]
    cards = _scan_cards(d)

    # 编号唯一：新卡按 <前缀><NNN> 判重；旧卡按卡头 ID 判重（R/X 变体卡卡头 ID 不同，不误伤）
    new_by_id: dict[str, list[Path]] = {}
    old_by_hdr: dict[str, list[Path]] = {}
    for path, _loc in cards:
        ctype, prefix, num = _classify_card(path)
        if ctype == "new":
            new_by_id.setdefault(prefix + num, []).append(path)
        else:
            hdr_id = _header_card_id(path)
            if hdr_id:
                old_by_hdr.setdefault(hdr_id, []).append(path)
    for cid, dupes in new_by_id.items():
        if len(dupes) > 1:
            for card in dupes[1:]:
                issues.append(
                    CardIssue(card.stem, str(card), f"新卡编号 {cid} 重复（与 {dupes[0].name} 冲突，编号跨项目唯一）")
                )
    for hdr_id, dupes in old_by_hdr.items():
        if len(dupes) > 1:
            for card in dupes[1:]:
                issues.append(
                    CardIssue(card.stem, str(card), f"编号 {hdr_id} 重复（与 {dupes[0].name} 冲突，编号必须唯一）")
                )

    for path, loc in cards:
        card_id = path.name.split(".")[0]
        ctype, prefix, num = _classify_card(path)
        if ctype == "new":
            issues.extend(_validate_new_naming(path, loc, prefix, num))
        elif ctype == "old":
            # 旧卡零拦截：仅提示迁移建议（T54 红线 2：旧卡不批量重命名，保持 git 历史）
            issues.append(
                CardIssue(
                    card_id,
                    str(path),
                    "旧卡（T 前缀）保持原名不迁移；新卡请用 <前缀><NNN>-<slug>.md 放 <前缀>/ 子目录（见 T-mapping.md）",
                    severity="warn",
                )
            )
            if loc == "subdir":
                issues.append(
                    CardIssue(
                        card_id,
                        str(path),
                        "旧卡样式文件位于子目录（旧卡应留在根目录；子目录只放新规则卡）",
                        severity="warn",
                    )
                )
        else:
            if loc == "subdir":
                issues.append(
                    CardIssue(card_id, str(path), f"子目录卡文件名不符合新命名规则 <前缀><三位序号>-<slug>.md: {path.name}")
                )

        meta = _header_metadata(path)
        if not meta:
            issues.append(CardIssue(card_id, str(path), "缺少卡头元数据行（> 且含 key：value）"))
            continue
        missing = [k for k in REQUIRED_HEADER_KEYS if not meta.get(k, "").strip()]
        if missing:
            issues.append(CardIssue(card_id, str(path), f"卡头缺字段: {missing}"))
        state_raw = meta.get("状态", "")
        base = base_state(state_raw)
        if base not in VALID_STATES:
            issues.append(CardIssue(card_id, str(path), f"状态值非法: {state_raw!r}（合法={sorted(VALID_STATES)}）"))
        if base in ("已回写", "已关闭", "打回") and not _body_has(path, "## 回写区"):
            issues.append(CardIssue(card_id, str(path), f"状态 {base} 但缺少 ## 回写区"))
        if not _body_has(path, "## 目标"):
            issues.append(CardIssue(card_id, str(path), "缺少 ## 目标"))
        if not _body_has(path, "## 验收标准"):
            issues.append(CardIssue(card_id, str(path), "缺少 ## 验收标准"))
    return issues


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    target = argv[0] if argv else "docs/dispatch"
    issues = validate_cards(target)
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warn"]
    count = len(_scan_cards(Path(target))) if Path(target).is_dir() else 0
    if not errors:
        print(f"卡头校验通过：{target}（{count} 张卡，{len(warns)} 条提示）")
        for w in warns:
            print(f"  [提示] [{w.card_id}] {w.path}: {w.reason}")
        return 0
    print(f"卡头校验发现 {len(errors)} 个问题（另 {len(warns)} 条提示）：")
    for it in errors:
        print(f"  [{it.card_id}] {it.path}: {it.reason}")
    for w in warns:
        print(f"  [提示] [{w.card_id}] {w.path}: {w.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
