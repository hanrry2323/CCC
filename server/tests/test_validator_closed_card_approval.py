"""ccc072 · 已关闭卡豁免卡头「批准」章校验。

背景：approve-merge 人审节点③（scripts/approve-merge.sh close_card）在每张卡
关闭时会于卡头有意盖「> 批准：老板合入批准」章；validate.py 若无条件将「批准」
列为违禁卡头字段，每张新合并卡会瞬间毒化所属项目出卡校验通道
（tst004/ccc068/xy059 实证）。本测试锁定语义：已关闭卡豁免「批准」键，
未关闭卡仍严格报错，其余违禁键（审批/review/approval）全态不豁免。
"""

from __future__ import annotations

from pathlib import Path

from server.board.validate import validate_cards


def _write_card(
    tmp: Path,
    name: str,
    hdr_id: str,
    state: str,
    extra_header: str = "",
) -> Path:
    """写一张新规则卡夹具（clw 子目录），默认含 close_card 所盖「批准」章行。

    同参数不同 ``state`` 的两张卡内容完全同构（唯一差异=状态）。
    """
    sub = tmp / "clw"
    sub.mkdir(parents=True, exist_ok=True)
    p = sub / name
    p.write_text(
        f"# 任务卡 {hdr_id} · 批准章测试\n"
        f"> 关联：TEST · 执行体：OpenCode · 验收：OpenCode · 状态：{state}"
        f" · 项目：clw · 日期：2026-08-24 · 批准：老板合入批准{extra_header}\n"
        "\n## 目标\nx\n\n## 验收标准\nx\n\n## 回写区\n**执行体**：X · 日期：\n",
        encoding="utf-8",
    )
    return p


def test_closed_card_exempt_open_card_rejected(tmp_path: Path) -> None:
    """两张 tmp 卡夹具唯一差异=状态（均含「批准」章行）：

    - 已关闭卡 → 零 issue（豁免生效，不再毒化出卡校验通道）；
    - 待分派卡 → 含且仅含对应的「批准」违禁字段 issue。
    """
    closed = _write_card(tmp_path, "clw905-closed-stamp.md", "clw905", "已关闭")
    dispatched = _write_card(tmp_path, "clw906-open-stamp.md", "clw906", "待分派")

    issues = validate_cards(tmp_path)
    closed_issues = [i for i in issues if i.path == str(closed)]
    assert closed_issues == [], f"已关闭卡应零 issue，实得：{[i.reason for i in closed_issues]}"

    dispatched_issues = [i for i in issues if i.path == str(dispatched)]
    assert len(dispatched_issues) == 1, f"待分派卡应恰好一条 issue，实得：{[(i.severity, i.reason) for i in dispatched_issues]}"
    assert "「批准」" in dispatched_issues[0].reason
    assert dispatched_issues[0].severity == "error"


def test_closed_card_other_forbidden_keys_not_exempt(tmp_path: Path) -> None:
    """豁免仅限「批准」键：已关闭卡的「审批/review」仍报错（禁扩大豁免范围）。"""
    card = _write_card(
        tmp_path,
        "clw907-closed-other-keys.md",
        "clw907",
        "已关闭",
        extra_header=" · 审批：某人 · review：pending",
    )
    issues = [i for i in validate_cards(tmp_path) if i.path == str(card)]
    reasons = " | ".join(i.reason for i in issues)
    assert "「审批」" in reasons
    assert "「review」" in reasons
    assert "「批准」" not in reasons
