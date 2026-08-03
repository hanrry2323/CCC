"""F4-2: success lessons by topic (record → read → topic match)."""
from __future__ import annotations

from pathlib import Path

from _lessons import (
    extract_topic,
    get_lessons_by_topic,
    get_recent_lessons,
    record_failure,
    record_success,
    sanitize_topic,
)


def test_extract_topic_keyword_and_tag() -> None:
    assert extract_topic("实现断线恢复与重连") == "disconnect-recovery"
    assert extract_topic("随便标题", tag="投递三态") == "delivery-tri-state"
    assert extract_topic("no-keyword-title") == sanitize_topic("no-keyword-title")


def test_record_success_append_and_get(tmp_path: Path) -> None:
    ws = tmp_path
    r1 = record_success(ws, "t-1", "disconnect", "断线恢复：先写心跳再重连")
    assert r1["topic"] == "disconnect"
    assert r1["kind"] == "success"
    path = ws / ".ccc" / "lessons" / "disconnect.md"
    assert path.is_file()
    record_success(ws, "t-2", "disconnect", "断线：退避指数增长")
    text = path.read_text(encoding="utf-8")
    assert text.count("## success ·") == 2
    assert "t-1" in text and "t-2" in text

    items = get_lessons_by_topic(ws, "disconnect", count=5)
    assert len(items) == 2
    assert {i["task_id"] for i in items} == {"t-1", "t-2"}
    assert all(i.get("kind") == "success" for i in items)


def test_get_lessons_by_topic_keyword_match(tmp_path: Path) -> None:
    ws = tmp_path
    record_success(ws, "a1", "disconnect", "ok")
    record_success(ws, "b1", "delivery", "投递三态落地")
    # title keyword → disconnect，应命中 disconnect 文件
    topic = extract_topic("修复断线问题")
    got = get_lessons_by_topic(ws, topic, count=5)
    assert len(got) >= 1
    assert got[0]["task_id"] == "a1"
    assert all(i["task_id"] != "b1" for i in got)


def test_failure_lessons_path_untouched(tmp_path: Path) -> None:
    """失败 lessons 仍走 *.json；success md 不混进 get_recent_lessons。"""
    ws = tmp_path
    record_failure(ws, "fail-1", "dev", "boom", analysis="真实分析：根因 X")
    record_success(ws, "ok-1", "disconnect", "成功经验")
    recent = get_recent_lessons(ws, count=50)
    assert any(x.get("task_id") == "fail-1" for x in recent)
    assert all(x.get("task_id") != "ok-1" for x in recent)
    assert not (ws / ".ccc" / "lessons" / "fail-1.md").exists()
    assert (ws / ".ccc" / "lessons" / "fail-1.json").is_file()
