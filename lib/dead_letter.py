"""lib/dead_letter.py — 失败任务死信文件写入。

按天滚动：var/dead-letters/YYYY-MM-DD.jsonl
每行一条 JSON：{timestamp, function_name, module, error_type, error_message, args_repr, kwargs_repr}

写入失败仅 print 告警，绝不抛异常（不能让死信拖垮业务）。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dead_letter_dir() -> Path:
    override = os.environ.get("QX_DEAD_LETTER_DIR")
    return Path(override) if override else PROJECT_ROOT / "var" / "dead-letters"


def write_dead_letter(
    func_name: str,
    exc: BaseException,
    module: str = "",
    args: Optional[tuple] = None,
    kwargs: Optional[dict] = None,
) -> None:
    """写一条死信记录到当日 JSONL 文件。失败仅 print 告警。"""
    try:
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "function_name": func_name,
            "module": module,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
            "stacktrace": traceback.format_exc()[:2000],
            "args_repr": repr(args)[:200] if args else "",
            "kwargs_repr": repr(kwargs)[:200] if kwargs else "",
        }
        d = _dead_letter_dir()
        d.mkdir(parents=True, exist_ok=True)
        fname = d / f"{datetime.now().date().isoformat()}.jsonl"
        with fname.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[dead_letter] 写入失败: {e}", file=sys.stderr)
