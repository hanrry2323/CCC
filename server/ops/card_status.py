"""reaper 卡状态解析（纯函数 · v2.0 P4.2）。

只做「卡文件 → 结构化视图」的解析与分类，不碰网络/git/ledger。
看板 API、分支枚举、ledger 落账、看板标黄全部放 reaper-card-audit.sh。

设计约束（launchd 每日 06:05 与 ccc-prod-health 同批）：
- 启动开销极低：仅 stdlib + 本模块，无第三方 import；
- 解析失败只标注不抛出（卡文件半写/编码污染仍能跑完全部卡）；
- 状态取卡头 `状态：`（契约 §2 六态），括号变体按基础态归一（与 loader 同口径）。

分类矩阵（v2.0 宪章 P4.2 · docs/notes/2026-09-07-reaper-report.md §2）：
- card_missing_on_board      卡有、看板无（漏索引/漏入库）
- board_orphan               看板有、卡无（孤儿视图条目/索引幽灵）
- state_drift_disk_vs_board  卡头状态 ≠ 看板状态（含看板运行时合成覆盖导致的合法漂移，WARN 级）
- branch_orphan              codex/* 分支无对应卡（已删卡未删分支）
- branch_missing             活跃卡（待分派/执行中/已回写/打回）无对应分支
- branch_merged_uncleaned    已关闭卡仍有未删 codex/* 分支（已合并未删，可清）
- branch_card_state_conflict 已关闭/作废卡仍挂 codex/* 分支（僵尸分支）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# 契约 §2 六态（与 server/board/models.py STATE 同口径；这里不做跨模块 import，
# 保持 reaper 独立、可被 bash 无虚拟环境复用）
STATES: tuple[str, ...] = ("待分派", "执行中", "已回写", "已关闭", "打回", "作废")

# 允许挂 codex/* 分支的状态：非终态（已关闭/作废 不允许分支残留）
BRANCH_OK_STATES: frozenset[str] = frozenset({"待分派", "执行中", "已回写", "打回"})

_CARD_ID_RE = re.compile(r"^([a-z]{2,4}\d{3,4})-", re.IGNORECASE)
_STATE_RE = re.compile(r"状态[：:]\s*([^·\n]+)")


def base_state(raw: str) -> str:
    """基础态归一：取括号前基础态（与 loader base_state 同口径）。"""
    if not raw:
        return "未知"
    base = re.split(r"[（(]", str(raw), maxsplit=1)[0].strip()
    return base or "未知"


def branch_name(card_path: str | Path) -> str:
    """卡路径 → codex/ 分支名：`docs/dispatch/<p>/<id>-<slug>.md` → `codex/<id>-<slug>`。"""
    return "codex/" + Path(card_path).stem.lower()


def card_id_of_branch(branch: str) -> str | None:
    """codex/ 分支名 → 卡 ID（`codex/xy060-content-library-api` → `xy060`）；非法/非 codex 前缀返回 None。"""
    if not branch.startswith("codex/"):
        return None
    stem = branch[len("codex/") :]
    m = _CARD_ID_RE.match(stem)
    return m.group(1).lower() if m else None


class CardParse:
    """单张卡文件的解析结果。解析失败不抛异常，标记 broken=True。"""

    __slots__ = (
        "id",
        "path",
        "state_raw",
        "state",
        "branch",
        "broken",
        "error",
        "has_branch_ok_state",
    )

    def __init__(
        self,
        *,
        id: str,
        path: str,
        state_raw: str,
        state: str,
        branch: str,
        broken: bool = False,
        error: str = "",
    ) -> None:
        self.id = id
        self.path = path
        self.state_raw = state_raw
        self.state = state
        self.branch = branch
        self.broken = broken
        self.error = error
        self.has_branch_ok_state = state in BRANCH_OK_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "state_raw": self.state_raw,
            "state": self.state,
            "branch": self.branch,
            "broken": self.broken,
            "error": self.error,
        }


def parse_card(path: str | Path) -> CardParse:
    """解析单张卡文件 → CardParse。半写/编码异常标记 broken=True。"""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return CardParse(
            id=p.stem.split("-")[0].lower() if "-" in p.stem else p.stem.lower(),
            path=str(p),
            state_raw="",
            state="未知",
            branch=branch_name(p),
            broken=True,
            error=f"read failed: {exc}",
        )
    m = _CARD_ID_RE.match(p.name)
    if not m:
        return CardParse(
            id=p.stem.lower(),
            path=str(p),
            state_raw="",
            state="未知",
            branch=branch_name(p),
            broken=True,
            error=f"card id regex not matched: {p.name}",
        )
    card_id = m.group(1).lower()
    sm = _STATE_RE.search(text)
    state_raw = sm.group(1).strip() if sm else ""
    state = base_state(state_raw)
    if not state_raw:
        state = "未知"
    if state not in STATES:
        return CardParse(
            id=card_id,
            path=str(p),
            state_raw=state_raw,
            state=state,
            branch=branch_name(p),
            broken=True,
            error=f"state not in STATES: {state_raw!r}",
        )
    return CardParse(
        id=card_id,
        path=str(p),
        state_raw=state_raw,
        state=state,
        branch=branch_name(p),
    )


def scan_dispatch(dispatch_dir: str | Path) -> list[CardParse]:
    """扫描 docs/dispatch/<prefix>/<id>-<slug>.md 全部任务卡，按 id 排序。"""
    root = Path(dispatch_dir)
    out: list[CardParse] = []
    if not root.is_dir():
        return out
    for p in sorted(root.glob("*/*.md")):
        if not _CARD_ID_RE.match(p.name):
            continue
        out.append(parse_card(p))
    out.sort(key=lambda c: c.id)
    return out
