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


def test_resolve_complexity_bumps_multi_step_smoke_small_to_medium():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "v1.3.21 单机三件套回归冒烟",
        "goal": "验证 Data Engine + Order Gateway + 单测",
        "complexity": "small",
        "acceptance": [
            "DRY_RUN=true .venv/bin/python scripts/startup_check.py --strict --env paper",
            ".venv/bin/python -m pytest tests/ -q",
            "DRY_RUN=true .venv/bin/python -m src.core.data_engine 启停",
            "DRY_RUN=true .venv/bin/python -m src.core.order_gateway 启停",
        ],
    }
    assert tg.resolve_complexity(body) == "medium"


def test_resolve_complexity_keeps_true_small_single_file():
    from chat_server.services import transfer_gate as tg

    body = {
        "title": "写入并提交 README 备忘",
        "goal": "单文件 stamp",
        "complexity": "small",
        "acceptance": ["README.md 含 stamp 并已 commit"],
    }
    assert tg.resolve_complexity(body) == "small"


def test_fanout_allows_multi_work_for_regression_even_if_small():
    from _product_fanout import detect_write_commit_oversplit

    epic = {
        "title": "v1.3.21 单机三件套回归冒烟",
        "description": "startup_check + pytest + data_engine + order_gateway",
        "complexity": "small",
    }
    kids = [
        {"title": "环境自检 startup_check", "description": "跑 startup_check"},
        {"title": "核心单测 pytest", "description": "跑 pytest"},
    ]
    assert detect_write_commit_oversplit(kids, epic=epic) is None


def test_fanout_still_blocks_oversplit_for_write_commit_small():
    from _product_fanout import detect_write_commit_oversplit

    epic = {
        "title": "写入并提交 flow-smoke",
        "description": "flow-smoke 单文件",
        "complexity": "small",
    }
    kids = [
        {"title": "写入 flow-smoke.md", "description": "写入文件"},
        {"title": "提交 git commit", "description": "只 commit"},
    ]
    err = detect_write_commit_oversplit(kids, epic=epic)
    assert err and "oversplit" in err


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
