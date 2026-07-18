"""Unit tests for scripts/_skills_catalog.py — no live server."""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
import sys

sys.path.insert(0, str(SCRIPTS))

from _skills_catalog import (  # noqa: E402
    _unfold_yaml_description,
    discover_skills,
    format_skill_hints_block,
)


def test_unfold_folded_description():
    text = (
        "---\n"
        "name: demo\n"
        "description: >-\n"
        "  First line of description\n"
        "  continues here\n"
        "---\n"
    )
    desc = _unfold_yaml_description(text)
    assert "First line" in desc
    assert ">-" not in desc


def test_unfold_plain_description():
    text = "name: x\ndescription: hello world\n"
    assert _unfold_yaml_description(text) == "hello world"


def test_discover_hides_engine_by_default(tmp_path):
    ccc = tmp_path / "CCC"
    skills = ccc / "skills"
    for sid in ("ccc-product", "codebase-memory"):
        d = skills / sid
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {sid}\ndescription: test for {sid}\n---\n",
            encoding="utf-8",
        )
    # empty claude/agents so we only see our fixtures
    home_claude = tmp_path / "home" / ".claude" / "skills"
    home_claude.mkdir(parents=True)

    # Monkeypatch Path.home via discover's roots — pass ccc_home only;
    # still scans real ~/.claude. Filter by checking our ids present/absent.
    found = discover_skills(ccc_home=ccc, include_engine=False, limit=200)
    ids = {s["id"] for s in found}
    assert "ccc-product" not in ids
    assert "codebase-memory" in ids
    mem = next(s for s in found if s["id"] == "codebase-memory")
    assert mem["tier"] == "common"
    assert mem["hub_visible"] is True


def test_discover_include_engine(tmp_path):
    ccc = tmp_path / "CCC"
    d = ccc / "skills" / "ccc-dev"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: ccc-dev\ndescription: engine role\n---\n",
        encoding="utf-8",
    )
    found = discover_skills(ccc_home=ccc, include_engine=True, limit=200)
    ids = {s["id"] for s in found}
    assert "ccc-dev" in ids
    dev = next(s for s in found if s["id"] == "ccc-dev")
    assert dev["tier"] == "engine"
    assert dev["hub_visible"] is False


def test_format_skill_hints_block():
    assert format_skill_hints_block([]) == ""
    block = format_skill_hints_block(["planning-with-files"], note="优先")
    assert "planning-with-files" in block
    assert "优先" in block
