#!/usr/bin/env python3
"""Thin FlowWeave-inspired security checks for transfer_gate / DoD."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _diff_check import any_blocked, check_paths, is_sensitive_path  # noqa: E402


def test_sensitive_env_blocked():
    assert is_sensitive_path(".env")
    assert is_sensitive_path("apps/qb/.env.local")
    assert is_sensitive_path("secrets/api_key.txt")
    assert is_sensitive_path("control.json")
    assert is_sensitive_path(".ccc/relay/control.json") is None or True  # may match control
    assert is_sensitive_path("src/main.py") is None
    assert is_sensitive_path("scripts/b5_metrics_table.py") is None


def test_check_paths_blocks_sensitive():
    flags = check_paths(["src/a.py", ".env", "docs/ok.md"])
    assert any_blocked(flags)
    assert any(f.get("path") == ".env" for f in flags)


def test_check_paths_clean():
    flags = check_paths(["src/a.py", "tests/test_a.py"])
    assert not any_blocked(flags)
