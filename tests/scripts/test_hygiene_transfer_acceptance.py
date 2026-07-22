#!/usr/bin/env python3
"""acceptance path extraction + transfer hygiene executor coerce."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_paths_from_bullets_skips_exclude_context():
    from _acceptance_gate import _paths_from_bullets

    bullets = [
        "白名单：须提交 `.ccc/board/abnormal/foo.jsonl`",
        "显式排除：`.ccc/warnings.json`（Engine 状态文件）、`src/`、`tests/`",
        "禁止入 `.ccc/board/on-hold/`",
        "交付 `.ccc/state.md` 入本次 commit",
    ]
    paths = _paths_from_bullets(bullets)
    assert ".ccc/board/abnormal/foo.jsonl" in paths
    assert ".ccc/state.md" in paths
    assert ".ccc/warnings.json" not in paths
    assert "src/" not in paths and not any(p.startswith("src") for p in paths)
    assert not any("on-hold" in p for p in paths)


def test_resolve_executor_ops_opencode_becomes_python():
    from chat_server.services import transfer_gate as tg

    assert (
        tg.resolve_executor_intent(
            {"pipeline": "ops", "executor_intent": "opencode", "title": "x"}
        )
        == "python"
    )
    assert (
        tg.resolve_executor_intent(
            {
                "pipeline": "dev",
                "executor_intent": "opencode",
                "title": "回收 abnormal 产物并单 commit",
            }
        )
        == "python"
    )
    # 真写码仍可 opencode
    assert (
        tg.resolve_executor_intent(
            {"pipeline": "dev", "executor_intent": "opencode", "title": "加登录页"}
        )
        == "opencode"
    )


def test_board_ops_scope_allows_ccc_artifacts_not_src():
    from board.roles.board_ops import scope_is_board_only

    assert scope_is_board_only(
        [
            {
                "phase": 1,
                "scope": [".ccc/board/abnormal/", ".ccc/plans/", ".ccc/reports/"],
            }
        ]
    )
    assert not scope_is_board_only(
        [{"phase": 1, "scope": [".ccc/board/", "src/app.py"]}]
    )
