"""v0.42: runtime-status 字段形状（不启 HTTP）"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_status_dict_has_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import _ccc_control as ctrl

    ctrl.CONTROL_DIR = tmp_path / ".ccc"
    ctrl.CONTROL_FILE = ctrl.CONTROL_DIR / "control.json"
    ctrl.DISABLED_SENTINEL = ctrl.CONTROL_DIR / "DISABLED"
    ctrl.set_mode("ui", reason="t", source="t")
    s = ctrl.status_dict()
    assert s["mode"] == "ui"
    assert "engine_allowed" in s
    assert s["engine_allowed"] is False


def test_gate_product_artifacts_blocks_empty_scope():
    import phase_lint

    # import board helpers
    import importlib.util

    board_path = Path(__file__).parent.parent / "ccc-board.py"
    # 轻量：直接测 phase_lint + plan，不加载整板
    plan = "# t\n\n## 验收\n- pytest -q\n"
    phases = [
        {
            "phase": 1,
            "status": "pending",
            "description": "x",
            "scope": [],
            "subtasks": {"1.1": "pending"},
            "timeout": 60,
        }
    ]
    ok, errs, _ = phase_lint.validate_phases_dict(phases)
    assert not ok
    assert any("empty scope" in e for e in errs)
    pok, perrs = phase_lint.validate_plan_acceptance(plan)
    assert pok, perrs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
