"""F4-1: ROLE_CONTEXT_MANIFEST + build_role_context."""
from __future__ import annotations

from pathlib import Path

import pytest

from board.context import (
    OPTIONAL_CONTEXT_KEYS,
    ROLE_CONTEXT_MANIFEST,
    build_role_context,
    set_workspace,
)


REQUIRED_BY_ROLE = {
    "product": {
        "skill",
        "baseline",
        "profile",
        "code_ctx",
        "ref_plans",
        "recent_lessons",
        "current_epic",
        "plan_template",
    },
    "dev": {
        "plan",
        "phases",
        "skill_hints",
        "pytest_failure",
        "current_epic",
    },
    "reviewer": {
        "skill",
        "plan",
        "verdict",
        "current_epic",
    },
}


@pytest.mark.parametrize("role,required", REQUIRED_BY_ROLE.items())
def test_manifest_contains_required_keys(role: str, required: set[str]) -> None:
    keys = set(ROLE_CONTEXT_MANIFEST[role])
    assert required <= keys, f"{role} missing {required - keys}"


def test_placeholder_roles_have_manifest() -> None:
    for role in ("tester", "kb", "ops", "regress"):
        assert role in ROLE_CONTEXT_MANIFEST
        assert isinstance(ROLE_CONTEXT_MANIFEST[role], list)
        assert ROLE_CONTEXT_MANIFEST[role]


def test_build_role_context_structure(tmp_path: Path) -> None:
    (tmp_path / ".ccc").mkdir()
    (tmp_path / ".ccc" / "profile.md").write_text("# profile\nhello\n", encoding="utf-8")
    set_workspace(tmp_path)
    task = {"id": "t-1", "title": "Demo", "description": "desc"}
    ctx = build_role_context("product", task)
    assert set(ctx.keys()) == set(ROLE_CONTEXT_MANIFEST["product"])
    assert all(isinstance(v, str) for v in ctx.values())
    assert "hello" in ctx["profile"]
    assert "t-1" in ctx["current_epic"]


def test_build_role_context_missing_files_empty(tmp_path: Path) -> None:
    (tmp_path / ".ccc").mkdir()
    set_workspace(tmp_path)
    ctx = build_role_context("dev", {"id": "missing-task"})
    assert set(ctx.keys()) == set(ROLE_CONTEXT_MANIFEST["dev"])
    assert ctx["plan"] == ""
    assert ctx["phases"] == ""
    assert ctx["pytest_failure"] == ""


def test_build_role_context_unknown_role() -> None:
    assert build_role_context("no-such-role", None) == {}


def test_optional_keys_documented() -> None:
    # optional 集合覆盖常见可缺项；collector 仍统一兜底空串
    assert "skill" in OPTIONAL_CONTEXT_KEYS
    assert "plan" in OPTIONAL_CONTEXT_KEYS
    assert "recent_lessons" in OPTIONAL_CONTEXT_KEYS


def test_ref_plans_retry_mode(tmp_path: Path) -> None:
    (tmp_path / ".ccc").mkdir()
    set_workspace(tmp_path)
    ctx = build_role_context("product", {"id": "x"}, include_ref_plans=False)
    assert "重试" in ctx["ref_plans"]
