"""engine.recover — recover_tasks + abnormal retry / post-exhaust.

Implementations: _recover_impl.py + _recover_retry_impl.py
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

_IMPL_A = Path(__file__).with_name("_recover_impl.py")
_IMPL_B = Path(__file__).with_name("_recover_retry_impl.py")


def attach(host: ModuleType | dict[str, Any]) -> None:
    ns = host if isinstance(host, dict) else host.__dict__
    for p in (_IMPL_A, _IMPL_B):
        code = p.read_text(encoding="utf-8")
        exec(compile(code, str(p), "exec"), ns)  # noqa: S102
