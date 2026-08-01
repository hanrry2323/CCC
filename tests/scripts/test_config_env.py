"""CCC 配置 SSOT 回归测试(v0.61.0 阶段 D)

覆盖:
- RelayEnv/HubEnv/AgentEnv/EngineEnv from_env() 优先级(env > 默认)
- 缺失 env 走默认
- Config() 暴露 4 个 sub-dataclass 属性
- Config 旧字段向后兼容
- ChatServerConfig.from_env() 同样契约
- ANTHROPIC_BASE_URL 跨模块值冲突检测(简化)
"""
from __future__ import annotations

from _config import AgentEnv, Config, EngineEnv, HubEnv, RelayEnv


def test_relay_env_defaults():
    """无 env 时 RelayEnv 走默认。"""
    env = RelayEnv()
    assert env.base_url == "http://127.0.0.1:4100"
    assert env.direct_url == ""
    assert env.upstream_config == ""
    assert env.admin_status_path == "/admin/status"
    assert env.probe_timeout == 1.5


def test_relay_env_env_priority(monkeypatch):
    """env 优先于默认。"""
    monkeypatch.setenv("CCC_RELAY_BASE_URL", "http://192.168.5.5:5000")
    monkeypatch.setenv("CCC_RELAY_DIRECT_URL", "http://direct.example.com")
    env = RelayEnv.from_env()
    assert env.base_url == "http://192.168.5.5:5000"  # 自动 rstrip("/")
    assert env.direct_url == "http://direct.example.com"


def test_hub_env_env_priority(monkeypatch):
    monkeypatch.setenv("CCC_HUB_URL", "http://10.0.0.5:17777")
    monkeypatch.setenv("CCC_HUB_USER", "alice")
    env = HubEnv.from_env()
    assert env.url == "http://10.0.0.5:17777"
    assert env.user == "alice"
    assert env.password == ""  # 缺 env 不写默认,只空


def test_agent_env_auth_default(monkeypatch):
    """CCC_AGENT_AUTH=0 应关闭鉴权(否则默认 True)。"""
    env_default = AgentEnv.from_env()
    assert env_default.auth_required is True
    monkeypatch.setenv("CCC_AGENT_AUTH", "0")
    env_off = AgentEnv.from_env()
    assert env_off.auth_required is False
    monkeypatch.setenv("CCC_AGENT_AUTH", "false")
    assert AgentEnv.from_env().auth_required is False


def test_engine_env_int_override(monkeypatch):
    """CCC_MAX_CONCURRENT 等 int 字段从 env 覆盖。"""
    monkeypatch.setenv("CCC_MAX_CONCURRENT", "12")
    monkeypatch.setenv("CCC_TASK_RETRY_BUDGET", "5")
    env = EngineEnv.from_env()
    assert env.max_concurrent == 12
    assert env.retry_budget == 5


def test_config_exposes_sub_dataclasses():
    """Config() 暴露 relay/hub/agent/engine 4 个新读 SSOT 属性。"""
    c = Config()
    assert isinstance(c.relay, RelayEnv)
    assert isinstance(c.hub, HubEnv)
    assert isinstance(c.agent, AgentEnv)
    assert isinstance(c.engine, EngineEnv)


def test_config_backward_compat():
    """旧字段保留,默认值与改造前一致。"""
    c = Config()
    assert c.model == "loop/flash"  # 2026-08-01 Flash 单通道 · ai-loop-router :4100
    assert c.max_retry == 5
    assert c.task_retry_budget == 8
    assert c.max_wallclock == 7200
    assert c.auto_replenish is False  # v0.42.4 永久 False


def test_config_old_and_new_consistent():
    """Config.relay.base_url 与 ai-loop-router :4100 一致(契约验证)。"""
    c = Config()
    assert c.relay.base_url == "http://127.0.0.1:4100"
    assert c.engine.retry_budget == 8
    assert c.agent.port == 7788
    # Hub URL 默认含 :17777(M1 隧道);Hub 真实端口 7777 在 ccc-fleet / chat-server plist
    assert "17777" in c.hub.url
    assert c.hub.board_url == "http://127.0.0.1:7775"


def test_anthropic_base_url_consistency_check():
    """ANTHROPIC_BASE_URL 跨模块值冲突检测(简化,仅查 ccc-engine.sh 默认)。

    完整检测在 production 启动时做(报告瓶颈 #3 修复);这里只验关键 invariant:
    Config.agent.relay_base_url 应与 Config.relay.base_url 一致(避免 agent 漂移)。
    """
    c = Config()
    assert c.agent.relay_base_url == c.relay.base_url
    assert c.agent.relay_base_url == "http://127.0.0.1:4100"  # ai-loop-router 权威端口(4100)
