"""engine.hang_support — hang retry counter + small helpers (slim hang.py)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger("ccc")

_HANG_COUNTER_FILE = Path.home() / ".ccc" / "engine-hang-retries.json"
_hang_retry_counter: dict[str, int] = {}


def hang_retry_counter() -> dict[str, int]:
    return _hang_retry_counter


def load_hang_retry_counter() -> None:
    """F-ARCH-01: 从磁盘恢复 hang 重试计数。"""
    _hang_retry_counter.clear()
    try:
        if _HANG_COUNTER_FILE.is_file():
            data = json.loads(_HANG_COUNTER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _hang_retry_counter.update(
                    {str(k): int(v) for k, v in data.items()}
                )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _hang_retry_counter.clear()


def save_hang_retry_counter() -> None:
    """F-ARCH-01: 持久化 hang 重试计数。"""
    try:
        _HANG_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HANG_COUNTER_FILE.write_text(
            json.dumps(_hang_retry_counter, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        _log.warning(
            "[hang] counter write failed for %s: %s", _HANG_COUNTER_FILE, exc
        )


def clear_hung_marker(hung_path: Path, label: str, *, log=None) -> None:
    try:
        hung_path.unlink()
    except OSError as exc:
        if log:
            log(f"[{label}] hang-auto: 清理 {hung_path.name} 失败: {exc}")


def hung_reason(hung_path: Path) -> str:
    try:
        data = json.loads(hung_path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(data, dict):
            return str(data.get("reason") or "").strip()
    except (OSError, json.JSONDecodeError, TypeError):
        pass  # intentional — hung reason file missing/corrupt → empty
    return ""
