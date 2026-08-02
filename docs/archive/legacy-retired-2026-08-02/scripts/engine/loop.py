"""engine.loop — engine_loop main poll

Implementation lives in _loop_impl.py; attach() execs into ccc_engine host.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

_IMPL = Path(__file__).with_name("_loop_impl.py")


def attach(host: ModuleType | dict[str, Any]) -> None:
    ns = host if isinstance(host, dict) else host.__dict__
    code = _IMPL.read_text(encoding="utf-8")
    exec(compile(code, str(_IMPL), "exec"), ns)  # noqa: S102
