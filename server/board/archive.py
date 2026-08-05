"""任务卡历史归档逻辑。

提供 6 个月卡自动移入 docs/archive/ccc-tasks/<project>/ 的逻辑。
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import date
from pathlib import Path

from server.board.loader import get_archive_dir, load_dispatch_cards
from server.board.models import base_state

logger = logging.getLogger("ccc.board.archive")


def archive_old_cards(dispatch_dir: Path | str, today: date | None = None) -> list[str]:
    """将关闭超过 6 个月的任务卡移到 docs/archive/ccc-tasks/<project>/。

    返回被归档的任务卡 ID 列表。
    """
    if today is None:
        today = date.today()

    dispatch_path = Path(dispatch_dir)
    if not dispatch_path.is_dir():
        logger.warning("dispatch directory %s does not exist, skip archive", dispatch_dir)
        return []

    # 加载所有的任务卡，需要包括已归档的（以免重复 mv）
    items = load_dispatch_cards(dispatch_path, include_archived=True)
    archived_ids: list[str] = []

    for item in items:
        # 如果已经标记为归档，跳过
        if item.archived:
            continue

        # 必须是已关闭状态
        if base_state(item.state) != "已关闭":
            continue

        # 优先使用写回日期，否则使用分派日期
        close_date_str = item.written_at
        if close_date_str == "未知" or not close_date_str:
            close_date_str = item.dispatched_at

        if close_date_str == "未知" or not close_date_str:
            continue

        try:
            close_date = date.fromisoformat(close_date_str)
        except ValueError:
            continue

        # 计算月份差
        diff_months = (today.year - close_date.year) * 12 + (today.month - close_date.month)
        is_old = False
        if diff_months > 6:
            is_old = True
        elif diff_months == 6:
            is_old = today.day >= close_date.day

        if not is_old:
            continue

        # 匹配文件（支持平铺或单层子目录）
        # 文件命名格式通常是 {id}.md 或 {id}-*.md
        glob_patterns = [
            f"{item.id}.md",
            f"{item.id}-*.md",
            f"*/{item.id}.md",
            f"*/{item.id}-*.md",
        ]
        src_file = None
        for pattern in glob_patterns:
            matches = list(dispatch_path.glob(pattern))
            if matches:
                src_file = matches[0]
                break

        if src_file is None or not src_file.is_file():
            continue

        project = item.project.lower() if item.project else "unclassified"
        if project == "未知" or not project:
            project = "unclassified"

        archive_base = get_archive_dir(dispatch_path)
        dest_dir = archive_base / project
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / src_file.name

        # 使用 git mv 移动文件，若失败则用 shutil.move 兜底
        logger.info("archiving card %s (%s) -> %s", item.id, src_file.name, dest_file)
        try:
            subprocess.run(
                ["git", "mv", str(src_file), str(dest_file)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            shutil.move(str(src_file), str(dest_file))

        archived_ids.append(item.id)

    if archived_ids:
        # 移走文件后，需要再次触发重构索引，这样索引中路径才会更新，且 archived 会被置为 True
        logger.info("rebuilding index after archiving %d cards", len(archived_ids))
        load_dispatch_cards(dispatch_path, include_archived=True)

    return archived_ids


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="ccc-board-archive",
        description="手动触发任务卡归档：将关闭 >6 个月的任务卡移到 docs/archive/ccc-tasks/<project>/",
    )
    parser.add_argument(
        "--dispatch-dir",
        default="docs/dispatch",
        help="任务卡目录（默认 docs/dispatch）",
    )
    parser.add_argument(
        "--today",
        help="模拟今天的日期，格式 YYYY-MM-DD（测试用）",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    simulated_today = None
    if args.today:
        try:
            simulated_today = date.fromisoformat(args.today)
        except ValueError:
            print("错误：--today 日期格式必须是 YYYY-MM-DD")
            return 1

    archived = archive_old_cards(args.dispatch_dir, simulated_today)
    print(f"归档运行完成。成功归档 {len(archived)} 张任务卡: {archived}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
