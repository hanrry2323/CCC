#!/usr/bin/env python3
"""Authority patrol tests — green on clean tree; red on planted violation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ccc-authority-patrol.py"


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    e = {"CCC_NOTIFY": "0", **(env or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), **e},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_patrol_green_on_clean_tree():
    cp = _run("--dry-run", "--json")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    data = json.loads(cp.stdout)
    assert data["ok"] is True
    assert data["findings"] == []


def test_patrol_red_on_affirmative_alt_ide(tmp_path, monkeypatch):
    # plant a temporary violation under docs/product
    planted = ROOT / "docs" / "product" / "_patrol_smoke_violation.md"
    planted.write_text(
        "# smoke\n\n日常请用 Claude Code 改本仓平台代码。\n",
        encoding="utf-8",
    )
    try:
        cp = _run("--dry-run", "--json")
        assert cp.returncode == 2, cp.stdout + cp.stderr
        data = json.loads(cp.stdout)
        assert data["ok"] is False
        ids = {f["id"] for f in data["findings"]}
        assert "dev-channel-cursor-only" in ids
    finally:
        planted.unlink(missing_ok=True)


def test_patrol_cards_loadable():
    cards = ROOT / "references" / "authority-patrol.jsonl"
    assert cards.is_file()
    n = 0
    for line in cards.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        json.loads(line)
        n += 1
    assert n >= 8
