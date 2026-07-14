"""_utils.py — CCC 共享工具函数 (v0.28.1+)

按 review 报告 H-003 落地：sanitize_id / now_iso 重复定义 3-4 份统一于此。

约束：
- sanitize_id: 仅保留 [a-zA-Z0-9_-]，与 _board_store.py 行为一致
- now_iso: 返回北京时间 ISO 8601（+08:00 后缀）

v0.28.1 行为变更：
- 之前 v0.28.0 统一为 UTC Z，但对齐用户所在地（中国）不便
- 从 UTC Z 改为 Asia/Shanghai +08:00
- 早期版本（v0.28.0 前）ccc-board.py 用 +08:00，_board_store.py 用 Z — 已统一
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta

# v0.28.1: 北京时间偏移常量（中国无夏令时，固定 +08:00）
_BEIJING_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def sanitize_prompt_input(text: str, max_len: int = 500) -> str:
    """净化用户提供的文本，防止 prompt injection。

    适用范围：task title/description 等用户输入插入 LLM prompt 之前。
    """
    if not text:
        return ""
    # 1. 截断
    text = str(text)[:max_len]
    # 2. 移除控制字符和 null bytes
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 3. 移除 markdown 代码块分隔符（防止逃逸）
    text = text.replace("```", "`` `")
    # 4. 移除再训练/忽略指令等注入模式（常见的中英文） — 仅在末尾出现时才移除，
    #    避免误伤正常含"你对"的文本
    text = re.sub(
        r"(?i)(忽略(以上|掉|所有).*|ignore\s+(all\s+)?(previous|above).*|"
        r"forget\s+(all\s+)?(previous|above).*)$",
        "[REDACTED]",
        text,
    )
    return text


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留 [a-zA-Z0-9_-]，防止路径遍历。

    与 v0.19+ _board_store.py 行为一致（regex + fallback "invalid"）。
    """
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"


def now_iso() -> str:
    """北京时间 ISO 8601 时间戳，+08:00 后缀（例：2026-07-12T09:23:45+08:00）。

    v0.28.1: 从 UTC Z 改为 Asia/Shanghai +08:00 以对齐用户所在地。
    以前版本（v0.28.0 及更早）可能输出 Z 或 +08:00，混合时区已统一。
    """
    return datetime.now(_BEIJING_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
