"""reaper 三方对账核心（纯函数 · v2.0 P4.2）。

输入：卡解析视图 + 看板视图 + 分支集合 → 输出差异记录列表。
输出记录为纯 dict，写 ledger / 看板标黄 / 报告全部由调用方决定。

差异分类矩阵（详见 docs/notes/2026-09-07-reaper-report.md §2）：
- card_missing_on_board      卡有、看板无
- board_orphan               看板有、卡无
- state_drift_disk_vs_board  卡头状态 ≠ 看板状态
- branch_orphan              codex/* 分支无对应卡
- branch_missing             活跃卡（待分派/执行中/已回写/打回）无对应分支
- branch_merged_uncleaned    已关闭卡仍有未删 codex/* 分支（已合并未删）
- branch_card_state_conflict 已关闭/作废卡仍挂 codex/* 分支
"""

from __future__ import annotations

from typing import Any, Iterable

from server.ops.card_status import BRANCH_OK_STATES, CardParse, card_id_of_branch

# 差异代码 → 严重级别（severe 阻板标红；warn 看板标黄；info 仅 ledger 留档）
SEVERITY: dict[str, str] = {
    "card_missing_on_board": "warn",
    "board_orphan": "severe",
    "state_drift_disk_vs_board": "warn",
    "branch_orphan": "warn",
    "branch_missing": "severe",
    "branch_merged_uncleaned": "warn",
    "branch_card_state_conflict": "severe",
}


def classify_diffs(
    cards: Iterable[CardParse],
    board_items: Iterable[dict[str, Any]],
    branches: Iterable[str],
) -> list[dict[str, Any]]:
    """输入三视图，输出差异记录（无差异时空列表）。"""
    card_by_id: dict[str, CardParse] = {c.id: c for c in cards}
    card_ids: set[str] = set(card_by_id)

    # 看板：id → state（取 board_column 优先，与看板渲染一致）
    board_map: dict[str, dict[str, Any]] = {}
    for item in board_items:
        bid = str(item.get("id") or "")
        if bid:
            board_map[bid] = item
    board_ids: set[str] = set(board_map)

    # 分支：codex/* → {branch, card_id, merged}（跨仓）。兼容纯字符串输入；
    # 生产入口传 dict 并由 git merge-base 独立核验是否已合入 main。
    branch_map: dict[str, dict[str, Any]] = {}
    for raw_branch in branches:
        if isinstance(raw_branch, dict):
            b = str(raw_branch.get("branch") or "")
            merged = bool(raw_branch.get("merged", False))
        else:
            b = str(raw_branch)
            merged = False
        cid = card_id_of_branch(b)
        if cid:
            branch_map[b] = {"card_id": cid, "merged": merged}
    branch_ids: set[str] = {entry["card_id"] for entry in branch_map.values()}

    diffs: list[dict[str, Any]] = []

    for cid, card in card_by_id.items():
        if cid not in board_map:
            diffs.append(_diff("card_missing_on_board", cid, card=card))
        else:
            # `board_column=机审` 是「已回写」的派生展示列，不是卡头状态；
            # 三方对账必须比较看板原始 state，避免把合法机审列误报为漂移。
            board_state = str(board_map[cid].get("state") or "")
            board_state = board_state.split("（", 1)[0].split("(", 1)[0].strip() or board_state.strip() or ""
            if board_state == "已作废":
                board_state = "作废"
            if board_state and board_state != card.state:
                diffs.append(
                    _diff(
                        "state_drift_disk_vs_board",
                        cid,
                        card=card,
                        extra={"board_state": board_state},
                    )
                )

    for bid in board_ids - card_ids:
        diffs.append(
            _diff(
                "board_orphan",
                bid,
                extra={"board_state": str(board_map[bid].get("state") or "")},
            )
        )

    # 分支侧（只按卡 ID 关联；跨仓同卡名分支一并计为同源）
    for branch, entry in sorted(branch_map.items()):
        cid = entry["card_id"]
        if cid not in card_ids:
            diffs.append(
                _diff("branch_orphan", cid, extra={"branch": branch})
            )
            continue
        state = card_by_id[cid].state
        if state in BRANCH_OK_STATES:
            continue
        if state == "已关闭":
            code = "branch_merged_uncleaned" if entry["merged"] else "branch_card_state_conflict"
            diffs.append(_diff(code, cid, extra={"branch": branch, "merged": entry["merged"]}))
        elif state == "作废":
            diffs.append(_diff("branch_card_state_conflict", cid, extra={"branch": branch, "merged": entry["merged"]}))

    # 活跃卡缺分支（同一卡可能在多仓多分支，任一存在即满足）
    present = {c for c in branch_ids}
    for cid, card in card_by_id.items():
        if card.state in BRANCH_OK_STATES and cid not in present:
            diffs.append(_diff("branch_missing", cid, card=card))

    return diffs


def _diff(code: str, cid: str, *, card: CardParse | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "kind": "reaper_diff",
        "code": code,
        "severity": SEVERITY.get(code, "info"),
        "card_id": cid,
        "detail": "",
    }
    details: list[str] = []
    if card is not None:
        details.append(f"card_state={card.state}")
        rec["card_path"] = card.path
    if extra:
        rec.update(extra)
        details.extend(f"{k}={v}" for k, v in extra.items())
    rec["detail"] = " ".join(details)
    return rec


__all__ = ["classify_diffs", "SEVERITY"]
