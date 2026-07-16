"""test_phase_lint.py — v0.28.0 phases.jsonl 校验测试"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from phase_lint import (
    validate_schema_version,
    validate_phase_structure,
    validate_no_cycle_dependencies,
    validate_status_transitions,
    run_lint,
)


class TestValidateSchemaVersion:
    """schema_version 校验测试"""

    def test_schema_version_mixed_periods(self):
        """phase 中包含 schema_version 字段应报错"""
        phases = [{"phase": 1, "phase_id": "1.1", "status": "pending", "schema_version": "1.1"}]
        is_valid, errors = validate_schema_version(phases, "test_task")
        assert not is_valid
        assert any("phase 返回类型混淆" in e for e in errors)

    def test_schema_version_valid(self):
        """schema_version 在 phase 字段中会被 phase_lint.py 标记为错误"""
        phases = [{"phase": 1, "phase_id": "1.1", "status": "pending", "schema_version": "1.1"}]
        is_valid, errors = validate_schema_version(phases, "test_task")
        assert any("phase 返回类型混淆" in e for e in errors)


class TestValidatePhaseStructure:
    """phase 结构校验测试"""

    def test_missing_phase_field(self):
        """缺少 phase 字段应报错"""
        phases = [{"phase_id": "1", "status": "pending"}]
        is_valid, errors = validate_phase_structure(phases)
        assert not is_valid
        assert any("phase 缺少 field: phase" in e for e in errors)

    def test_phase_id_mismatch(self):
        """phase_id 与 phase 不一致时应存在错误"""
        phases = [{"phase": 1, "phase_id": "2", "status": "pending"}]
        is_valid, errors = validate_phase_structure(phases)
        assert not is_valid
        assert any("phase_id 与 phase 不一致" in e for e in errors)

    def test_unknown_fields(self):
        """未知字段应报错"""
        phases = [{"phase": 1, "phase_id": "1", "status": "pending", "unknown_field": "value"}]
        is_valid, errors = validate_phase_structure(phases)
        assert not is_valid
        assert any("未知字段" in e for e in errors)

    def test_valid_minimal_phase(self):
        """最小有效 phase"""
        phases = [{"phase": 1, "phase_id": "1", "status": "pending"}]
        is_valid, errors = validate_phase_structure(phases)
        assert is_valid


class TestValidateNoCycleDependencies:
    """循环依赖检测测试"""

    def test_no_cycle(self):
        phases = [
            {"phase": 1, "phase_id": "1", "status": "pending", "depends_on": [2]},
            {"phase": 2, "phase_id": "2", "status": "pending"},
        ]
        is_valid, errors = validate_no_cycle_dependencies(phases)
        assert is_valid

    def test_simple_cycle(self):
        phases = [
            {"phase": 1, "phase_id": "1", "status": "pending", "depends_on": [2]},
            {"phase": 2, "phase_id": "2", "status": "pending", "depends_on": [1]},
        ]
        is_valid, errors = validate_no_cycle_dependencies(phases)
        assert not is_valid
        assert any("循环依赖" in e for e in errors)


class TestValidateStatusTransitions:
    """状态流转校验测试"""

    def test_valid_progression(self):
        phases = [
            {"phase": 1, "phase_id": "1", "status": "pending"},
            {"phase": 2, "phase_id": "2", "status": "done"},
        ]
        is_valid, errors = validate_status_transitions(phases)
        assert is_valid

    def test_invalid_instant_jump(self):
        phases = [{"phase": 1, "phase_id": "1", "status": "done"}]
        is_valid, errors = validate_status_transitions(phases)
        assert not is_valid
        assert any("状态从" in e for e in errors)


class TestRunLint:
    """集成测试"""

    def test_nonexistent_phase_file(self):
        exit_code = run_lint("nonexistent_task")
        assert exit_code == 1

    def test_empty_phases_file(self):
        phases_file = Path.cwd() / ".ccc" / "phases" / "empty.phases.json"
        phases_file.write_text("")
        exit_code = run_lint("empty_task")
        # phase_lint 会对空文件报错
        assert exit_code == 1
        phases_file.unlink()

    def test_valid_phases_file(self):
        phases_file = Path.cwd() / ".ccc" / "phases" / "valid.phases.json"
        phases_content = '{"schema_version": "1.1"}\n{"phase": 1, "phase_id": "1", "status": "pending"}\n'
        phases_file.write_text(phases_content)
        exit_code = run_lint("valid_task")
        # phase_lint 应该通过校验
        assert exit_code == 0
        phases_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
