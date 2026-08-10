"""Tests for ccc-plan parse + ready_for_merge query."""

from __future__ import annotations

import pytest

from server.board.ccc_plan import PlanError, parse_ccc_plan
from server.board.models import BoardItem
from server.board.queries import ready_for_merge


YAML_PLAN = """```ccc-plan
title: dogfood
project: ccc
slices:
  - title: Ready API
    slug: ready-for-merge-api
    acceptance:
      - "pytest -q 绿"
    whitelist: ["server/board/queries.py"]
    executor: OpenCode
  - title: Plan script
    slug: plan-to-cards-script
    acceptance:
      - "dry-run ok"
    whitelist: ["scripts/plan-to-cards.sh"]
    executor: OpenCode
```"""


def test_parse_yaml_fence_two_slices() -> None:
    plan = parse_ccc_plan(YAML_PLAN)
    assert plan.title == "dogfood"
    assert plan.project == "ccc"
    assert len(plan.slices) == 2
    assert plan.slices[0].slug == "ready-for-merge-api"
    assert plan.slices[0].acceptance == ["pytest -q 绿"]
    assert plan.slices[0].whitelist == ["server/board/queries.py"]


def test_parse_json_plan() -> None:
    raw = """
    {
      "title": "t",
      "project": "ccc",
      "slices": [{
        "title": "s",
        "slug": "one-slice",
        "acceptance": ["ok"],
        "whitelist": [],
        "executor": "OpenCode"
      }]
    }
    """
    plan = parse_ccc_plan(raw)
    assert plan.slices[0].slug == "one-slice"


def test_reject_empty_acceptance() -> None:
    with pytest.raises(PlanError, match="acceptance"):
        parse_ccc_plan(
            '{"title":"t","project":"ccc","slices":[{"title":"s","slug":"bad-slice","acceptance":[]}]}'
        )


def test_reject_qh_prefix() -> None:
    with pytest.raises(PlanError, match="qh"):
        parse_ccc_plan(
            """{"title":"t","project":"qh","slices":[{"title":"s","slug":"x","acceptance":["a"]}]}"""
        )


def test_ready_for_merge_only_audited() -> None:
    pending = BoardItem(
        id="a",
        title="p",
        state="已回写",
        project="ccc",
        machine_audit_passed=False,
    )
    ready = BoardItem(
        id="b",
        title="r",
        state="已回写",
        project="ccc",
        machine_audit_passed=True,
    )
    payload = ready_for_merge([pending, ready])
    assert payload["count"] == 1
    assert payload["cards"][0]["id"] == "b"
    assert payload["cards"][0]["board_column"] == "已回写"


def test_ready_for_merge_backlog_threshold() -> None:
    import os
    ready_items = [
        BoardItem(
            id=f"item_{i}",
            title=f"title_{i}",
            state="已回写",
            project="ccc",
            machine_audit_passed=True,
        )
        for i in range(5)
    ]
    # Default threshold is 5, count is 5 -> should trigger
    payload = ready_for_merge(ready_items)
    assert payload["count"] == 5
    assert payload["backlog_alert"] is True
    assert "warning" in payload
    assert "积压" in payload["warning"]

    # Explicit threshold as argument
    payload_explicit = ready_for_merge(ready_items, threshold=6)
    assert payload_explicit["backlog_alert"] is False
    assert "warning" not in payload_explicit

    # Threshold from environment variable CCC_BACKLOG_THRESHOLD
    os.environ["CCC_BACKLOG_THRESHOLD"] = "3"
    try:
        payload_env = ready_for_merge(ready_items)
        assert payload_env["backlog_alert"] is True
        assert payload_env["threshold"] == 3
    finally:
        os.environ.pop("CCC_BACKLOG_THRESHOLD", None)

    # Threshold from environment variable BACKLOG_THRESHOLD
    os.environ["BACKLOG_THRESHOLD"] = "10"
    try:
        payload_env2 = ready_for_merge(ready_items)
        assert payload_env2["backlog_alert"] is False
        assert payload_env2["threshold"] == 10
    finally:
        os.environ.pop("BACKLOG_THRESHOLD", None)

