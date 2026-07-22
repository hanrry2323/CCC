"""Baseline dirty classification + ready_for_task semantics."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from _project_baseline import (
    baseline_prompt_for_claude,
    classify_dirty,
    collect_baseline,
)


def test_classify_dirty_ccc_only():
    meta = classify_dirty(
        [
            " M .ccc/board/index.json",
            " M .ccc/reports/x.report.md",
            " M .ccc/warnings.json",
        ]
    )
    assert meta["dirty_kind"] == "ccc_hygiene"
    assert meta["dirty_ccc_only"] is True
    assert meta["dirty_business_paths"] == []


def test_classify_dirty_business_and_mixed():
    biz = classify_dirty([" M src/foo.py", "?? README.md"])
    assert biz["dirty_kind"] == "business"
    mixed = classify_dirty([" M .ccc/board/index.json", " M src/foo.py"])
    assert mixed["dirty_kind"] == "mixed"
    assert mixed["dirty_ccc_only"] is False


def test_classify_dirty_rename_and_clean():
    ren = classify_dirty(["R  .ccc/a.jsonl -> .ccc/b.jsonl"])
    assert ren["dirty_kind"] == "ccc_hygiene"
    assert classify_dirty([])["dirty_kind"] == "clean"


def _git_init(tmp: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp, check=True, capture_output=True
    )


def test_ready_true_when_only_ccc_dirty(tmp_path: Path):
    _git_init(tmp_path)
    (tmp_path / "VERSION").write_text("v1.0.0\n")
    (tmp_path / ".ccc" / "board").mkdir(parents=True)
    (tmp_path / "tracked.txt").write_text("a\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / ".ccc" / "board" / "index.json").write_text("{}\n")
    bl = collect_baseline(tmp_path, project_id="t")
    assert bl["git"]["dirty"] is True
    assert bl["dirty_kind"] == "ccc_hygiene"
    assert bl["dirty_ccc_only"] is True
    assert bl["ready_for_task"] is True
    assert bl["can_dispatch"] is True
    assert "仅编排产物" in "\n".join(bl["risks"]) or "卫生" in bl["summary"]
    prompt = baseline_prompt_for_claude(bl)
    assert "dirty_kind" in prompt
    assert "禁止说「可能是业务改动」" in prompt or "仅编排产物未提交" in prompt
    assert "可下达任务" in prompt
    assert "≤20" in prompt or "20 字" in prompt


def test_ready_false_when_business_dirty(tmp_path: Path):
    _git_init(tmp_path)
    (tmp_path / "VERSION").write_text("v1.0.0\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / "src" / "a.py").write_text("y\n")
    bl = collect_baseline(tmp_path, project_id="t")
    assert bl["dirty_kind"] == "business"
    assert bl["ready_for_task"] is False
    assert bl["can_dispatch"] is True
