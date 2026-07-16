"""test_intake_pipeline.py — 分级架构测试（v0.35）

覆盖:
  1. _classify_task_intake — auto/quick/full 分类
  2. _intake_failsafe — 源头熔断
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import importlib
    _spec = importlib.util.spec_from_file_location("ccc_board", str(ROOT / "scripts" / "ccc-board.py"))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _classify_task_intake = _mod._classify_task_intake
    _intake_failsafe = _mod._intake_failsafe
finally:
    sys.path.pop(0)

# ═══════════════════════════════════════════════════════════════
# _classify_task_intake
# ═══════════════════════════════════════════════════════════════

def _task(tags=None, title="", desc="", tid=""):
    return {
        "id": tid,
        "title": title,
        "description": desc,
        "tags": tags or [],
    }


class TestClassify:
    def test_auto_audit_review(self):
        """tags 含 audit+review → auto"""
        assert _classify_task_intake(_task(["audit", "review"], "type error")) == "auto"

    def test_auto_auto_tag(self):
        """tags 含 auto → auto"""
        assert _classify_task_intake(_task(["auto"], "fix lint")) == "auto"

    def test_auto_audit_review_id(self):
        """id 以 audit-review- 开头 → auto"""
        assert _classify_task_intake(_task([], "", "", "audit-review-xxx")) == "auto"

    def test_auto_type_keyword(self):
        """title 含 type:/lint:/ruff: → auto"""
        assert _classify_task_intake(_task([], "type: db/hp_pg.py:149 error")) == "auto"
        assert _classify_task_intake(_task([], "lint: unused import")) == "auto"
        assert _classify_task_intake(_task([], "ruff: F841")) == "auto"

    def test_quick_fix_keyword(self):
        """title 含 fix/clean/typo + 短描述 → quick"""
        assert _classify_task_intake(_task([], "fix typo in config", "short desc")) == "quick"

    def test_quick_audit_non_decision(self):
        """tags 含 audit 不含 decision → quick"""
        assert _classify_task_intake(_task(["audit"], "some issue", "desc")) == "quick"

    def test_full_audit_decision(self):
        """tags 含 audit+decision → full"""
        assert _classify_task_intake(_task(["audit", "decision"], "arch change")) == "full"

    def test_full_default(self):
        """其他 → full"""
        assert _classify_task_intake(_task([], "large feature", "many changes needed")) == "full"
        assert _classify_task_intake(_task([], "refactor database module", "")) == "full"

    def test_edge_empty_fields(self):
        """空字段不崩溃"""
        assert _classify_task_intake({}) == "full"


# ═══════════════════════════════════════════════════════════════
# _intake_failsafe
# ═══════════════════════════════════════════════════════════════

class TestIntakeFailsafe:
    def test_allow_no_tasks(self, tmp_path):
        """no abnormal tasks → allow"""
        ws = Path(tmp_path)
        assert _intake_failsafe(ws, "decision") is True

    def test_allow_low_fail_rate(self, tmp_path):
        """abnormal 占比 < 60% → allow"""
        ws = Path(tmp_path)
        bp = ws / ".ccc" / "board"
        for col in ("backlog", "abnormal"):
            (bp / col).mkdir(parents=True, exist_ok=True)
        # 1 abnormal
        (bp / "abnormal" / "audit-decision-abnormal.jsonl").write_text(
            '{"id":"audit-decision-abnormal","status":"abnormal"}\n'
        )
        # 2 active = 33% fail rate
        (bp / "backlog" / "audit-decision-active-1.jsonl").write_text(
            '{"id":"audit-decision-active-1","status":"backlog"}\n'
        )
        (bp / "backlog" / "audit-decision-active-2.jsonl").write_text(
            '{"id":"audit-decision-active-2","status":"backlog"}\n'
        )
        assert _intake_failsafe(ws, "decision") is True

    def test_block_high_fail_rate(self, tmp_path):
        """abnormal 占比 > 60% → block"""
        ws = Path(tmp_path)
        bp = ws / ".ccc" / "board"
        for col in ("backlog", "abnormal"):
            (bp / col).mkdir(parents=True, exist_ok=True)
        # 3 abnormal
        for i in range(3):
            (bp / "abnormal" / f"audit-decision-{i}.jsonl").write_text(
                '{"id":"audit-decision-' + str(i) + '","status":"abnormal"}\n'
            )
        # 1 active
        (bp / "backlog" / "audit-decision-active.jsonl").write_text(
            '{"id":"audit-decision-active","status":"backlog"}\n'
        )
        assert _intake_failsafe(ws, "decision") is False

    def test_different_category_not_affected(self, tmp_path):
        """decision 类不受 review 类 abnormal 影响"""
        ws = Path(tmp_path)
        bp = ws / ".ccc" / "board"
        for col in ("backlog", "abnormal"):
            (bp / col).mkdir(parents=True, exist_ok=True)
        # 5 review 类，4 个 abnormal
        for i in range(5):
            (bp / "backlog" / f"audit-review-{i}.jsonl").write_text(
                '{"id":"audit-review-' + str(i) + '","status":"backlog"}\n'
            )
        for i in range(4):
            (bp / "abnormal" / f"audit-review-{i}.jsonl").write_text(
                '{"id":"audit-review-' + str(i) + '","status":"abnormal"}\n'
            )
            (bp / "backlog" / f"audit-review-{i}.jsonl").unlink(missing_ok=True)
        # decision 类 1 条正常
        (bp / "backlog" / "audit-decision-active.jsonl").write_text(
            '{"id":"audit-decision-active","status":"backlog"}\n'
        )
        assert _intake_failsafe(ws, "decision") is True
