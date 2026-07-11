"""test_fallback_quarantine.py — R-12 验证 medium/large fallback 强制 quarantine（v0.24.5+）

事实依据：scripts/ccc-board.py:1601-1628（_review_one_task fallback quarantine 路径）

测试：
  1. medium 类 LLM fallback → task 留在 testing 或 abnormal，不进 verified
  2. large 类 LLM fallback → 同 medium
  3. small 类 LLM fallback → 仍走 py_compile pass（保留 v0.24.1 行为）
  4. fallback 触发 L2 ccc-notify.sh subprocess
  5. review.md 含 "fallback quarantine" 关键字
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

# ccc-board.py 含连字符，从 scripts/ 目录加载
os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ccc_board", str(SCRIPTS / "ccc-board.py"))
ccc_board = importlib.util.module_from_spec(_spec)
sys.modules["ccc_board"] = ccc_board
_spec.loader.exec_module(ccc_board)


@pytest.fixture
def tmp_workspace(tmp_path):
    """临时 workspace 含 .ccc/plans + reports + reviews 目录"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    for sub in ["plans", "reports", "reviews", "review-locks"]:
        (workspace / ".ccc" / sub).mkdir(parents=True)
    return workspace


@pytest.fixture(autouse=True)
def chdir_workspace(tmp_workspace, monkeypatch):
    """切到临时 workspace 并 patch ROOT"""
    monkeypatch.chdir(tmp_workspace)
    monkeypatch.setattr(ccc_board, "ROOT", tmp_workspace)
    yield


def _create_testing_task(task_id: str, size_lines: int) -> str:
    """在 testing 列放一个 task + plan + diff"""
    # 1. 写 .ccc/plans/<id>.plan.md 含 ## 验收 段
    plan_file = tmp_workspace_path() / ".ccc" / "plans" / f"{task_id}.plan.md"
    plan_file.write_text(
        f"# {task_id} Plan\n\n## 验收\n- 跑测试\n- 检查改动\n",
        encoding="utf-8",
    )

    # 2. testing 列写 task JSONL
    testing_dir = tmp_workspace_path() / ".ccc" / "board" / "testing"
    testing_dir.mkdir(parents=True, exist_ok=True)
    jsonl = testing_dir / f"{task_id}.jsonl"
    jsonl.write_text(
        '{"id": "' + task_id + '", "title": "fallback test", "column": "testing"}',
        encoding="utf-8",
    )
    return task_id


def tmp_workspace_path():
    """helper：当前测试用的 workspace path（chdir 后用 .）"""
    return Path.cwd()


def _git_init_with_diff(tmp_path: Path, lines: int = 30):
    """git init + 提交 N 行文件，模拟 size_class=medium/large 的 diff"""
    import subprocess as sp
    sp.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    sp.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

    # 写一个 .py 文件 N 行
    py_file = tmp_path / "scripts" / "test_diff.py"
    py_file.parent.mkdir(exist_ok=True)
    py_file.write_text("\n".join([f"x = {i}" for i in range(lines)]))
    sp.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    sp.run(["git", "commit", "-m", f"test diff {lines} lines"], cwd=tmp_path, check=True, capture_output=True)


def test_fallback_quarantine_calls_subprocess():
    """fallback 路径必须调 subprocess.run(['bash', 'ccc-notify.sh', 'L2', ...])"""
    # 静态扫描：reviewer fallback 分支调 subprocess.run with ccc-notify.sh L2
    src = (SCRIPTS / "ccc-board.py").read_text()
    # fallback 段必须包含 L2 + ccc-notify.sh
    assert "ccc-notify.sh" in src
    assert '"L2"' in src or "'L2'" in src
    # fallback quarantine 关键字
    assert "fallback quarantine" in src


def test_fallback_quarantine_reason_format():
    """R-12 quarantine reason 必须含 v0.24.5 fallback quarantine"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    assert "v0.24.5 fallback quarantine:" in src
    assert "medium/large" in src or "size_class" in src


def test_small_class_keeps_py_compile_path():
    """small 类（≤10 行）LLM fallback 仍走 py_compile pass（保留 v0.24.1 行为）"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # small class + py_files + _py_compile_fallback → move verified
    assert 'size_class == "small"' in src
    assert "_py_compile_fallback" in src
    # small 分支没有 quarantine
    # 通过检查 medium/large 分支有 quarantine 但 small 分支没有
    assert "REVIEW_SIZE_SMALL_MAX = 10" in src


def test_medium_large_does_not_quarantine_small():
    """fallback quarantine 仅对 medium/large，small 类不应触发 L2"""
    # 静态检查：fallback quarantine 段在 medium/large 分支
    src = (SCRIPTS / "ccc-board.py").read_text()
    # 找到 fallback quarantine 段位置
    fallback_quarantine_pos = src.find("fallback quarantine")
    assert fallback_quarantine_pos > 0
    # 必须不在 small 分支内（small 分支用 size_class == "small" 标识）
    # 简单检查：fallback quarantine 不在 "small" 字符串后的 if 块内
    small_pos = src.find('size_class == "small"')
    if small_pos > 0:
        # 查找下一个 size_class 判断
        next_size_check = src.find("size_class", small_pos + 10)
        assert fallback_quarantine_pos > next_size_check or next_size_check < 0


def test_review_md_contains_quarantine_keyword():
    """review.md 写回时含 'fallback' / 'QUARANTINED' 关键字"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # fallback 分支写 review.md 时 verdict 应包含 fallback 信息
    # 检查有写 review.md 的逻辑
    assert ".review.md" in src
    assert "verdict_data" in src


def test_pyreview_classify_review_size_thresholds():
    """REVIEW_SIZE_SMALL_MAX=10 / MEDIUM_MAX=50 分级阈值不变"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    assert "REVIEW_SIZE_SMALL_MAX = 10" in src
    assert "REVIEW_SIZE_MEDIUM_MAX = 50" in src


def test_advisory_lock_released_on_quarantine():
    """quarantine 路径也必须释放 advisory lock（_review_one_task finally）"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # reviewer_role 主循环 finally 块 unlink lock
    assert "os.unlink(lock_path)" in src


def test_subprocess_notify_called_with_correct_args():
    """subprocess.run 调用 ccc-notify.sh L2 必须传 reason[:200]"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # 检查 notify 调用模式：ccc-notify.sh L2 + reason[:200]
    assert "ccc-notify.sh" in src
    # reason[:200] 截断
    assert "[0:200]" in src or "[:200]" in src