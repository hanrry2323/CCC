"""server/engine/logpaths.py — 执行体/机审工件目录解析（叶子模块，零内部依赖）。

从 phase2 抽出（2026-09-05 深扫解环）：failure_class 自检需要 verdict 工件目录，
不应为此依赖 phase2 的私有符号；目录口径与 Engine 执行体日志同源，故独立成叶。
"""

from __future__ import annotations

import os
from pathlib import Path


def audit_log_dir(cfg: dict) -> Path:
    """机审前置工件目录；与 Engine 执行体日志目录保持同源。"""
    raw = cfg.get("EXECUTOR_LOG_DIR") or cfg.get("LOG_DIR") or os.environ.get("EXECUTOR_LOG_DIR")
    return Path(str(raw)).expanduser() if raw else Path.home() / ".ccc" / "logs" / "exec"
