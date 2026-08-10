"""registry.yaml → PREFIXES / forbidden / taskable SSOT."""

from __future__ import annotations

from server.board import models
from server.board.registry import (
    card_prefixes,
    check_path_locations,
    clear_registry_cache,
    forbidden_prefixes,
    load_projects,
    ProjectEntry,
    taskable_names,
)


def test_prefixes_match_registry() -> None:
    clear_registry_cache()
    from_reg = card_prefixes()
    assert set(models.PREFIXES) == set(from_reg)
    assert "ccc" not in models.PREFIXES  # 2026-08-10 平台自研禁出卡
    assert "qh" not in models.PREFIXES


def test_qh_forbidden() -> None:
    clear_registry_cache()
    assert "qh" in forbidden_prefixes()
    assert "qh" in models.FORBIDDEN_CARD_PREFIXES


def test_ccc_forbidden_platform_self_dev() -> None:
    """2026-08-10 红线：CCC 平台自研禁出卡 → ccc 与 qh 同列禁卡表。"""
    clear_registry_cache()
    assert "ccc" in forbidden_prefixes()
    assert "ccc" in models.FORBIDDEN_CARD_PREFIXES


def test_taskable_excludes_ccc_and_qh() -> None:
    clear_registry_cache()
    names = taskable_names()
    assert "qb" in names
    assert "CCC" not in names and "ccc" not in names  # ccc 禁出卡
    assert "QuantHive" not in names
    assert "qh" not in {n.lower() for n in names if n == "qh"}


def test_load_projects_non_empty() -> None:
    clear_registry_cache()
    projects = load_projects()
    assert any(p.prefix == "ccc" for p in projects)
    assert any(p.prefix == "qh" and p.forbidden for p in projects)


def test_registry_locations_comply() -> None:
    """存量 registry 全部项目路径落在归属树内（legacy 豁免）。"""
    clear_registry_cache()
    assert check_path_locations() == []


def test_check_path_locations_out_of_tree() -> None:
    """业务仓路径越界 → 问题清单；legacy 豁免。"""
    p = ProjectEntry(
        prefix="xy",
        id="xianyu",
        name="xianyu",
        display="xianyu",
        taskable=True,
        forbidden=False,
        status="active",
        dossier=None,
        role="",
        path_m1=None,
        path_mac2017="/Users/fan/ZCodeProject/xianyu",
        location="mac2017-apps",
    )
    issues = check_path_locations([p])
    assert any("越界" in i for i in issues)


def test_check_path_locations_legacy_exempt() -> None:
    p = ProjectEntry(
        prefix="qh",
        id="QuantHive",
        name="QuantHive",
        display="QuantHive",
        taskable=False,
        forbidden=True,
        status="active",
        dossier=None,
        role="",
        path_m1="/Users/apple/ZCodeProject/QuantHive",
        path_mac2017=None,
        location="legacy",
    )
    assert check_path_locations([p]) == []


def test_check_path_locations_missing_location() -> None:
    p = ProjectEntry(
        prefix="n1",
        id="n1",
        name="n1",
        display="n1",
        taskable=True,
        forbidden=False,
        status="active",
        dossier=None,
        role="",
        path_m1=None,
        path_mac2017="/Users/fan/program/apps/n1",
        location="",
    )
    issues = check_path_locations([p])
    assert any("缺 location" in i for i in issues)
