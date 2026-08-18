#!/usr/bin/env python3
"""螺旋上升 P1-2：确定性方案/里程碑进度自动修复脚本。

被 server/engine/observer.py 通过 subprocess 调用（observer 代码层保持只读，
白名单测试禁止 observer import plans 写接口）。

用法：
    python3 scripts/auto-fix-plan-progress.py <repo_root> <plan_rel_path> [project]

功能：
    1. sync_plan_progress(repo_root, plan_rel_path)  重算并回写方案进度
    2. sync_milestone_progress(project, plan_rel_path) 级联同步里程碑进度

退出码：0=修复完成/无操作，1=失败（stderr 带原因）。
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: auto-fix-plan-progress.py <repo_root> <plan_rel_path> [project]", file=sys.stderr)
        return 1
    repo_root = Path(sys.argv[1]).resolve()
    rel_path = sys.argv[2]
    project = sys.argv[3] if len(sys.argv) > 3 else "ccc"

    # 延迟 import：仅在本脚本执行时加载（observer 不 import plans）
    from server.board.plans import sync_plan_progress
    from server.board.roadmap import sync_milestone_progress

    res = sync_plan_progress(repo_root, rel_path)
    if isinstance(res, dict) and res.get("error"):
        print(f"sync_plan_progress 失败: {res['error']}", file=sys.stderr)
        return 1

    # 级联同步里程碑（方案进度变更后）
    try:
        sync_milestone_progress(project, rel_path)
    except Exception as e:  # noqa: BLE001
        print(f"sync_milestone_progress 警告: {e}", file=sys.stderr)

    progress = res.get("progress", {})
    print(f"进度已同步: {progress.get('closed', '?')}/{progress.get('total', '?')} ({progress.get('progress_pct', '?')}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
