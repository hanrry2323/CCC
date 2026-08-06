"""registry.yaml → PREFIXES / forbidden / taskable SSOT."""

from __future__ import annotations

from server.board import models
from server.board.registry import (
    card_prefixes,
    clear_registry_cache,
    forbidden_prefixes,
    load_projects,
    taskable_names,
)


def test_prefixes_match_registry() -> None:
    clear_registry_cache()
    from_reg = card_prefixes()
    assert set(models.PREFIXES) == set(from_reg)
    assert models.PREFIXES["ccc"] == from_reg["ccc"]
    assert "qh" not in models.PREFIXES


def test_qh_forbidden() -> None:
    clear_registry_cache()
    assert "qh" in forbidden_prefixes()
    assert "qh" in models.FORBIDDEN_CARD_PREFIXES


def test_taskable_includes_ccc_excludes_qh() -> None:
    clear_registry_cache()
    names = taskable_names()
    assert "CCC" in names or "ccc" in names
    assert "qb" in names
    assert "QuantHive" not in names
    assert "qh" not in {n.lower() for n in names if n == "qh"}


def test_load_projects_non_empty() -> None:
    clear_registry_cache()
    projects = load_projects()
    assert any(p.prefix == "ccc" for p in projects)
    assert any(p.prefix == "qh" and p.forbidden for p in projects)
