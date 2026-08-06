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
