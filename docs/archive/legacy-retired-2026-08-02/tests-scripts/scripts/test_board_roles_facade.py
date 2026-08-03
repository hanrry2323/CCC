"""Role facade: board.roles / ccc_board re-export stay aligned."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_ccc_board():
    path = SCRIPTS / "ccc-board.py"
    spec = importlib.util.spec_from_file_location("ccc_board_facade_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["ccc_board_facade_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_board_roles_exports_match_ccc_board():
    import board.roles as roles

    board = _load_ccc_board()
    for name in (
        "product_role",
        "dev_role_launch",
        "dev_role_relaunch",
        "dev_role_check_complete",
        "reviewer_role",
        "tester_role",
        "ops_role",
        "kb_role",
        "audit_role",
        "regress_role",
    ):
        assert getattr(roles, name) is getattr(board, name), name


def test_engine_binds_board_roles_not_importlib_monolith():
    path = SCRIPTS / "ccc-engine.py"
    spec = importlib.util.spec_from_file_location("ccc_engine_facade_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["ccc_engine_facade_test"] = mod
    spec.loader.exec_module(mod)
    assert mod.dev_role_launch.__module__.startswith("board.roles.")
    assert not hasattr(mod, "_ccc_board_path")
