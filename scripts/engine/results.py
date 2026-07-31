"""engine.results — acceptance budget + handle_task_result

Implementation lives in _results_impl.py; attach() execs into ccc_engine host.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

_IMPL = Path(__file__).with_name("_results_impl.py")


def attach(host: ModuleType | dict[str, Any]) -> None:
    """Exec implementation into host module dict or globals dict."""
    ns = host if isinstance(host, dict) else host.__dict__
    code = _IMPL.read_text(encoding="utf-8")
    exec(compile(code, str(_IMPL), "exec"), ns)  # noqa: S102
