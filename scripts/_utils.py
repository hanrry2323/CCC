"""_utils.py — CCC 共享工具函数 (v0.28.0+)

按 review 报告 H-003 落地：sanitize_id / now_iso 重复定义 3-4 份统一于此。

约束：
- sanitize_id: 仅保留 [a-zA-Z0-9_-]，与 _board_store.py 行为一致
- now_iso: 返回 UTC ISO 8601（统一为 Z 后缀），跨文件行为一致
- 所有脚本从此处导入（ccc-board.py / _board_store.py / ccc-board-server.py / ccc-engine.py）

v0.28.0 行为变更：
- 之前 ccc-board.py 用 Asia/Shanghai（+08:00），_board_store.py 用 UTC（Z）— 行为不一致
- 统一为 UTC（Z 后缀），与 board JSONL 协议（references/board-task-schema.md §4.4）一致
"""

from __future__ import annotations

import re
from datetime import datetime, timezone


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留 [a-zA-Z0-9_-]，防止路径遍历。

    与 v0.19+ _board_store.py 行为一致（regex + fallback "invalid"）。
    """
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"


def now_iso() -> str:
    """UTC ISO 8601 时间戳，Z 后缀（例：2026-07-12T01:23:45Z）。

    与 board-task-schema v1 §4.4 一致。所有 CCC 脚本统一使用。
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
