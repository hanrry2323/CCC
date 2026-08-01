"""auth rate-limit 桶：无界增长防护 + 429 限速。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _reset_buckets():
    from chat_server import auth

    auth._auth_failures.clear()
    auth._auth_call_count = 0
    yield
    auth._auth_failures.clear()


def test_sweep_removes_stale_ip_keeps_active():
    """滑出窗口的桶被周期清扫，活跃桶保留（防轮换 IP 内存无界增长）。"""
    from chat_server import auth

    now = time.monotonic()
    auth._auth_failures["stale-ip"] = [now - auth._AUTH_WINDOW_S - 10]
    auth._auth_failures["active-ip"] = [now - 1]
    auth._sweep_stale_auth_buckets(now)

    assert "stale-ip" not in auth._auth_failures
    assert "active-ip" in auth._auth_failures


def test_sweep_removes_empty_buckets():
    """defaultdict 访问会留下空桶；清扫一并移除。"""
    from chat_server import auth

    now = time.monotonic()
    auth._auth_failures["empty-ip"] = []
    auth._sweep_stale_auth_buckets(now)
    assert "empty-ip" not in auth._auth_failures


def test_rate_limit_blocks_after_max_fails():
    """同窗口内失败达 _AUTH_MAX_FAILS → 429。"""
    from fastapi import HTTPException

    from chat_server import auth

    auth._auth_failures.clear()
    for _ in range(auth._AUTH_MAX_FAILS):
        auth._auth_failures["ip-x"].append(time.monotonic())

    with pytest.raises(HTTPException) as ei:
        auth._rate_limit_auth("ip-x")
    assert ei.value.status_code == 429


def test_bucket_pruned_by_window():
    """窗口滑动：旧失败不计入，不触发 429。"""
    from chat_server import auth

    now = time.monotonic()
    auth._auth_failures["ip-y"] = [now - auth._AUTH_WINDOW_S - 5] * auth._AUTH_MAX_FAILS
    # 不 raise（旧失败已滑出窗口，桶在 _rate_limit_auth 内被修剪）
    auth._rate_limit_auth("ip-y")
    assert len(auth._auth_failures["ip-y"]) == 0
