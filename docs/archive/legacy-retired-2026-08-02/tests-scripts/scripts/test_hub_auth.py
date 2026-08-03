"""test_hub_auth.py — scripts/_hub_auth 统一认证辅助（窗口 G 迁移）。

覆盖：Bearer 换发、内存缓存复用、TTL 过期重取、401 invalidate 后重取、
换发失败回退 Basic、凭据/Hub URL 解析。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    from _hub_auth import _TOKEN_CACHE

    _TOKEN_CACHE.clear()
    for key in ("CCC_HUB_AUTH", "CCC_HUB_URL", "CCC_HUB_BASE", "CCC_CHAT_USER", "CCC_CHAT_PASS"):
        monkeypatch.delenv(key, raising=False)


class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mock_token_endpoint(monkeypatch, *, token: str = "tok-1", ttl_s: int = 3600, fail: bool = False):
    """monkeypatch urllib.request.urlopen → token 端点响应；返回调用计数 dict。"""
    calls = {"n": 0}

    def fake_open(req, timeout=8):
        calls["n"] += 1
        if fail:
            raise urllib.error.URLError("no-hub")
        return _FakeResp(
            json.dumps(
                {"token": token, "role": "operator", "scheme": "bearer", "ttl_s": ttl_s}
            ).encode()
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    return calls


# ── Bearer 换发 + 缓存 ───────────────────────────────────────────


def test_fetch_and_cache_reuse(monkeypatch):
    from _hub_auth import hub_headers

    calls = _mock_token_endpoint(monkeypatch)
    h1 = hub_headers()
    assert h1["Authorization"] == "Bearer tok-1"
    h2 = hub_headers()
    assert h2 == h1
    assert calls["n"] == 1  # 二次调用命中缓存，不再 POST


def test_ttl_expiry_refetches(monkeypatch):
    from _hub_auth import _TOKEN_CACHE, hub_headers, hub_url

    calls = _mock_token_endpoint(monkeypatch)
    hub_headers()
    assert calls["n"] == 1
    key = hub_url()
    _TOKEN_CACHE[key] = (_TOKEN_CACHE[key][0], time.monotonic() - 1)  # 拨到已过期
    hub_headers()
    assert calls["n"] == 2


def test_invalidate_refetches(monkeypatch):
    from _hub_auth import hub_headers, hub_invalidate

    calls = _mock_token_endpoint(monkeypatch)
    hub_headers()
    assert calls["n"] == 1
    hub_invalidate()
    hub_headers()
    assert calls["n"] == 2


# ── 降级回退 ─────────────────────────────────────────────────────


def test_fetch_fail_falls_back_basic(monkeypatch):
    from _hub_auth import hub_headers

    _mock_token_endpoint(monkeypatch, fail=True)
    h = hub_headers()
    assert h["Authorization"] == "Basic " + _b64("ccc:ccc")


def test_fetch_fail_fallback_uses_env_creds(monkeypatch):
    from _hub_auth import hub_headers

    monkeypatch.setenv("CCC_CHAT_USER", "u")
    monkeypatch.setenv("CCC_CHAT_PASS", "p")
    _mock_token_endpoint(monkeypatch, fail=True)
    h = hub_headers()
    assert h["Authorization"] == "Basic " + _b64("u:p")


# ── 凭据解析 ─────────────────────────────────────────────────────


def test_creds_default():
    from _hub_auth import hub_creds

    assert hub_creds() == ("ccc", "ccc")


def test_creds_from_chat_user_pass(monkeypatch):
    from _hub_auth import hub_creds

    monkeypatch.setenv("CCC_CHAT_USER", "u")
    monkeypatch.setenv("CCC_CHAT_PASS", "p")
    assert hub_creds() == ("u", "p")


def test_creds_hub_auth_preferred(monkeypatch):
    from _hub_auth import hub_creds

    monkeypatch.setenv("CCC_CHAT_USER", "u")
    monkeypatch.setenv("CCC_CHAT_PASS", "p")
    monkeypatch.setenv("CCC_HUB_AUTH", "hu:hp")
    assert hub_creds() == ("hu", "hp")


# ── Hub URL 解析 ─────────────────────────────────────────────────


def test_hub_url_default():
    from _hub_auth import hub_url

    assert hub_url() == "http://127.0.0.1:17777"


def test_hub_url_env_priority(monkeypatch):
    from _hub_auth import hub_url

    monkeypatch.setenv("CCC_HUB_URL", "http://h:1")
    monkeypatch.setenv("CCC_HUB_BASE", "http://b:2")
    assert hub_url() == "http://h:1"


def test_hub_url_explicit_override(monkeypatch):
    from _hub_auth import hub_url

    monkeypatch.setenv("CCC_HUB_URL", "http://h:1")
    assert hub_url("http://127.0.0.1:7777") == "http://127.0.0.1:7777"


# ── content_type 参数 ────────────────────────────────────────────


def test_hub_headers_content_type(monkeypatch):
    from _hub_auth import hub_headers

    _mock_token_endpoint(monkeypatch)
    h = hub_headers(content_type=True)
    assert h["Content-Type"] == "application/json"


def _b64(s: str) -> str:
    import base64

    return base64.b64encode(s.encode()).decode()
