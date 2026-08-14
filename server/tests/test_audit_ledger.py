"""测试 server/board/audit_ledger.py — 机审命中率台账（机审 v4 · 2026-08-14）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from server.board.audit_ledger import (
    backfill_card_hits,
    hit_rate,
    load_ledger,
    mark_card_hit,
    record_audit,
)


def _patched_ledger(tmp_path: Path):
    return patch(
        "server.board.audit_ledger._ledger_path",
        return_value=tmp_path / "ledger.jsonl",
    )


def test_record_and_load(tmp_path: Path):
    """记录写入 + 读取。"""
    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc001", conclusion="不通过", severity="重", reasons=["红线越界"])
        record_audit("w1", "ccc001", conclusion="通过", severity="重")
        rows = load_ledger()
        assert len(rows) == 2
        assert rows[0]["conclusion"] == "不通过"
        assert rows[0]["severity"] == "重"
        assert rows[1]["conclusion"] == "通过"


def test_backfill_hits_on_pass(tmp_path: Path):
    """卡最终通过 → 既往「不通过」回填命中；「通过」行自身留待合入时标（重度复审口径修正）。"""
    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc002", conclusion="不通过", severity="轻", reasons=["缺注释"])
        record_audit("w1", "ccc002", conclusion="不通过", severity="中", reasons=["边界未覆盖"])
        record_audit("w1", "ccc002", conclusion="通过", severity="中")
        backfill_card_hits("ccc002")
        rows = load_ledger()
        # 两条不通过 → 命中；通过行 hit 保持 None（待合入 mark_card_pass_hit）
        assert rows[0]["hit"] is True
        assert rows[1]["hit"] is True
        assert rows[2]["hit"] is None


def test_mark_false_positive(tmp_path: Path):
    """老板标误报 → 最近一条不通过回填未命中。"""
    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc003", conclusion="不通过", severity="中", reasons=["疑似误报"])
        record_audit("w2", "ccc003", conclusion="不通过", severity="中", reasons=["真问题"])
        mark_card_hit("ccc003", False)
        rows = load_ledger()
        # 最近一条（真问题）标为未命中；更早的保持 None
        assert rows[-1]["hit"] is False
        assert rows[0]["hit"] is None


def test_pass_hit_at_merge(tmp_path: Path):
    """通过行命中在合入时回填：无返工=命中，返工=未命中。"""
    from server.board.audit_ledger import mark_card_pass_hit, mark_card_pass_miss

    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc007", conclusion="通过", severity="中")
        mark_card_pass_hit("ccc007")
        assert load_ledger()[-1]["hit"] is True
        # 返工 → 未命中
        record_audit("w2", "ccc008", conclusion="通过", severity="中")
        mark_card_pass_miss("ccc008")
        assert load_ledger()[-1]["hit"] is False


def test_infra_not_counted(tmp_path: Path):
    """基建失败（机审执行失败）不参与命中判定。"""
    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc009", conclusion="不通过", severity="中", kind="infra", reasons=["机审执行失败"])
        backfill_card_hits("ccc009")
        rows = load_ledger()
        # infra 行 hit 保持 None（不被 backfill 标命中）
        assert rows[0]["hit"] is None
        assert hit_rate()["total"] == 0


def test_hit_rate(tmp_path: Path):
    """命中率统计：hit 已判定的审计记录（不含 infra）中的命中比例。"""
    from server.board.audit_ledger import mark_card_pass_hit

    with _patched_ledger(tmp_path):
        record_audit("w1", "ccc004", conclusion="不通过", severity="中")
        record_audit("w2", "ccc005", conclusion="不通过", severity="中")
        record_audit("w3", "ccc006", conclusion="通过", severity="中")
        mark_card_hit("ccc004", True)   # 不通过行：修复后命中
        mark_card_hit("ccc005", False)  # 老板标误报
        mark_card_pass_hit("ccc006")    # 通过行：合入无返工命中
        rate = hit_rate()
        assert rate["total"] == 3
        assert rate["hits"] == 2
        assert rate["misses"] == 1
        assert rate["hit_rate"] == round(2 / 3, 3)
