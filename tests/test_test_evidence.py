"""Regression tests for Markdown command extraction in test-evidence.sh."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test-evidence.sh"


def run_evidence(tmp_path: Path, declaration: str) -> tuple[int, str]:
    card = tmp_path / "card.md"
    evidence = tmp_path / "evidence.log"
    card.write_text(f"# Fixture\n\n## 门禁\n\n{declaration}\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(card), str(tmp_path), str(evidence)],
        capture_output=True,
        text=True,
    )
    return result.returncode, evidence.read_text(encoding="utf-8")


def test_plain_command(tmp_path):
    rc, evidence = run_evidence(tmp_path, "测试：printf '%s' plain")
    assert rc == 0
    assert "cmd=printf '%s' plain" in evidence
    assert "plain" in evidence


def test_inline_code_command(tmp_path):
    rc, evidence = run_evidence(tmp_path, "测试：`printf '%s' wrapped`")
    assert rc == 0
    assert "cmd=printf '%s' wrapped" in evidence
    assert "wrapped" in evidence


def test_inline_code_with_chinese_annotation(tmp_path):
    declaration = "测试：`printf '%s' annotated`（若仓库现行入口不同，先核实后使用等价命令）"
    rc, evidence = run_evidence(tmp_path, declaration)
    assert rc == 0
    assert "cmd=printf '%s' annotated" in evidence
    assert "若仓库" not in evidence


def test_pytest_node_id_is_not_truncated(tmp_path):
    command = "printf '%s' tests/test_demo.py::test_foo"
    rc, evidence = run_evidence(tmp_path, f"测试：`{command}`")
    assert rc == 0
    assert f"cmd={command}" in evidence
    assert "tests/test_demo.py::test_foo" in evidence


def test_inner_shell_backticks_are_preserved(tmp_path):
    command = "printf '%s' `printf inner`"
    rc, evidence = run_evidence(tmp_path, f"测试：{command}")
    assert rc == 0
    assert f"cmd={command}" in evidence
    assert "inner" in evidence


def test_missing_test_declaration_is_allowed(tmp_path):
    card = tmp_path / "card.md"
    evidence = tmp_path / "evidence.log"
    card.write_text("# Fixture\n\n## gate\n\n无测试声明\n", encoding="utf-8")
    result = subprocess.run(
        ["bash", str(SCRIPT), str(card), str(tmp_path), str(evidence)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert evidence.read_text(encoding="utf-8") == "no_test_declared\n"
