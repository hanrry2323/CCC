"""CCC Relay 2026-07-25 fail-open 集成回归测试。

侧文件:sidecar 进程 / chat_server 服务共享 _utils.relay_is_up +
relay_direct_fallback,claude_session._build_options 在 relay 不可达时
覆盖 env["ANTHROPIC_BASE_URL"] 为直连 URL,不改 os.environ。

验证契约:
1. relay_is_up() True → env 保留 plist 写的 :4000(走 relay)
2. relay_is_up() False → env 覆盖为 CCC_RELAY_DIRECT_URL(走直连)
3. 覆盖只改局部 env dict,不改 os.environ(无 race)
4. relay_direct_fallback() 缺 env 时回退 MiniMax 默认
"""
from __future__ import annotations

from unittest.mock import patch

import _utils
from _utils import relay_direct_fallback, relay_is_up


def _build_env(simulated: str = "http://127.0.0.1:4000") -> dict[str, str]:
    """模拟 _build_options 构造的 env 局部 dict。"""
    return {"ANTHROPIC_BASE_URL": simulated, "CLAUDE_PROJECT_DIR": "/x"}


def test_relay_up_true_keeps_relay_url(monkeypatch):
    """relay 在线时,env 保留 plist 写的 relay URL。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://api.minimaxi.com/anthropic")
    monkeypatch.setattr(_utils, "relay_is_up", lambda: True)
    env = _build_env()
    if not _utils.relay_is_up():
        env["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    # os.environ 未被覆盖
    import os
    assert os.environ.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4000"


def test_relay_up_false_overrides_to_direct(monkeypatch):
    """relay 不可达时,env 覆盖为直连 URL。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://api.minimaxi.com/anthropic")
    monkeypatch.setattr(_utils, "relay_is_up", lambda: False)
    env = _build_env()
    if not _utils.relay_is_up():
        env["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env["ANTHROPIC_BASE_URL"] == "https://api.minimaxi.com/anthropic"


def test_local_env_not_polluted(monkeypatch):
    """fail-open 覆盖只改局部 env dict,不改 os.environ。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://api.minimaxi.com/anthropic")
    # 模拟两个并发请求:request A fail-open,request B 不应被污染
    monkeypatch.setattr(_utils, "relay_is_up", lambda: False)
    env_a = _build_env()
    if not _utils.relay_is_up():
        env_a["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    monkeypatch.setattr(_utils, "relay_is_up", lambda: True)
    env_b = _build_env()
    if not _utils.relay_is_up():
        env_b["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env_a["ANTHROPIC_BASE_URL"] == "https://api.minimaxi.com/anthropic"
    assert env_b["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    # os.environ 始终是 plist 的 :4000
    import os
    assert os.environ.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4000"


def test_relay_direct_fallback_default(monkeypatch):
    """缺 CCC_RELAY_DIRECT_URL 时回退 MiniMax 默认。"""
    monkeypatch.delenv("CCC_RELAY_DIRECT_URL", raising=False)
    assert relay_direct_fallback() == "https://api.minimaxi.com/anthropic"


def test_relay_is_up_caches(monkeypatch):
    """relay_is_up 10s 缓存:同 host/port 第二次调用不发请求。"""
    import _utils
    # 清缓存(同模块跨测试共享)
    monkeypatch.setattr(_utils, "_RELAY_UP_CACHE", {"ts": 0.0, "up": None, "host": "127.0.0.1", "port": 4000})

    calls = {"n": 0}

    def fake_urlopen(*a, **kw):
        calls["n"] += 1
        from unittest.mock import MagicMock
        m = MagicMock()
        m.__enter__ = lambda self: m
        m.__exit__ = lambda self, *args: None
        m.status = 200
        return m

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        r1 = relay_is_up()
        r2 = relay_is_up()
    assert r1 is True
    assert r2 is True
    assert calls["n"] == 1, f"应只调一次 urlopen,实际 {calls['n']} 次"
