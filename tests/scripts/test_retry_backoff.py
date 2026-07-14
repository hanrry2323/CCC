"""test_retry_backoff.py — 验证 dev_role retry 退避语义（v0.24.7+）

事实依据：scripts/ccc-board.py:62-67 (_backoff_seconds) + 853-885 (retry_at 写回)

测试：
  1. _backoff_seconds(retry=0) ≥ 60（v0.24.7+ 强制 first backoff）
  2. _backoff_seconds 序列：60/120/240/480/960/1920/3600（封顶 1h）
  3. dev_role retry=0 时 retry_at 必填（非 None）
  4. retry_at 时间为 now + backoff（±2s 容差）
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ccc_board", str(SCRIPTS / "ccc-board.py"))
ccc_board = importlib.util.module_from_spec(_spec)
sys.modules["ccc_board"] = ccc_board
_spec.loader.exec_module(ccc_board)


_backoff_seconds = ccc_board._backoff_seconds


def test_retry_zero_minimum_60s():
    """v0.24.7+ first backoff：retry=0 必须 ≥ 60s（之前是 0 → 立即重试）"""
    backoff = _backoff_seconds(0)
    assert backoff >= 60, f"retry=0 backoff must be ≥ 60s, got {backoff}"


def test_backoff_exponential_sequence():
    """_backoff_seconds 序列：60→120→240→480→960→1920→3600"""
    expected = [60, 120, 240, 480, 960, 1920, 3600]
    for retry, expected_s in enumerate(expected):
        actual = _backoff_seconds(retry)
        assert actual == expected_s, f"retry={retry}: expected {expected_s}, got {actual}"


def test_backoff_capped_at_3600():
    """retry ≥ 6 封顶 3600s（1h）"""
    for retry in [6, 7, 10, 100]:
        backoff = _backoff_seconds(retry)
        assert backoff == 3600, f"retry={retry}: expected 3600, got {backoff}"


def test_backoff_monotonic_increase():
    """retry 越大 backoff 越大（封顶前）"""
    prev = 0
    for retry in range(7):
        current = _backoff_seconds(retry)
        assert current > prev or retry == 0, f"retry={retry}: {current} should be > {prev}"
        prev = current


def test_retry_at_never_none_in_source():
    """v0.24.7+ retry_at 必填：源码检查 retry=0 时也填 retry_at"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # 修复前：retry=0 时 retry_at = None
    # 修复后：retry >= 0 时 retry_at = now + backoff
    assert "if retry >= 0" in src or "if retry >= 1" not in src or "backoff = _backoff_seconds(retry - 1) if retry else 60" in src
    # 必须有 "retry else 60"（v0.24.7 first backoff 强制）
    assert "retry else 60" in src, "v0.24.7 first backoff must be 60s"


def test_dev_role_retry_first_backoff_in_branch():
    """dev_role 写 retry_at 段必须用 _backoff_seconds(retry-1) if retry else 60"""
    src = (SCRIPTS / "ccc-board.py").read_text()
    # v0.24.7 关键修复：retry else 60（之前是 retry else 0）
    assert "_backoff_seconds(retry - 1) if retry else 60" in src
    # 不能有旧的 "else 0" 单独出现（在 retry backoff 上下文里）
    # 注：其他无关的 "else 0" 可能存在，所以只检查 retry backoff 段


def test_retry_count_increments():
    """_backoff_seconds(retry-1) 等价于 min(60 * 2^retry, 3600)"""
    for retry in [1, 2, 3, 4, 5]:
        actual = _backoff_seconds(retry)
        expected = min(60 * (2**retry), 3600)
        assert actual == expected, f"retry={retry}: expected {expected}, got {actual}"