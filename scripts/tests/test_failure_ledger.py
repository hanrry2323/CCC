"""tests for failure ledger + invent/queue-consumer control"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import _ccc_control as ctrl  # noqa: E402
import _failure_ledger as fl  # noqa: E402


@pytest.fixture()
def control_home(tmp_path, monkeypatch):
    monkeypatch.setattr(ctrl, "CONTROL_DIR", tmp_path)
    monkeypatch.setattr(ctrl, "CONTROL_FILE", tmp_path / "control.json")
    monkeypatch.setattr(ctrl, "DISABLED_SENTINEL", tmp_path / "DISABLED")
    monkeypatch.delenv("CCC_FOREGROUND", raising=False)
    return tmp_path


def test_invent_mode_allows_engine_and_invent(control_home):
    ctrl.set_mode("invent", reason="t")
    assert ctrl.may_start_engine() is True
    assert ctrl.may_invent() is True
    assert ctrl.may_start_ui() is True
    assert ctrl.is_enabled() is False


def test_enabled_is_queue_consumer_not_invent(control_home):
    ctrl.set_mode("enabled", reason="t")
    assert ctrl.may_start_engine() is True
    assert ctrl.may_invent() is False


def test_record_and_read_failures(tmp_path):
    ws = tmp_path / "proj"
    (ws / ".ccc" / "reports").mkdir(parents=True)
    result = ws / ".ccc" / "reports" / "t1.result.json"
    result.write_text('{"stderr":"boom line1\\nboom line2"}\n', encoding="utf-8")

    fl.record_failure(
        ws,
        task_id="t1",
        role="reviewer",
        reason="verdict missing",
        phase=1,
        from_col="testing",
        exit_code=1,
    )
    path = fl.failures_path(ws)
    assert path.is_file()
    rows = fl.read_failures(ws, last=5)
    assert len(rows) == 1
    assert rows[0]["task_id"] == "t1"
    assert rows[0]["role"] == "reviewer"
    assert rows[0]["stderr_path"] == ".ccc/reports/t1.result.json"
    assert "boom" in (rows[0].get("stderr_tail") or "")


def test_infer_role():
    assert fl.infer_role_from_reason("reviewer 未产出 verdict") == "reviewer"
    assert fl.infer_role_from_reason("product_role 连续失败") == "product"
