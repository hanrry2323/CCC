"""Tests for board garbage classification and regress eligibility."""

from __future__ import annotations

from pathlib import Path

from _board_garbage import (
    hard_quarantine_garbage,
    is_garbage_board_card,
    is_regress_eligible,
)


def test_l3b_keep_not_garbage():
    assert not is_garbage_board_card("p0-momentum-edge-close-l3b-adf9e247-w1")
    assert not is_garbage_board_card("testnet-40bps-paper-strategy-l3b-04f14509")


def test_new_momentum_cost_edge_epic_not_garbage():
    """前缀误杀回归：新业务 epic 不得因旧 id 子串被 skip。"""
    assert not is_garbage_board_card("p0-momentum-cost-edge-close-5f90684d")
    assert is_garbage_board_card("p0-momentum-cost-edge-close-d6df424d")
    assert is_garbage_board_card("p0-momentum-edge-close-272fb4ce-w1")


def test_regression_and_probe_are_garbage():
    assert is_garbage_board_card("regression-ccc-v0-63-desktop-loop-probe-x-20260729-1")
    assert is_garbage_board_card("ccc-open-intent-r10-c18b830d-w1")
    assert is_garbage_board_card("qb-biz-small-1784574086-16035-w1")
    assert is_garbage_board_card(
        "layer1-v2-966d70fa-w1",
        {"title": "写入 Layer1 文档戳记 v2"},
    )


def test_regress_eligible_skips_hidden_and_garbage():
    assert not is_regress_eligible({"id": "x", "ui_hidden": True})
    assert not is_regress_eligible({"id": "regression-foo-1", "ui_hidden": False})
    assert is_regress_eligible(
        {"id": "p0-momentum-edge-close-l3b-adf9e247-w1", "ui_hidden": False}
    )


def test_hard_quarantine_moves_off_board(tmp_path: Path):
    board = tmp_path / ".ccc" / "board"
    for col in ("backlog", "released", "planned"):
        (board / col).mkdir(parents=True)
    tid = "regression-ccc-open-intent-r7-x"
    (board / "backlog" / f"{tid}.jsonl").write_text(
        '{"id":"%s","title":"回归探针","card_kind":"epic","split_status":"pending"}\n'
        % tid,
        encoding="utf-8",
    )
    keep = "p0-momentum-edge-close-l3b-adf9e247-w1"
    (board / "released" / f"{keep}.jsonl").write_text(
        '{"id":"%s","title":"L3b","card_kind":"work"}\n' % keep,
        encoding="utf-8",
    )
    # non-keep released stamp
    stamp = "layer1-v2-966d70fa-w1"
    (board / "released" / f"{stamp}.jsonl").write_text(
        '{"id":"%s","title":"戳记","card_kind":"work"}\n' % stamp,
        encoding="utf-8",
    )
    out = hard_quarantine_garbage(
        tmp_path,
        keep_ids={keep},
        also_empty_released=True,
    )
    assert tid in out["ids"]
    assert stamp in out["ids"]
    assert keep not in out["ids"]
    assert not (board / "backlog" / f"{tid}.jsonl").exists()
    assert (tmp_path / ".ccc" / "quarantines" / tid / "board-purge" / "backlog.jsonl").is_file()
    assert (board / "released" / f"{keep}.jsonl").is_file()
