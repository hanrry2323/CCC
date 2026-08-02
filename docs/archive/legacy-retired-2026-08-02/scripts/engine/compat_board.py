"""engine.compat_board — ccc_board namespace attach."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from types import ModuleType
_IMPL = Path(__file__).with_name("_compat_board_impl.py")
def attach(host: ModuleType | dict[str, Any]) -> None:
    ns = host if isinstance(host, dict) else host.__dict__
    exec(compile(_IMPL.read_text(encoding="utf-8"), str(_IMPL), "exec"), ns)  # noqa: S102
