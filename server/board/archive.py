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


def _git_repo_root(path: Path) -> Path | None:
    """解析 path 所属 git 仓库根；非 git 仓返回 None（测试/临时目录无仓时归档可正常跑）。"""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if res.returncode != 0:
        return None
    root = res.stdout.strip()
    return Path(root) if root else None


def _git_branch(repo: Path) -> str:
    """读取当前分支；失败回退 main。"""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return res.stdout.strip() or "main"
    except (subprocess.SubprocessError, OSError):
        pass
    return "main"


def _git_commit_and_push(repo: Path, archived_ids: list[str], moved: list[Path]) -> bool:
    """归档 tar 后统一 commit + push（P0 加固：杜绝 git_sync checkout -f 恢复未落库旧文件）。

    规则：
    - 未 commit/未 push 的归档文件不回滚（保留脏现场），push 失败打 error 告警，不吞错误。
    - push 失败只告警不重试（避免循环重试），脏提交留在本地由人处理。
    - 非 git 仓 / 无远程：返回 True 且不打错误（仅 info 日志），保证测试/临时目录不破坏。
    """
    if not archived_ids or not moved:
        return True

    # 非 git 仓（如纯文件测试环境）→ 跳过 git 落库，不改语义
    if (
        not subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        == "true"
    ):
        logger.info("归档目录不在 git 仓库内，跳过 git commit/push（共 %d 张卡）", len(archived_ids))
        return True

    # 暂存被移动的卡（相对仓库根的路径）
    rel_paths = []
    for p in moved:
        try:
            rel_paths.append(str(p.resolve().relative_to(repo.resolve())))
        except ValueError:
            rel_paths.append(str(p))

    if not rel_paths:
        return True

    stamp = " ".join(sorted(archived_ids))
    msg = f"board(archive): 归档 {len(archived_ids)} 张卡 — {stamp[:120]}"
    branch = _git_branch(repo)
    try:
        # 纳入 protected_git_lock：mv + add + commit + push 全程在锁内，杜绝与
        # git_sync checkout -f / 卡合约提交 相互清扫（B3 `archive vs git_sync 对攻` 收口）。
        from server.engine.card_state_store import protected_git_lock

        with protected_git_lock(repo, blocking=True):
            subprocess.run(
                ["git", "add", "--", *rel_paths],
                cwd=str(repo),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # 无实际变更（可能已在之前批次 commit）→ 直接跳过 push
            if (
                subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).returncode
                == 0
            ):
                logger.info("归档后无待提交变更，跳过 commit/push")
                return True
            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(repo),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            logger.info("归档已 commit: %s", msg)
            # push：失败只告警，保留本地脏提交，不做循环重试
            if (
                not subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).returncode
                == 0
            ):
                logger.warning("归档目录无 origin 远程，跳过 push（commit 已留本地）")
                return True
            res = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=60,
            )
    except (subprocess.CalledProcessError, subprocess.SubprocessError, OSError) as exc:
        logger.error("归档 git mv/add/commit/push 阶段失败（保留脏现场）: %s (%s)", msg, exc)
        return False
    if res.returncode != 0:
        logger.error("归档后 git push 失败（保留本地 commit，须人工处理）: %s", res.stderr.strip()[:500])
        return False
    logger.info("归档已 push origin/%s", branch)
    return True


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
    moved_files: list[Path] = []
    repo_root: Path | None = _git_repo_root(dispatch_path)

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
        moved = False
        if repo_root is not None:
            try:
                subprocess.run(
                    ["git", "mv", str(src_file), str(dest_file)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                moved = True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.SubprocessError):
                pass
        if not moved:
            shutil.move(str(src_file), str(dest_file))

        archived_ids.append(item.id)
        moved_files.append(dest_file)

    # P0 加固：归档移完文件后统一 commit + push，杜绝 git_sync checkout -f 把归档恢复回看板。
    if archived_ids:
        if repo_root is not None:
            _git_commit_and_push(repo_root, archived_ids, moved_files)
        else:
            logger.warning("归档目录不在 git 仓库，无法落库（%d 张卡已本地移动）", len(archived_ids))

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
