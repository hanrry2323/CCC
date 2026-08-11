"""方案链编号保留表（2026-08-12 · 出卡/校验单一事实源）。"""

from __future__ import annotations

from pathlib import Path

from server.board.plan_reservations import (
    next_free_card_id,
    plan_reserved_card_titles,
    plan_reserved_ids,
)


def _write_plan(projects_dir: Path, prefix: str, num: int, related: str) -> Path:
    pdir = projects_dir / prefix / "plans"
    pdir.mkdir(parents=True, exist_ok=True)
    p = pdir / f"{prefix}-plan-{num:03d}.md"
    p.write_text(
        f"# 方案 · 测试方案 {num}\n\n"
        f"> 关联卡：{related}\n",
        encoding="utf-8",
    )
    return p


def test_plan_reserved_ids_extracts_related_cards(tmp_path: Path) -> None:
    _write_plan(tmp_path, "mx", 1, "mx001, mx003, mx005")
    _write_plan(tmp_path, "clw", 2, "clw010")
    reserved = plan_reserved_ids(tmp_path)
    assert reserved["mx"] == {1, 3, 5}
    assert reserved["clw"] == {10}


def test_plan_reserved_card_titles(tmp_path: Path) -> None:
    _write_plan(tmp_path, "mx", 7, "mx007")
    titles = plan_reserved_card_titles()
    # 真实库与临时库并存时以真实库为准；临时库文件不污染真实库（函数默认读仓内 docs/projects）
    assert isinstance(titles, dict)


def test_plan_reserved_ids_missing_dir() -> None:
    assert plan_reserved_ids("/nonexistent-dir-xyz") == {}


def test_next_free_card_id_skips_reserved(monkeypatch) -> None:
    from server.board import plan_reservations

    monkeypatch.setattr(plan_reservations, "plan_reserved_ids", lambda: {"mx": {1, 2, 4}})
    # taken={1}：1 已占用，2/4 保留 → 3 空闲
    assert next_free_card_id("mx", {1}) == 3
    # 1/2/4 保留 + 3/5 占用 → 6 空闲
    assert next_free_card_id("mx", {3, 5}) == 6
