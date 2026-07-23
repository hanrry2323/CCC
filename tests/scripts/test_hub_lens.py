"""Hub 只读透镜 + resolve_tool_mode 业务仓旁路收死。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chat_server import config  # noqa: E402
from chat_server.services import hub_lens  # noqa: E402


def test_resolve_tool_mode_default_engineer_on_business_project():
    assert config.resolve_tool_mode("engineer", project_id="ccc-demo") == "engineer"
    assert (
        config.resolve_tool_mode(
            None, user_text="请开工程师模式", project_id="ccc-demo"
        )
        == "engineer"
    )
    assert config.resolve_tool_mode("discuss", project_id="ccc-demo") == "discuss"
    assert config.resolve_tool_mode("engineer", project_id="ccc") == "engineer"
    assert config.resolve_tool_mode(None, project_id="") == "engineer"


def test_hub_lens_board_counts(tmp_path: Path):
    board = tmp_path / ".ccc" / "board"
    for col in ("planned", "in_progress"):
        (board / col).mkdir(parents=True)
    work = board / "in_progress" / "demo-w1.jsonl"
    work.write_text(
        json.dumps({"id": "demo-w1", "title": "在飞示例"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (board / "planned" / "demo-w0.jsonl").write_text(
        json.dumps({"id": "demo-w0", "title": "计划中"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    data = hub_lens.collect_board(tmp_path, project_id="demo")
    assert data["ok"] is True
    assert data["counts"]["in_progress"] == 1
    assert data["counts"]["planned"] == 1
    assert data["inflight_total"] == 2
    ids = {x["id"] for x in data["inflight"]}
    assert "demo-w1" in ids
    text = hub_lens.format_board_for_prompt(data)
    assert "demo-w1" in text
    assert "live board" in text.lower() or "Hub live board" in text


def test_hub_lens_file_and_tree(tmp_path: Path):
    (tmp_path / "src").mkdir()
    f = tmp_path / "src" / "hello.txt"
    f.write_text("hello lens\n", encoding="utf-8")
    tree = hub_lens.collect_tree(tmp_path, project_id="demo", path="", depth=2)
    assert tree["ok"] is True
    paths = {e["path"] for e in tree["entries"]}
    assert "src" in paths or any(p.startswith("src") for p in paths)
    file_data = hub_lens.collect_file(
        tmp_path, project_id="demo", path="src/hello.txt"
    )
    assert "hello lens" in file_data["content"]
    with pytest.raises(ValueError):
        hub_lens.collect_file(tmp_path, project_id="demo", path="../etc/passwd")


def test_hub_lens_grep(tmp_path: Path):
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    hits = hub_lens.collect_grep(tmp_path, project_id="demo", q="def foo")
    assert hits["ok"] is True
    assert hits["count"] >= 1
    assert any("foo" in h["text"] for h in hits["hits"])


def test_hub_lens_locate_aggregates_by_file(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(
        "def transfer():\n    pass\n# transfer helper\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("transfer_once()\n", encoding="utf-8")
    data = hub_lens.collect_locate(tmp_path, project_id="demo", q="transfer", limit=10)
    assert data["ok"] is True
    assert data["file_count"] >= 1
    paths = [f["path"] for f in data["files"]]
    assert "src/a.py" in paths
    top = data["files"][0]
    assert top["hit_count"] >= 1
    assert top["previews"]
    assert "相对" in (data.get("hint") or "")


def test_discuss_discipline_mentions_lens():
    assert "ccc-hub-lens" in config.DISCUSS_TOOL_DISCIPLINE
    assert "locate" in config.DISCUSS_TOOL_DISCIPLINE
    assert "ssh" in config.DISCUSS_TOOL_DISCIPLINE.lower()
