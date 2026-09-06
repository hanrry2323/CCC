"""Regression tests for Markdown command extraction in test-evidence.sh.

P3（2026-09-07）：env-manifest ``test_entry`` argv 声明化执行路径——不 eval、
支持引号/空白拆分、缺失回退卡文本解析。``CCC_PROJECTS_DIR`` 指向 tmp 隔离。
"""

import json
import os
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


def _run_with_manifest(
    tmp_path: Path,
    *,
    manifest: dict | None,
    card_body: str,
    workdir: Path,
    test_bin: str = "run-tests.sh",
) -> tuple[int, str]:
    """manifest 在 tmp/projects/<prefix>；卡路径含 docs/dispatch/<prefix>/。"""
    prefix = "zz"
    projects = tmp_path / "projects"
    (projects / prefix).mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (projects / prefix / "env-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
    card_dir = workdir / "docs" / "dispatch" / prefix
    card_dir.mkdir(parents=True, exist_ok=True)
    card = card_dir / f"{prefix}001-x.md"
    card.write_text(f"# Fixture\n\n## 门禁\n\n{card_body}\n", encoding="utf-8")
    evidence = tmp_path / "evidence.log"
    env = dict(os.environ)
    env["CCC_PROJECTS_DIR"] = str(projects)
    result = subprocess.run(
        ["bash", str(SCRIPT), str(card), str(workdir), str(evidence)],
        capture_output=True,
        text=True,
        env=env,
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


# ── P3 env-manifest test_entry argv 声明化执行 ─────────────────────────────


def test_manifest_test_entry_argv_takes_precedence(tmp_path):
    """test_entry 声明 → argv 执行（不 eval），卡文本回退不生效。"""
    workdir = tmp_path / "wd"
    workdir.mkdir(parents=True)
    bin_dir = workdir / "bins"
    bin_dir.mkdir()
    test_bin = bin_dir / "run-tests.sh"
    test_bin.write_text("#!/bin/bash\nprintf 'argv-ran %s <<%s>>\\n' \"$1\" \"$2\"\nexit 0\n", encoding="utf-8")
    test_bin.chmod(0o755)

    rc, evidence = _run_with_manifest(
        tmp_path,
        manifest={"test_entry": "./bins/run-tests.sh --flag 'quoted arg'"},
        card_body="测试：`printf 'card-fallback'`",
        workdir=workdir,
    )
    assert rc == 0
    assert "source=env_manifest" in evidence
    assert "argv-ran --flag <<quoted arg>>" in evidence
    assert "card-fallback" not in evidence


def test_manifest_test_entry_failure_propagates(tmp_path):
    """test_entry 失败 → 退出码原样透传（硬打回语义）。"""
    workdir = tmp_path / "wd"
    workdir.mkdir(parents=True)
    bin_dir = workdir / "bins"
    bin_dir.mkdir()
    test_bin = bin_dir / "fail.sh"
    test_bin.write_text("#!/bin/bash\necho 'boom'\nexit 7\n", encoding="utf-8")
    test_bin.chmod(0o755)

    rc, evidence = _run_with_manifest(
        tmp_path,
        manifest={"test_entry": "./bins/fail.sh"},
        card_body="测试：`printf 'card-fallback'`",
        workdir=workdir,
    )
    assert rc == 7
    assert "exit_code=7" in evidence


def test_manifest_empty_entry_falls_back_to_card(tmp_path):
    """manifest 存在但 test_entry 为空 → 回退卡文本解析（原语义不变）。"""
    workdir = tmp_path / "wd"
    workdir.mkdir(parents=True)

    rc, evidence = _run_with_manifest(
        tmp_path,
        manifest={"test_entry": ""},
        card_body="测试：`printf 'card-fallback'`",
        workdir=workdir,
    )
    assert rc == 0
    assert "card-fallback" in evidence
    assert "cmd=printf 'card-fallback'" in evidence


def test_manifest_missing_falls_back_to_card(tmp_path):
    """env-manifest.json 缺失 → 回退卡文本解析。"""
    workdir = tmp_path / "wd"
    workdir.mkdir(parents=True)

    rc, evidence = _run_with_manifest(
        tmp_path,
        manifest=None,
        card_body="测试：`printf 'card-fallback'`",
        workdir=workdir,
    )
    assert rc == 0
    assert "card-fallback" in evidence
    assert "cmd=printf 'card-fallback'" in evidence


def test_manifest_entry_in_non_prefix_card_ignored(tmp_path):
    """卡路径不含 docs/dispatch/<prefix>/ → 不解析 manifest，走卡文本。"""
    workdir = tmp_path / "wd"
    workdir.mkdir(parents=True)
    projects = tmp_path / "projects"
    (projects / "zz").mkdir(parents=True)
    (projects / "zz" / "env-manifest.json").write_text(
        json.dumps({"test_entry": "./bins/run-tests.sh"}), encoding="utf-8"
    )
    card = workdir / "card.md"
    card.write_text("# Fixture\n\n## 门禁\n\n测试：`printf 'card-fallback'`\n", encoding="utf-8")
    evidence = tmp_path / "evidence.log"
    env = dict(os.environ)
    env["CCC_PROJECTS_DIR"] = str(projects)
    result = subprocess.run(
        ["bash", str(SCRIPT), str(card), str(workdir), str(evidence)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "card-fallback" in evidence.read_text(encoding="utf-8")
