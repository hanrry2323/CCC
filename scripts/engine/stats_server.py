"""engine.stats_server — stats HTTP

Implementation lives in _stats_server_impl.py; attach() execs into ccc_engine host.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

_IMPL = Path(__file__).with_name("_stats_server_impl.py")


def attach(host: ModuleType | dict[str, Any]) -> None:
    ns = host if isinstance(host, dict) else host.__dict__
    code = _IMPL.read_text(encoding="utf-8")
    exec(compile(code, str(_IMPL), "exec"), ns)  # noqa: S102
