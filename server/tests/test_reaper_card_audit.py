"""reaper 三方对账测试（v2.0 P4.2）。

覆盖差异分类矩阵（docs/notes/2026-09-07-reaper-report.md §2）：
card_missing_on_board / board_orphan / state_drift_disk_vs_board /
branch_orphan / branch_missing / branch_merged_uncleaned / branch_card_state_conflict。
另覆盖：纯解析边界、跨仓 codex 分支关联、ledger 落账、看板不可用 fail-closed、
launchd 安装模板替换。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from server.ops.board_fetch import _parse_auth_file
from server.ops.card_status import (
    BRANCH_OK_STATES,
    base_state,
    branch_name,
    card_id_of_branch,
    parse_card,
    scan_dispatch,
)
from server.ops.ledger_writer import load_active_snapshot, record_reaper_diffs, write_active_snapshot
from server.ops.reconcile import SEVERITY, classify_diffs


def _card(path: Path, card_id: str, *, title: str = "test", state: str = "待分派") -> Path:
    p = path / f"{card_id}-{title}.md"
    body = f"# 任务卡 {card_id}\n\n> 关联：- · 执行体：DSH · 验收：DSH · 状态：{state} · 派发：engine · 项目：{card_id[:2]} · 日期：2026-09-07\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ── 分类矩阵 ─────────────────────────────────────────────


def test_card_missing_on_board(tmp_path: Path) -> None:
    card = _card(tmp_path, "xy001", state="待分派")
    parsed = parse_card(card)
    diffs = classify_diffs([parsed], [], [])
    codes = [d["code"] for d in diffs]
    assert "card_missing_on_board" in codes
    rec = next(d for d in diffs if d["code"] == "card_missing_on_board")
    assert rec["card_id"] == "xy001"
    assert rec["severity"] == "warn"


def test_board_orphan(tmp_path: Path) -> None:
    cards = [_card(tmp_path, "xy001", state="待分派")]
    parsed = [parse_card(c) for c in cards]
    # 看板含一张磁盘无对应的卡
    board = [{"id": "ghost999", "state": "待分派", "board_column": "待分派"}]
    diffs = classify_diffs(parsed, board, [])
    codes = [d["code"] for d in diffs]
    assert "board_orphan" in codes
    rec = next(d for d in diffs if d["code"] == "board_orphan")
    assert rec["card_id"] == "ghost999"
    assert rec["severity"] == "severe"


def test_state_drift_disk_vs_board(tmp_path: Path) -> None:
    card = _card(tmp_path, "xy002", state="已关闭")
    parsed = [parse_card(card)]
    board = [{"id": "xy002", "state": "已回写", "board_column": "已回写"}]
    diffs = classify_diffs(parsed, board, [])
    codes = [d["code"] for d in diffs]
    assert "state_drift_disk_vs_board" in codes
    rec = next(d for d in diffs if d["code"] == "state_drift_disk_vs_board")
    assert rec["board_state"] == "已回写"
    assert rec["card_id"] == "xy002"
    assert rec["severity"] == "warn"


def test_branch_orphan(tmp_path: Path) -> None:
    cards = [_card(tmp_path, "xy003", state="已关闭")]
    parsed = [parse_card(c) for c in cards]
    board = [{"id": "xy003", "state": "已关闭", "board_column": "已关闭"}]
    branches = [
        {"branch": "codex/xy999-something", "merged": False},
        {"branch": "codex/xy003-closed", "merged": True},
    ]
    diffs = classify_diffs(parsed, board, branches)
    codes = [d["code"] for d in diffs]
    assert "branch_orphan" in codes  # ghost301 无对应卡
    orphan = next(d for d in diffs if d["code"] == "branch_orphan")
    assert orphan["card_id"] == "xy999"
    assert orphan["branch"] == "codex/xy999-something"
    # xy003 已关闭且分支仍在 → 已合并未删
    assert "branch_merged_uncleaned" in codes


def test_branch_missing_active_card(tmp_path: Path) -> None:
    card = _card(tmp_path, "xy004", state="已回写")
    parsed = [parse_card(card)]
    board = [{"id": "xy004", "state": "已回写", "board_column": "机审"}]
    diffs = classify_diffs(parsed, board, [])
    codes = [d["code"] for d in diffs]
    assert "branch_missing" in codes
    rec = next(d for d in diffs if d["code"] == "branch_missing")
    assert rec["card_id"] == "xy004"
    assert rec["severity"] == "severe"


def test_branch_merged_uncleaned_closed_card(tmp_path: Path) -> None:
    card = _card(tmp_path, "xy005", state="已关闭")
    parsed = [parse_card(card)]
    board = [{"id": "xy005", "state": "已关闭", "board_column": "已关闭"}]
    branches = [{"branch": "codex/xy005-merged", "merged": True}]
    diffs = classify_diffs(parsed, board, branches)
    codes = [d["code"] for d in diffs]
    assert "branch_merged_uncleaned" in codes
    rec = next(d for d in diffs if d["code"] == "branch_merged_uncleaned")
    assert rec["card_id"] == "xy005"
    assert rec["severity"] == "warn"


def test_branch_card_state_conflict_void_card(tmp_path: Path) -> None:
    card = _card(tmp_path, "xy006", state="作废")
    parsed = [parse_card(card)]
    board = [{"id": "xy006", "state": "作废", "board_column": "作废"}]
    branches = ["codex/xy006-void"]
    diffs = classify_diffs(parsed, board, branches)
    codes = [d["code"] for d in diffs]
    assert "branch_card_state_conflict" in codes
    rec = next(d for d in diffs if d["code"] == "branch_card_state_conflict")
    assert rec["card_id"] == "xy006"
    assert rec["severity"] == "severe"


def test_clean_no_diffs(tmp_path: Path) -> None:
    cards = [
        _card(tmp_path, "xy010", title="a", state="待分派"),
        _card(tmp_path, "xy011", title="b", state="执行中"),
    ]
    parsed = [parse_card(c) for c in cards]
    board = [
        {"id": "xy010", "state": "待分派", "board_column": "待分派"},
        {"id": "xy011", "state": "执行中", "board_column": "执行中"},
    ]
    branches = ["codex/xy010-a", "codex/xy011-b"]
    assert classify_diffs(parsed, board, branches) == []


def test_multi_branch_any_satisfies(tmp_path: Path) -> None:
    """同一卡跨仓多 codex 分支，任一存在即不触发 branch_missing。"""
    card = _card(tmp_path, "xy012", state="已回写")
    parsed = [parse_card(card)]
    board = [{"id": "xy012", "state": "已回写", "board_column": "已回写"}]
    branches = ["codex/xy012-a", "codex/xy012-b"]
    assert classify_diffs(parsed, board, branches) == []


# ── 纯解析边界 ─────────────────────────────────────────────


def test_parse_card_states(tmp_path: Path) -> None:
    for state in ("待分派", "执行中", "已回写", "已关闭", "打回", "作废"):
        c = _card(tmp_path, f"xy9{['待分派','执行中','已回写','已关闭','打回','作废'].index(state)}9", state=state)
        parsed = parse_card(c)
        assert parsed.state == state


def test_parse_card_bracket_variant(tmp_path: Path) -> None:
    c = _card(tmp_path, "xy020", state="打回（原因待修）")
    parsed = parse_card(c)
    assert parsed.state == "打回"
    assert parsed.state_raw == "打回（原因待修）"


def test_parse_card_broken(tmp_path: Path) -> None:
    c = _card(tmp_path, "xy021", state="待分派")
    c.write_text("# 任务卡 xy021\n> 执行体：DSH\n", encoding="utf-8")
    parsed = parse_card(c)
    assert parsed.broken is True
    assert parsed.state == "未知"


def test_branch_name_and_card_id() -> None:
    assert branch_name("docs/dispatch/xy/xy022-something.md") == "codex/xy022-something"
    assert card_id_of_branch("codex/xy022-something") == "xy022"
    assert card_id_of_branch("origin/codex/xy022-something") is None  # 只认 codex/ 前缀


def test_scan_dispatch_sorted(tmp_path: Path) -> None:
    dispatch = tmp_path / "xy"
    _card(dispatch, "xy030", state="待分派")
    _card(dispatch, "xy021", state="待分派")
    cards = scan_dispatch(tmp_path)
    # dispatch/<prefix>/<id>-<slug>.md
    assert [c.id for c in cards] == ["xy021", "xy030"]


def test_base_state_and_branch_ok_set() -> None:
    assert base_state("打回（x）") == "打回"
    assert "已关闭" not in BRANCH_OK_STATES
    assert "作废" not in BRANCH_OK_STATES
    assert "待分派" in BRANCH_OK_STATES


def test_all_codes_have_severity() -> None:
    for code in (
        "card_missing_on_board",
        "board_orphan",
        "state_drift_disk_vs_board",
        "branch_orphan",
        "branch_missing",
        "branch_merged_uncleaned",
        "branch_card_state_conflict",
    ):
        assert code in SEVERITY


# ── ledger 落账 / 快照 ─────────────────────────────────────


def test_record_reaper_diffs_append(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "audit" / "ledger.jsonl"
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(ledger))
    diffs = [{"code": "branch_missing", "severity": "severe", "card_id": "xy040", "detail": "x"}]
    n = record_reaper_diffs(diffs)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert n == 1
    assert rows[0]["action"] == "reaper_diff"
    assert rows[0]["kind"] == "reaper_diff"
    assert rows[0]["object_id"] == "xy040"
    assert rows[0]["code"] == "branch_missing"


def test_record_reaper_diffs_empty(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "audit" / "ledger.jsonl"
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(ledger))
    assert record_reaper_diffs([]) == 0
    assert not ledger.exists()


def test_write_active_snapshot(tmp_path: Path) -> None:
    diffs = [{"code": "board_orphan", "severity": "severe", "card_id": "ghost1", "detail": "x"}]
    out = tmp_path / "reaper-active.jsonl"
    n = write_active_snapshot(diffs, out)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert n == 1
    assert rows[0]["kind"] == "reaper_diff"
    assert rows[0]["code"] == "board_orphan"
    assert load_active_snapshot(out) == rows


# ── 看板不可用 fail-closed ─────────────────────────────────


def test_fetch_cards_network_unavailable(monkeypatch) -> None:
    """网络不可达 → fetch_cards 返回 None（fail-closed，不把空当一致）。"""
    monkeypatch.setenv("CCC_BOARD_URL", "http://127.0.0.1:1")
    monkeypatch.delenv("CCC_BOARD_TOKEN", raising=False)
    from server.ops import board_fetch

    # 禁 token 轮换，让低端口连接快速失败
    monkeypatch.setattr(board_fetch, "_fetch_token", lambda: "")
    assert board_fetch.fetch_cards() is None


# ── board_fetch.auth 解析 ──────────────────────────────────


def test_parse_auth_file_zh(tmp_path: Path) -> None:
    f = tmp_path / "web-auth.txt"
    f.write_text("# title\n账号: ccc\n口令: s3cret\n", encoding="utf-8")
    assert _parse_auth_file(f) == ("ccc", "s3cret")


def test_parse_auth_file_fallback_single_line(tmp_path: Path) -> None:
    f = tmp_path / "web-auth.txt"
    f.write_text("ccc:singlepass\n", encoding="utf-8")
    assert _parse_auth_file(f) == ("ccc", "singlepass")


# ── 安装脚本模板替换（纯文件生成，不加载 launchd）─────────────


def test_install_template_substitution(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    template = root / "server" / "deploy" / "com.ccc.reaper.plist"
    if not template.is_file():
        import pytest

        pytest.skip("template not present")
    target = tmp_path / "com.ccc.reaper.plist"
    script = root / "scripts" / "ops" / "install-reaper-plist.sh"
    subprocess.run(
        [
            "/bin/bash",
            str(script),
        ],
        check=True,
        env={
            "HOME": str(tmp_path),
            "CCC_REAPER_PYTHON": str(sys.executable),
            "CCC_REAPER_LOG_DIR": str(tmp_path / "logs"),
        },
    )
    text = (tmp_path / "Library" / "LaunchAgents" / "com.ccc.reaper.plist").read_text(encoding="utf-8")
    assert "$PROJECT_ROOT" not in text  # 占位符全部替换
    assert "$HOME" not in text
    assert "StartCalendarInterval" in text
    assert "<integer>6</integer>" in text and "<integer>5</integer>" in text
