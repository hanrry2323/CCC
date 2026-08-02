"""test_engine_dispatch — 注册表读取 + 派发决策（可后台 / 手动两分支）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine.dispatch import (
    DispatchDecision,
    ExecutorEntry,
    ExecutorRegistry,
    decide,
    load_registry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "server" / "config" / "executors.example.json"


def _registry(entries: list[tuple[str, str, str]]) -> ExecutorRegistry:
    """构造临时注册表（role, category, binding）。"""
    return ExecutorRegistry(
        tuple(
            ExecutorEntry(role=role, category=category, binding=binding, note="")
            for role, category, binding in entries
        )
    )


class TestLoadRegistry:
    """注册表加载与 §7 校验。"""

    def test_example_registry_loads(self) -> None:
        reg = load_registry(REGISTRY_PATH)
        assert len(reg.entries) == 5

    def test_missing_fields_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text('{"executors": [{"角色": "开发执行体"}]}', encoding="utf-8")
        with pytest.raises(ValueError, match="缺字段"):
            load_registry(bad)

    def test_invalid_category_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(
            json.dumps(
                {"executors": [{"角色": "x", "分类": "非法值", "当前绑定": "y", "备注": ""}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="分类"):
            load_registry(bad)

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry("/tmp/nonexistent_registry_xyz.json")


class TestDecide:
    """派发决策两分支 + 不派发。"""

    def test_auto_for_dev_role(self) -> None:
        """开发执行体含「可后台 CLI」行 → AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("开发执行体", reg) is DispatchDecision.AUTO

    def test_auto_for_ops_role(self) -> None:
        """维护执行体（可后台 CLI）→ AUTO。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("维护执行体", reg) is DispatchDecision.AUTO

    def test_manual_for_gui_only_role(self) -> None:
        """角色仅「手动 GUI」行 → MANUAL（挂起等人）。"""
        reg = _registry([("开发执行体", "手动 GUI", "Trae")])
        assert decide("开发执行体", reg) is DispatchDecision.MANUAL

    def test_not_dispatchable_for_staff(self) -> None:
        """管理席 / 验收席（分类「—」）→ 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("管理席", reg) is DispatchDecision.NONE
        assert decide("验收席", reg) is DispatchDecision.NONE

    def test_not_dispatchable_unknown_role(self) -> None:
        """未知角色 → 不派发。"""
        reg = load_registry(REGISTRY_PATH)
        assert decide("不存在的角色", reg) is DispatchDecision.NONE
