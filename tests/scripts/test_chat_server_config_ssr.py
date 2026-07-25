"""CCC ChatServerConfig SSOT 回归测试(v0.61.0 阶段 D)"""
from __future__ import annotations


def test_chat_server_config_defaults():
    """无 env 时 ChatServerConfig 走默认。"""
    from chat_server.config import ChatServerConfig

    c = ChatServerConfig()
    assert c.host == "127.0.0.1"
    assert c.port == 7777
    assert c.user == "ccc"
    assert c.idle_timeout == 600
    assert c.first_event_timeout == 120


def test_chat_server_config_env_priority(monkeypatch):
    """env 优先于默认。"""
    from chat_server.config import ChatServerConfig

    monkeypatch.setenv("CCC_CHAT_HOST", "0.0.0.0")
    monkeypatch.setenv("CCC_CHAT_PORT", "9999")
    monkeypatch.setenv("CCC_CHAT_USER", "bob")
    c = ChatServerConfig.from_env()
    assert c.host == "0.0.0.0"
    assert c.port == 9999
    assert c.user == "bob"


def test_chat_server_config_legacy_compat():
    """旧模块级全局(HOST/PORT/AUTH_USER 等)仍可用,不破坏现有 import。"""
    from chat_server import config

    assert config.HOST == "127.0.0.1"
    assert config.PORT == 7777
    assert config.AUTH_USER == "ccc"
    assert isinstance(config.CHAT_IDLE_TIMEOUT, int)
    assert config.CHAT_IDLE_TIMEOUT > 0
    assert config.BOARD_URL.startswith("http")


def test_chat_server_config_new_and_old_consistent():
    """新 ChatServerConfig 与旧全局变量默认值一致(契约验证)。"""
    from chat_server import config
    from chat_server.config import ChatServerConfig

    c = ChatServerConfig()
    assert c.host == config.HOST
    assert c.port == config.PORT
    assert c.user == config.AUTH_USER
    assert c.idle_timeout == config.CHAT_IDLE_TIMEOUT
    assert c.first_event_timeout == config.CHAT_FIRST_EVENT_TIMEOUT
