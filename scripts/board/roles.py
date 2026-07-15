"""board.roles — 7 角色入口（从 ccc-board 再导出，保持签名稳定）。

实现体仍在 ccc-board.py（巨大 orchestration）；本模块是拆包边界声明与稳定 import 路径。
后续可逐角色下沉到 roles_*.py，不改调用方。
"""
from __future__ import annotations

# 延迟导入，避免 importlib 加载 ccc_board 与 board.roles 循环
def __getattr__(name: str):
    import importlib
    import sys
    from pathlib import Path

    # Prefer already-loaded ccc_board (engine importlib module)
    mod = sys.modules.get("ccc_board")
    if mod is None:
        # Fallback: load sibling ccc-board.py
        board_py = Path(__file__).resolve().parent.parent / "ccc-board.py"
        if "ccc_board" not in sys.modules:
            import importlib.util

            spec = importlib.util.spec_from_file_location("ccc_board", board_py)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            # Ensure scripts on path
            scripts = str(board_py.parent)
            if scripts not in sys.path:
                sys.path.insert(0, scripts)
            sys.modules["ccc_board"] = mod
            spec.loader.exec_module(mod)
        else:
            mod = sys.modules["ccc_board"]
    try:
        return getattr(mod, name)
    except AttributeError as exc:
        raise AttributeError(name) from exc


__all__ = [
    "product_role",
    "dev_role",
    "dev_role_launch",
    "dev_role_relaunch",
    "dev_role_check_complete",
    "reviewer_role",
    "tester_role",
    "ops_role",
    "kb_role",
    "regress_role",
    "audit_role",
]
