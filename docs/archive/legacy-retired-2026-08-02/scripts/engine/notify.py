"""engine/notify.py — 非阻塞 macOS 桌面通知。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块，零内部依赖
（仅 stdlib + _executor._sanitized_env）。原 ccc-engine.py:624-638
_ccc_notify 函数迁移到此处。

使用：
    from engine.notify import ccc_notify
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from _executor import _sanitized_env

_log = logging.getLogger("ccc.engine.notify")

NOTIFY_SCRIPT = Path(__file__).resolve().parent.parent / "ccc-notify.sh"


def ccc_notify(title: str, message: str) -> None:
    """非阻塞 macOS 桌面通知（Engine 主循环不等待）。"""
    if not NOTIFY_SCRIPT.is_file():
        _log.warning("notify 跳过: %s 不存在", NOTIFY_SCRIPT)
        return
    try:
        subprocess.Popen(
            ["bash", str(NOTIFY_SCRIPT), title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=_sanitized_env(),
        )
    except OSError as exc:
        _log.warning("notify 失败: %s", exc)
