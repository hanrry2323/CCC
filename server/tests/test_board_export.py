"""test_board_export — 导出 board.js 可被页面读取（file:// 变量注入）。"""

from __future__ import annotations

import json
from pathlib import Path

from server.board.export import build_board_data, export_board
from server.board.models import BoardItem

PREFIX = "window.BOARD_DATA = "


def _items() -> list[BoardItem]:
    return [
        BoardItem(
            id="T1",
            title="示例任务",
            state="待分派",
            project="PRJ-X",
            executor="执行体",
            dispatched_at="2026-08-01",
            written_at="2026-08-02",
            reject_count=0,
        )
    ]


def _extract_payload(text: str) -> dict[str, object]:
    assert text.startswith(PREFIX)
    payload = text[len(PREFIX):].rstrip().rstrip(";")
    return json.loads(payload)


class TestExportBoard:
    """导出文件可解析 + 变量注入前缀。"""

    def test_export_parseable(self, tmp_path: Path) -> None:
        out = tmp_path / "board.js"
        export_board(_items(), out)
        text = out.read_text(encoding="utf-8")
        data = _extract_payload(text)
        assert "states" in data
        assert "views" in data
        assert {"realtime", "recent", "by_project"} <= set(data["views"].keys())
        assert "roadmap" in data

    def test_export_creates_parent_dir(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "data" / "board.js"
        export_board(_items(), out)
        assert out.is_file()


class TestBuildBoardData:
    """聚合数据结构完整。"""

    def test_roundtrip(self) -> None:
        data = build_board_data(_items())
        assert data["states"]["待分派"] == 1
        assert data["views"]["recent"][0]["id"] == "T1"
        assert data["views"]["by_project"][0]["project"] == "PRJ-X"
        assert "overview" in data["roadmap"]
        assert "by_project" in data["roadmap"]
        assert "project_detail" in data["roadmap"]
        assert data["roadmap"]["overview"][0]["bucket"] == "未开发"
