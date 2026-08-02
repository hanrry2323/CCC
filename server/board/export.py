"""看板导出：把三视图 + 线路图写入 `web/data/board.js`。

以 `window.BOARD_DATA = {...}` 变量注入，页面 `<script src>` 读取，
零 fetch / 零 API，`file://` 可直接打开。

用法（函数）：
    from server.board.export import export_board

    export_board(items, Path("server/web/data/board.js"))

用法（CLI）：
    $PYTHON_BIN -m server.board.export --dispatch-dir docs/dispatch \
        --output server/web/data/board.js
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from server.board.loader import load_dispatch_cards
from server.board.models import BoardItem
from server.board.queries import (
    roadmap_by_project,
    roadmap_overview,
    roadmap_project_detail,
    state_counts,
    view_by_project,
    view_recent,
    view_realtime,
)


def build_board_data(
    items: list[BoardItem],
    now: date | None = None,
    days: int = 7,
) -> dict[str, object]:
    """聚合三视图 + 线路图三层（总览/单项目/项目线路图）+ 状态徽章数据。"""
    projects = sorted({i.project for i in items if i.project != "未知"})
    return {
        "source": "任务卡文档",
        "generated_at": date.today().isoformat(),
        "states": state_counts(items),
        "views": {
            "realtime": view_realtime(items),
            "recent": view_recent(items, now=now, days=days),
            "by_project": view_by_project(items),
        },
        "roadmap": {
            "overview": roadmap_overview(items),
            "by_project": roadmap_by_project(items),
            "project_detail": {
                project: roadmap_project_detail(items, project)
                for project in projects
            },
        },
    }


def export_board(
    items: list[BoardItem],
    output_path: Path | str,
    now: date | None = None,
    days: int = 7,
) -> None:
    """导出 `window.BOARD_DATA = {...};` 到目标文件（file:// 可开）。"""
    payload = json.dumps(
        build_board_data(items, now=now, days=days),
        ensure_ascii=False,
        indent=2,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "window.BOARD_DATA = " + payload + ";\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ccc-board-export",
        description="从任务卡导出看板静态数据 board.js",
    )
    parser.add_argument("--dispatch-dir", default="docs/dispatch", help="任务卡目录（相对仓库根）")
    parser.add_argument("--output", default="server/web/data/board.js", help="导出路径（相对仓库根）")
    args = parser.parse_args(argv)

    items = load_dispatch_cards(args.dispatch_dir)
    export_board(items, Path(args.output))
    print(f"exported {len(items)} cards -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
