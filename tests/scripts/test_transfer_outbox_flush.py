"""transfer outbox flush — sidecar 后台投递，不依赖 Desktop 开着。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from chat_server.services import transfer_outbox_flush as flush


def _item(**kwargs):
    base = {
        "client_request_id": "crid-1",
        "project_id": "ccc-demo",
        "thread_id": "ccc-demo::main",
        "title": "t",
        "goal": "g",
        "acceptance": ["a"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
        "plan_md": "# p",
        "complexity": "small",
        "attempts": 0,
    }
    base.update(kwargs)
    return base


def test_flush_once_empty(tmp_path: Path):
    p = tmp_path / "transfer-outbox.json"
    summary = flush.flush_once(path=p)
    assert summary["pending"] == 0
    assert summary["delivered"] == 0


def test_flush_once_delivers_and_removes(tmp_path: Path):
    p = tmp_path / "transfer-outbox.json"
    p.write_text(json.dumps([_item()]), encoding="utf-8")

    with patch.object(
        flush,
        "_post_transfer",
        return_value=(True, "epic-1", {"ok": True, "epic_id": "epic-1"}),
    ):
        summary = flush.flush_once(path=p)

    assert summary["delivered"] == 1
    assert summary["pending"] == 0
    assert flush.load_outbox(p) == []


def test_flush_once_retries_on_transient(tmp_path: Path):
    p = tmp_path / "transfer-outbox.json"
    p.write_text(json.dumps([_item(attempts=0)]), encoding="utf-8")

    with patch.object(
        flush, "_post_transfer", return_value=(False, "timeout", {})
    ):
        summary = flush.flush_once(path=p)

    assert summary["delivered"] == 0
    assert summary["pending"] == 1
    left = flush.load_outbox(p)
    assert len(left) == 1
    assert left[0]["attempts"] == 1


def test_flush_once_exhausts(tmp_path: Path):
    p = tmp_path / "transfer-outbox.json"
    p.write_text(
        json.dumps([_item(attempts=flush.MAX_ATTEMPTS)]), encoding="utf-8"
    )

    with patch.object(
        flush, "_post_transfer", return_value=(False, "still_down", {})
    ) as mock_post:
        summary = flush.flush_once(path=p)

    mock_post.assert_not_called()
    assert summary["failed"] == 1
    assert summary["pending"] == 0
    assert flush.load_outbox(p) == []
    failed = flush.load_failed(flush.failed_path(p))
    assert len(failed) == 1
    assert failed[0]["client_request_id"] == "crid-1"


def test_flush_once_exhaust_on_retry_writes_failed(tmp_path: Path):
    p = tmp_path / "transfer-outbox.json"
    p.write_text(
        json.dumps([_item(attempts=flush.MAX_ATTEMPTS - 1)]), encoding="utf-8"
    )

    with patch.object(
        flush, "_post_transfer", return_value=(False, "timeout", {})
    ):
        summary = flush.flush_once(path=p)

    assert summary["failed"] == 1
    assert summary["pending"] == 0
    assert flush.load_outbox(p) == []
    assert len(flush.load_failed(flush.failed_path(p))) == 1
