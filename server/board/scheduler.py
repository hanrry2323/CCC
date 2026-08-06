"""看板定时重导出入口 — 复用 T3 board.export。

扫描 `docs/dispatch/` → 聚合 → 写 `web/data/board.js`。
支持 --once（单次）和 --watch（持续轮询）两种模式。

用法：
    $PYTHON_BIN -m server.board.scheduler --once                    # 单次导出后退出
    $PYTHON_BIN -m server.board.scheduler --watch                   # 持续模式（默认每60秒轮询）
    $PYTHON_BIN -m server.board.scheduler --watch --interval 300    # 每5分钟轮询

定时默认只读：重导出只写 board.js，不产生任何业务动作/派发。
失败时保留旧 board.js + 记日志，不中断、不产生脏数据。
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from server.board.export import export_board
from server.board.loader import load_dispatch_cards

logger = logging.getLogger("ccc.board.scheduler")

DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_DISPATCH_DIR = "docs/dispatch"
DEFAULT_OUTPUT = "server/web/data/board.js"

# 临时文件后缀（与输出同目录，rename 原子替换）
_TMP_SUFFIX = ".board.js.tmp"


def export_safe(
    dispatch_dir: str,
    output_path: str,
) -> bool:
    """安全导出：先写临时文件，成功再 rename 覆盖旧文件。

    失败时保留旧 board.js + 记日志；不中断、不产生脏数据。
    导出前尝试自动 git sync（与 Engine 同策略），使看板尽快看见新 push 的卡。
    """
    try:
        try:
            from server.git_sync import auto_pull_enabled, resolve_repo_root, sync_origin_main

            if auto_pull_enabled():
                sync_origin_main(resolve_repo_root(dispatch_dir))
        except Exception:
            logger.exception("export 前 git sync 失败，继续用本地卡导出")

        # 定时执行自动归档：关闭 >6 个月卡自动移入 docs/archive/ccc-tasks/<project>/
        try:
            from server.board.archive import archive_old_cards
            archived = archive_old_cards(dispatch_dir)
            if archived:
                logger.info("automatically archived %d old cards: %s", len(archived), archived)
        except Exception:
            logger.exception("automatic archiving failed, proceeding with export")

        items = load_dispatch_cards(dispatch_dir)
        output = Path(output_path)
        tmp = output.with_suffix(_TMP_SUFFIX)
        export_board(items, tmp)
        tmp.replace(output)
        logger.info("exported %d cards -> %s", len(items), output_path)
        return True
    except Exception:
        logger.exception("export failed, keeping old board.js")
        # 清理残留临时文件
        tmp_path = Path(output_path).with_suffix(_TMP_SUFFIX)
        if tmp_path.is_file():
            tmp_path.unlink()
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-board-scheduler",
        description="看板定时重导出：扫描任务卡 → 聚合 → 写 board.js（默认只读，不产生业务动作）",
    )
    parser.add_argument("--once", action="store_true", help="单次导出后退出")
    parser.add_argument("--watch", action="store_true", help="持续轮询模式")
    parser.add_argument(
        "--dispatch-dir",
        default=DEFAULT_DISPATCH_DIR,
        help=f"任务卡目录（默认 {DEFAULT_DISPATCH_DIR}）",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"导出路径（默认 {DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"轮询间隔秒数（默认 {DEFAULT_INTERVAL_SECONDS}）",
    )
    return parser.parse_args(argv)


def run_once(dispatch_dir: str, output_path: str) -> int:
    """单次导出；失败返回 1。"""
    return 0 if export_safe(dispatch_dir, output_path) else 1


def run_watch(dispatch_dir: str, output_path: str, interval: int) -> int:
    """持续轮询模式：每 interval 秒执行一次导出。"""
    logger.info("看板定时重导出启动（轮询间隔 %ds）", interval)
    while True:
        export_safe(dispatch_dir, output_path)
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    if args.watch:
        return run_watch(args.dispatch_dir, args.output, args.interval)
    return run_once(args.dispatch_dir, args.output)


if __name__ == "__main__":
    sys.exit(main())
