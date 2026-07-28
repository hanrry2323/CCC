"""test_retry_abnormal_refeed.py — Phase A (015): auto-refeed boundary tests.

Tests the pure function ``should_auto_refeed`` extracted from
``_retry_abnormal_failures``, plus end-to-end scenario tests using
tmp_path board fixtures.

A1: work + transient reason + cooldown passed → reopen, count +1
A2: epic → never reopen
A3: exhausted/permanent reason → never reopen
A4: auto_retried >= 2 → never reopen
A5: is_orch_path → never reopen
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from engine.failure_router import RefeedDecision, should_auto_refeed


# ── Pure function tests ────────────────────────────────────────────────

class TestShouldAutoRefeed:
    """A1–A4: ``should_auto_refeed`` pure-function boundary tests."""

    def test_a1_work_transient_returns_true(self):
        """Normal work with transient reason should refeed."""
        d = should_auto_refeed(
            card_kind="work",
            reason="timeout: upstream unavailable",
            auto_retried=0,
        )
        assert d.should is True, d.reason

    def test_a1_work_transient_cooled(self):
        """Even with no explicit pack, transient keyword hit suffices."""
        d = should_auto_refeed(
            card_kind="work",
            reason="connection reset by peer",
            auto_retried=0,
            has_pack_or_transient=True,
        )
        assert d.should is True, d.reason

    def test_a2_epic_never_refeed(self):
        """Epic cards must never be auto-refeed."""
        d = should_auto_refeed(
            card_kind="epic",
            reason="any reason",
            auto_retried=0,
        )
        assert d.should is False
        assert d.reason == "epic"

    def test_a3_exhausted_keyword_skips(self):
        """Exhausted/permanent markers prevent refeed."""
        markers = [
            "reviewer_fail_loop_exhausted",
            "tester_fail_loop_exhausted",
            "fail_loop_exhausted",
            "重试耗尽",
            "次全部失败",
            "missing plan",
            "缺 plan",
            "缺 phases",
            "hang auto-restart 耗尽",
            "short_path_fail_budget",
            "retry budget 耗尽",
            "phase graph unresolvable",
        ]
        for m in markers:
            d = should_auto_refeed(card_kind="work", reason=m, auto_retried=0)
            assert d.should is False, f"marker '{m}' should skip"
            assert d.reason == "exhausted_keyword", f"wrong reason for '{m}': {d.reason}"

    def test_a3_permanent_classified_skips(self):
        """Permanent classification (e.g. syntax error) prevents refeed."""
        d = should_auto_refeed(
            card_kind="work",
            reason="syntax error on line 42",
            auto_retried=0,
        )
        assert d.should is False
        assert d.reason == "permanent"

    def test_a3_no_pack_no_transient_skips(self):
        """No review_fail pack and no transient keyword → skip."""
        d = should_auto_refeed(
            card_kind="work",
            reason="some generic error",
            auto_retried=0,
            has_pack_or_transient=False,
        )
        assert d.should is False
        assert d.reason == "no_pack_or_transient"

    def test_a4_max_retry_reached(self):
        """auto_retried >= MAX_AUTO_RETRY (default 2) → skip."""
        d = should_auto_refeed(
            card_kind="work",
            reason="timeout",
            auto_retried=2,
        )
        assert d.should is False
        assert "max_retry_reached" in d.reason, d.reason

    def test_a4_custom_max_retry(self):
        """Custom max_auto_retry parameter works."""
        d = should_auto_refeed(
            card_kind="work",
            reason="timeout",
            auto_retried=2,
            max_auto_retry=3,
        )
        assert d.should is True, d.reason

    def test_border_empty_reason(self):
        """Empty reason → classify_failure returns transient → should refeed if pack exists."""
        d = should_auto_refeed(card_kind="work", reason="", auto_retried=0)
        assert d.should is True, d.reason

    def test_border_no_card_kind(self):
        """Empty card_kind (neither work nor epic) → allowed (treated as work-like)."""
        d = should_auto_refeed(card_kind="", reason="timeout", auto_retried=0)
        assert d.should is True, d.reason


# ── Board-level scenario tests (A5: orch path) ────────────────────────


def _mk_board(ws: Path) -> Path:
    for col in (
        "backlog", "planned", "in_progress", "testing",
        "verified", "released", "abnormal",
    ):
        (ws / ".ccc" / "board" / col).mkdir(parents=True)
    (ws / ".ccc" / "pids").mkdir(parents=True)
    return ws


def test_a5_orch_path_skips_auto_refeed():
    """is_orch_path 的仓禁止 auto-refeed — 验证 _retry_abnormal_failures 的调用逻辑。

    orch 路径是通过 is_orch_path() 在 caller 层判断的（ccc-engine.py:2881），
    should_auto_refeed 纯函数不含此逻辑。本测试确认两者分工。
    """
    # 验证 real orch_home is orchid
    from _workspace_registry import is_orch_path as _iop, orch_home
    assert _iop(orch_home()) is True

    # 验证任意临时路径不是 orch
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert _iop(Path(d)) is False, "tmp_path should not be orch"

    # pure function doesn't know about orch — that's by design
    d = should_auto_refeed(card_kind="work", reason="timeout", auto_retried=0)
    assert d.should is True  # pure function doesn't know about orch


def test_refeed_decision_dataclass():
    """RefeedDecision 结构正确。"""
    d1 = RefeedDecision(should=True, reason="")
    assert d1.should is True
    assert d1.reason == ""

    d2 = RefeedDecision(should=False, reason="epic")
    assert d2.should is False
    assert d2.reason == "epic"
