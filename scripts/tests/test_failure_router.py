"""failure_router 单元测试（方案 2.3 落地）。

覆盖：
- classify_failure 三类关键词
- MAX_TASK_RETRY_BUDGET 常量
- increment_retry_count 抛 RetryBudgetExceeded
- can_retry 边界
- parse_tester_result 解析 **Result:** 行
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from engine.failure_router import (  # noqa: E402
    MAX_TASK_RETRY_BUDGET,
    RetryBudgetExceeded,
    can_retry,
    classify_failure,
    increment_retry_count,
    parse_tester_result,
)


# ── classify_failure ──


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("connection timeout", "transient"),
        ("rate limit exceeded", "transient"),
        ("5xx upstream error", "transient"),
        ("syntax error in x.py", "permanent"),
        ("import error: No module", "permanent"),
        ("permission denied", "permanent"),
        ("random unknown failure", "quarantine"),
        ("", "quarantine"),
    ],
)
def test_classify_failure(msg, expected):
    assert classify_failure(msg) == expected


# ── MAX_TASK_RETRY_BUDGET ──


def test_max_retry_budget_is_8():
    # 方案 2.3 锁定：单卡重试上限 8
    assert MAX_TASK_RETRY_BUDGET == 8


# ── increment_retry_count + can_retry（无 task store 场景）──


def test_increment_retry_count_no_task_raises_after_budget(tmp_path):
    """无 task JSONL 时 retry_count 视为 0，第 9 次（>8）抛 RetryBudgetExceeded。"""
    ws = tmp_path
    # 第 1-8 次不应抛
    for i in range(1, MAX_TASK_RETRY_BUDGET + 1):
        assert increment_retry_count(ws, "ghost-tid") == i
    # 第 9 次抛
    with pytest.raises(RetryBudgetExceeded, match="retry budget exceeded"):
        increment_retry_count(ws, "ghost-tid")


def test_can_retry_no_task_is_true(tmp_path):
    """无 task 时 can_retry 返回 True（视为新任务）。"""
    assert can_retry(tmp_path, "ghost-tid") is True


# ── parse_tester_result ──


def test_parse_tester_result_no_file(tmp_path):
    assert parse_tester_result(tmp_path, "tid-x") is None


def test_parse_tester_result_pass(tmp_path):
    verdict_dir = tmp_path / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True)
    (verdict_dir / "tid.tester.md").write_text(
        "**Result:** PASS\nnotes: all good\n",
        encoding="utf-8",
    )
    assert parse_tester_result(tmp_path, "tid") == "PASS"


def test_parse_tester_result_fail(tmp_path):
    verdict_dir = tmp_path / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True)
    (verdict_dir / "tid.tester.md").write_text(
        "header\n**Result:** FAIL\ntraceback...\n",
        encoding="utf-8",
    )
    assert parse_tester_result(tmp_path, "tid") == "FAIL"


def test_parse_tester_result_skip(tmp_path):
    verdict_dir = tmp_path / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True)
    (verdict_dir / "tid.tester.md").write_text(
        "Result: SKIP — no tests\n",
        encoding="utf-8",
    )
    assert parse_tester_result(tmp_path, "tid") == "SKIP"


def test_parse_tester_result_garbage_returns_none(tmp_path):
    verdict_dir = tmp_path / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True)
    (verdict_dir / "tid.tester.md").write_text("no result line here\n", encoding="utf-8")
    assert parse_tester_result(tmp_path, "tid") is None


def test_parse_tester_result_oserror_returns_none(tmp_path, monkeypatch):
    """OSError 读取时返回 None（不抛）。"""
    verdict_dir = tmp_path / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True)
    target = verdict_dir / "tid.tester.md"
    target.write_text("**Result:** PASS\n", encoding="utf-8")

    def _boom(*a, **k):
        raise OSError("denied")

    monkeypatch.setattr(Path, "read_text", _boom)
    assert parse_tester_result(tmp_path, "tid") is None
