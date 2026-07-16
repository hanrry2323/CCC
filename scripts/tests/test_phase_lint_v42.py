"""v0.42: scope 硬门 + plan 验收硬门"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from phase_lint import (
    validate_scope,
    validate_plan_acceptance,
    validate_phases_dict,
)


def _ok_phase(**kwargs):
    base = {
        "phase": 1,
        "phase_id": "1",
        "status": "pending",
        "description": "touch one file",
        "scope": ["scripts/foo.py"],
        "subtasks": {"1.1": "pending"},
        "timeout": 60,
    }
    base.update(kwargs)
    return base


class TestValidateScope:
    def test_empty_scope_error(self):
        ok, errors, _ = validate_scope([_ok_phase(scope=[])])
        assert not ok
        assert any("empty scope" in e for e in errors)

    def test_missing_scope_error(self):
        p = _ok_phase()
        del p["scope"]
        ok, errors, _ = validate_scope([p])
        assert not ok
        assert any("empty scope" in e for e in errors)

    def test_all_forbidden(self):
        ok, errors, _ = validate_scope([_ok_phase(scope=["all"])])
        assert not ok
        assert any("['all']" in e or "all" in e for e in errors)

    def test_all_allowed_with_marker(self):
        ok, errors, _ = validate_scope(
            [_ok_phase(scope=["all"], notes="全仓重构", allow_all_scope=True)]
        )
        assert ok
        assert not errors

    def test_valid_scope_in_phases_dict(self):
        ok, errors, _ = validate_phases_dict([_ok_phase()])
        assert ok, errors


class TestValidatePlanAcceptance:
    def test_missing_section(self):
        ok, errors = validate_plan_acceptance("# t\n\n## 目标\n- x\n")
        assert not ok
        assert any("验收" in e or "验证" in e for e in errors)

    def test_empty_items(self):
        ok, errors = validate_plan_acceptance("# t\n\n## 验收\n\n（无）\n")
        assert not ok
        assert any("no executable" in e for e in errors)

    def test_valid_acceptance(self):
        ok, errors = validate_plan_acceptance(
            "# t\n\n## 验收\n- pytest scripts/tests/test_x.py -q\n"
        )
        assert ok, errors

    def test_verify_alias(self):
        ok, errors = validate_plan_acceptance(
            "# t\n\n## 验证\n1. python3 -m py_compile scripts/a.py\n"
        )
        assert ok, errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
