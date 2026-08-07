"""运行时卡状态 sidecar 测试（主树干净化地基）。"""

from __future__ import annotations

from pathlib import Path

from server.engine.runtime_state import read_card_state, write_card_state


def test_write_and_read_last_wins(tmp_path: Path) -> None:
    write_card_state(tmp_path, "xy001", state="执行中", retry_count=0)
    write_card_state(tmp_path, "xy001", state="已回写", retry_count=1, reason="超时重试")
    write_card_state(tmp_path, "xy002", state="打回", reason="缺测试")

    rt = read_card_state(tmp_path)
    assert rt["xy001"]["state"] == "已回写"
    assert rt["xy001"]["retry_count"] == 1
    assert rt["xy001"]["reason"] == "超时重试"
    assert rt["xy002"]["state"] == "打回"
    assert rt["xy002"]["reason"] == "缺测试"


def test_redispatch_marker(tmp_path: Path) -> None:
    write_card_state(tmp_path, "xy003", state="待分派", retry_count=0, redispatch="2026-08-07T00:00:00Z")
    rt = read_card_state(tmp_path)
    assert rt["xy003"]["redispatch"] == "2026-08-07T00:00:00Z"
    assert rt["xy003"]["retry_count"] == 0


def test_corrupt_line_tolerated(tmp_path: Path) -> None:
    write_card_state(tmp_path, "ok1", state="执行中")
    (tmp_path / "state" / "cards.jsonl").write_text(
        (tmp_path / "state" / "cards.jsonl").read_text(encoding="utf-8")
        + "not-json\n{\"id\": \"ok2\", \"state\": \"已回写\"}\n",
        encoding="utf-8",
    )
    rt = read_card_state(tmp_path)
    assert rt["ok1"]["state"] == "执行中"
    assert rt["ok2"]["state"] == "已回写"


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_card_state(tmp_path / "nope") == {}
