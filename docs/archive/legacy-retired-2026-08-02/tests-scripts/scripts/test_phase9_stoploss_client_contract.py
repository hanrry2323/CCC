"""Phase9 Desktop stopLossHint client contract (no GUI)."""

from __future__ import annotations


def desktop_stop_loss_hint(*, user_stage: str | None, works: list[dict], title: str) -> str | None:
    """Mirror AppModel rule: failed stage or any abnormal work → hint string."""
    failed = (user_stage or "") == "failed"
    any_abnormal = any((w.get("status") or "") == "abnormal" for w in works)
    if not failed and not any_abnormal:
        return None
    t = (title or "任务").strip() or "任务"
    return f"编排异常：{t} · 点开运维或看板止损"


def test_hint_from_failed_stage():
    hint = desktop_stop_loss_hint(
        user_stage="failed", works=[], title="Epic Fail"
    )
    assert hint is not None
    assert "止损" in hint
    assert "Epic Fail" in hint


def test_hint_from_abnormal_work():
    hint = desktop_stop_loss_hint(
        user_stage="running",
        works=[{"status": "abnormal", "id": "w1"}],
        title="X",
    )
    assert hint is not None
    assert "止损" in hint


def test_no_hint_when_healthy():
    assert (
        desktop_stop_loss_hint(
            user_stage="done",
            works=[{"status": "released"}],
            title="Ok",
        )
        is None
    )
