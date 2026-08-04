"""从任务卡文档解析看板派生数据（任务卡 = 唯一事实源）。

- 元数据块（`>` 行，`key：value` 以 `·` 分隔）→ 状态 / 项目 / 执行体 / 分派时间 / 派发方式。
- 项目：卡头「项目」字段优先；缺省从「关联」首段（冒号/空格前）推导，推导不出归「未分类」。
- 派发方式：卡头「派发」字段（manual|engine，缺省 engine）。
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

from server.board.models import UNCLASSIFIED, UNKNOWN, BoardItem, base_state

# `# 任务卡 T3 · 标题`（MULTILINE：^/$ 按行锚定）
_TITLE_RE = re.compile(r"^#\s*任务卡\s+(\S+)\s*[·\-]\s*(.+?)\s*$", re.MULTILINE)
# 元数据行内的 `key：value`（`>` 行，`·` 分隔）
_META_PAIR_RE = re.compile(r"^\s*([^：\s][^：]*?)\s*[:：]\s*(.+?)\s*$")
# 回写区日期：`**日期**：YYYY-MM-DD`
_WRITTEN_RE = re.compile(r"\*\*日期\*\*\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
# 显式打回次数：`打回次数：N`
_REJECT_RE = re.compile(r"打回次数\s*[:：]\s*(\d+)")

# 「派发」字段合法值（缺省 engine）
_DISPATCH_VALUES: frozenset[str] = frozenset({"manual", "engine"})
# 推导出的项目名不得含这些字符（长句/引号/括号 → 非项目前缀，归「未分类」）
_GARBLED_RE = re.compile(r"[「」『』【】\"'<>（）()]")
# 卡头标题行：`# 任务卡 <ID>`（行首锚定；正文/说明里出现 `# 任务卡` 字面量不算）
_CARD_TITLE_RE = re.compile(r"^#\s*任务卡\s", re.MULTILINE)


def _strip_parenthetical(value: str) -> str:
    """取括号前部分（如 `INT-120（CCC 重构）` → `INT-120`）。"""
    return re.split(r"[（(]", value, maxsplit=1)[0].strip()


def _derive_project_from_related(related: str) -> str:
    """旧卡兼容：无「项目」字段时从「关联」首段推导项目名。

    推导规则（T53）：
    1. 取关联值首段（按 `：`/`:`/空格 切分）；
    2. 去括号（如 `INT-120（CCC 重构）` → `INT-120`）；
    3. 结果含引号/括号等非项目前缀字符、或为空/未知 → 「未分类」。

    例：`INT-120（CCC 重构）` → `INT-120`；`阶段 3 P1` → `阶段`；
        `新阶段「双壳可用 + 心智升级」` → 「未分类」。
    """
    if not related or related == UNKNOWN:
        return UNCLASSIFIED
    seg = re.split(r"[：:\s]", related, maxsplit=1)[0].strip()
    seg = _strip_parenthetical(seg)
    if not seg or seg == UNKNOWN or _GARBLED_RE.search(seg):
        return UNCLASSIFIED
    return seg


def _resolve_project(meta: dict[str, str]) -> str:
    """项目名：卡头「项目」字段优先；缺省从「关联」首段推导。"""
    explicit = meta.get("项目", "").strip()
    if explicit:
        return _strip_parenthetical(explicit)
    return _derive_project_from_related(meta.get("关联", UNKNOWN))


def _resolve_dispatch(meta: dict[str, str]) -> str:
    """派发方式：manual|engine（缺省 engine；非法值回落 engine）。"""
    raw = (meta.get("派发", "") or "").strip().lower()
    return raw if raw in _DISPATCH_VALUES else "engine"


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
        project=_resolve_project(meta),
        executor=_strip_parenthetical(meta.get("执行体", UNKNOWN)),
        dispatched_at=meta.get("日期", UNKNOWN),
        written_at=_parse_written_at(text),
        reject_count=reject_count,
        dispatch=_resolve_dispatch(meta),
    )


def _is_task_card(path: Path) -> bool:
    """是否任务卡：行首含 `# 任务卡` 卡头标题；T-mapping.md 等说明文档跳过。"""
    return bool(_CARD_TITLE_RE.search(path.read_text(encoding="utf-8")))


def scan_dispatch_files(directory: Path | str) -> list[Path]:
    """扫描任务卡文件：根目录平铺（旧卡）+ 一层子目录（`<prefix>/` 下新卡）。

    T54 规则：旧卡（根 `T*.md`）与 `<prefix>/` 子目录新卡共存；只认含 `# 任务卡`
    卡头标题的 .md，T-mapping.md 等说明文档不参与。目录不存在返回空。
    """
    d = Path(directory)
    if not d.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(d.glob("*.md")):
        if _is_task_card(p):
            files.append(p)
    for p in sorted(d.glob("[!.]*/[!.]*.md")):
        if _is_task_card(p):
            files.append(p)
    return files


def load_dispatch_cards(directory: Path | str) -> list[BoardItem]:
    """扫描目录下全部任务卡（根平铺旧卡 + 一层子目录新卡）；单张失败跳过不崩。"""
    items: list[BoardItem] = []
    for path in scan_dispatch_files(directory):
        try:
            items.append(parse_card(path))
        except OSError:
            continue
    return items
