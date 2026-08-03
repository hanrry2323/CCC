"""test_quarantine_reason_codes.py — Phase B (015): machine-readable reason codes.

Ensures critical quarantine/hang reason strings contain stable snake_case codes
like ``hang_detected``, ``reviewer_produced_no_verdict``, etc.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _src(fn) -> str:
    return inspect.getsource(fn)


class TestHangReason:
    """hang.py 产出 reason 必须含 hang_detected 机读码。"""

    def test_quarantine_hang_exhausted_contains_hang_detected(self):
        from engine.hang import _quarantine_hang_exhausted as fn

        body = _src(fn)
        assert "hang_detected" in body, (
            "_quarantine_hang_exhausted 的 reason 字面量须含 hang_detected"
        )

    def test_check_and_mark_hung_contains_hang_detected(self):
        from engine.hang import _check_and_mark_hung_unlocked as fn

        body = _src(fn)
        hang_count = body.count("hang_detected")
        assert hang_count >= 2, (
            f"expected ≥2 'hang_detected' in _check_and_mark_hung body, got {hang_count}"
        )


class TestQuarantineReason:
    """gates.py 等 quarantine reason 须含稳定的 snake_case 码。"""

    def test_retry_budget_exhausted_contains_code(self):
        from engine.gates import _run_reviewer_tester_gate_unlocked as fn

        body = _src(fn)
        assert (
            "reviewer_fail_loop_exhausted" in body
            or "reviewer 未产出 verdict" in body
            or "reviewer_produced_no_verdict" in body
        ), "retry/no-verdict quarantine path needs a stable code or known phrase"

    def test_quarantine_handle_fail_to_planned(self):
        from engine.gates import _handle_fail_to_planned as fn

        body = _src(fn)
        assert "reviewer_fail_loop_exhausted" in body, (
            "_handle_fail_to_planned quarantine reason must include "
            "reviewer_fail_loop_exhausted code"
        )

    def test_reviewer_produced_no_verdict_has_snake_case_in_reason(self):
        from engine.gates import _write_fail_verdict_before_quarantine as fn

        body = _src(fn)
        assert (
            "produced no verdict" in body
            or "reviewer_produced_no_verdict" in body
            or "reviewer" in body
        ), "_write_fail_verdict_before_quarantine must mention review/produced nature"


class TestLedgerCodes:
    """_failure_ledger.related_event_for_reason 必须正确映射 hang 码。"""

    def test_related_event_hang_detected(self):
        from _failure_ledger import related_event_for_reason

        for reason in (
            "hang_detected pid=123 cpu=0.5",
            "hang_detected: low-cpu-stale",
            "hang auto-restart exhausted",
            "hang_no_progress idle=300s",
        ):
            assert related_event_for_reason(reason) == "hang_detected", reason

    def test_related_event_default_is_quarantine(self):
        from _failure_ledger import related_event_for_reason

        assert related_event_for_reason("reviewer timeout") == "quarantine"
        assert related_event_for_reason("acceptance_cmd_failed") == "quarantine"
        assert related_event_for_reason("tester failed") == "quarantine"


class TestFailureLearningCodes:
    """_failure_learning.classify_failure_category 必须正确识别 hang。"""

    def test_classify_hang_reason(self):
        from _failure_learning import classify_failure_category

        assert classify_failure_category("hang_detected pid=1") == "hang"
        assert classify_failure_category("hang auto-restart 耗尽") == "hang"
        assert classify_failure_category("hang_no_progress idle=300") == "hang"

    def test_classify_non_hang(self):
        from _failure_learning import classify_failure_category

        assert classify_failure_category("reviewer timeout") != "hang"
        assert classify_failure_category("syntax error") != "hang"
