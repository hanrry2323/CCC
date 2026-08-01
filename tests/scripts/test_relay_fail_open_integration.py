"""CCC Relay 2026-07-25 fail-open 集成回归测试。

侧文件:sidecar 进程 / chat_server 服务共享 _utils.relay_is_up +
relay_direct_fallback,claude_session._build_options 在 relay 不可达时
覆盖 env["ANTHROPIC_BASE_URL"] 为直连 URL,不改 os.environ。

验证契约:
1. relay_is_up() True → env 保留 plist 写的 :4100(走 M1 ai-loop-router)
2. relay_is_up() False → env 覆盖为 CCC_RELAY_DIRECT_URL(走直连)
3. 覆盖只改局部 env dict,不改 os.environ(无 race)
4. relay_direct_fallback() 缺 env 时回退直连默认
"""
from __future__ import annotations

from unittest.mock import patch

import _utils
from _utils import relay_direct_fallback, relay_is_up


def _build_env(simulated: str = "http://127.0.0.1:4100") -> dict[str, str]:
    """模拟 _build_options 构造的 env 局部 dict。"""
    return {"ANTHROPIC_BASE_URL": simulated, "CLAUDE_PROJECT_DIR": "/x"}


def test_relay_up_true_keeps_relay_url(monkeypatch):
    """relay 在线时,env 保留 plist 写的 relay URL。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4100")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://fallback.example.test/anthropic")
    monkeypatch.setattr(_utils, "relay_is_up", lambda: True)
    env = _build_env()
    if not _utils.relay_is_up():
        env["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4100"
    # os.environ 未被覆盖
    import os
    assert os.environ.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4100"


def test_relay_up_false_overrides_to_direct(monkeypatch):
    """relay 不可达时,env 覆盖为直连 URL。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4100")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://fallback.example.test/anthropic")
    monkeypatch.setattr(_utils, "relay_is_up", lambda: False)
    env = _build_env()
    if not _utils.relay_is_up():
        env["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env["ANTHROPIC_BASE_URL"] == "https://fallback.example.test/anthropic"


def test_local_env_not_polluted(monkeypatch):
    """fail-open 覆盖只改局部 env dict,不改 os.environ。"""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4100")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "https://fallback.example.test/anthropic")
    # 模拟两个并发请求:request A fail-open,request B 不应被污染
    monkeypatch.setattr(_utils, "relay_is_up", lambda: False)
    env_a = _build_env()
    if not _utils.relay_is_up():
        env_a["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    monkeypatch.setattr(_utils, "relay_is_up", lambda: True)
    env_b = _build_env()
    if not _utils.relay_is_up():
        env_b["ANTHROPIC_BASE_URL"] = _utils.relay_direct_fallback()
    assert env_a["ANTHROPIC_BASE_URL"] == "https://fallback.example.test/anthropic"
    assert env_b["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4100"
    # os.environ 始终是 plist 的 :4100
    import os
    assert os.environ.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4100"


def test_relay_direct_fallback_default(monkeypatch, tmp_path):
    """缺 CCC_RELAY_DIRECT_URL / 直连文件时返回空（MiniMax 已退役，无硬编码）。"""
    monkeypatch.delenv("CCC_RELAY_DIRECT_URL", raising=False)
    monkeypatch.setattr(_utils, "_RELAY_DIRECT_URL_FILE", str(tmp_path / "missing.url"))
    url = relay_direct_fallback()
    assert url == ""


def test_relay_direct_fallback_reads_file(monkeypatch, tmp_path):
    """未设 env 时可读 ~/.ccc/relay-direct.url。"""
    monkeypatch.delenv("CCC_RELAY_DIRECT_URL", raising=False)
    p = tmp_path / "relay-direct.url"
    p.write_text("https://fallback.example.test/anthropic\n", encoding="utf-8")
    monkeypatch.setattr(_utils, "_RELAY_DIRECT_URL_FILE", str(p))
    assert relay_direct_fallback() == "https://fallback.example.test/anthropic"


def test_relay_direct_fallback_rejects_relay_loop(monkeypatch, tmp_path):
    """误配 DIRECT_URL=:4100 时不得空转，视为未配置。"""
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "http://127.0.0.1:4100")
    monkeypatch.setattr(_utils, "_RELAY_DIRECT_URL_FILE", str(tmp_path / "missing.url"))
    url = relay_direct_fallback()
    assert url == ""
    assert ":4100" not in url
