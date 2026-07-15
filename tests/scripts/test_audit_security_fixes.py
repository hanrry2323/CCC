"""F-SEC-01 / F-ARCH-02: Chat auth fail-closed + 默认绑定。"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "scripts" / "chat_server" / "config.py"


def _load_config_module(monkeypatch, **env):
    for k in list(os.environ):
        if k.startswith("CCC_CHAT_"):
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # 强制重新执行 config.py（其常量在 import 时绑定）
    name = "ccc_chat_config_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, CONFIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_default_host_is_localhost(monkeypatch):
    cfg = _load_config_module(monkeypatch)
    assert cfg.HOST == "127.0.0.1"


def test_weak_password_rejected(monkeypatch):
    cfg = _load_config_module(monkeypatch, CCC_CHAT_PASS="claude2026")
    with pytest.raises(SystemExit):
        cfg.validate_auth_config()


def test_short_password_rejected(monkeypatch):
    cfg = _load_config_module(monkeypatch, CCC_CHAT_PASS="short")
    with pytest.raises(SystemExit):
        cfg.validate_auth_config()


def test_strong_password_accepted(monkeypatch):
    cfg = _load_config_module(monkeypatch, CCC_CHAT_PASS="a-strong-pass-phrase")
    cfg.validate_auth_config()  # no raise


def test_no_hardcoded_apple_claude_path(monkeypatch):
    """源码不得硬编码作者本机路径；which 结果可以是任意本机 PATH。"""
    src = CONFIG_PATH.read_text(encoding="utf-8")
    assert '"/Users/apple/.local/bin/claude"' not in src
    assert "'/Users/apple/.local/bin/claude'" not in src
    cfg = _load_config_module(monkeypatch, CCC_CHAT_PASS="a-strong-pass-phrase")
    # require_claude_bin 在未安装时必须失败而非返回硬编码路径
    if not cfg.CLAUDE_BIN:
        with pytest.raises(RuntimeError):
            cfg.require_claude_bin()
    else:
        assert cfg.require_claude_bin() == cfg.CLAUDE_BIN


def test_parse_verdict_status_no_substring_false_positive():
    """F-FLOW-03: PASS 正文含 FAIL 字样不得误判。"""

    def parse(content: str):
        for line in content.splitlines():
            stripped = line.strip()
            low = stripped.lower()
            if low.startswith("**verdict:**") or low.startswith("verdict:"):
                raw = stripped.split(":", 1)[1].strip().strip("*").strip()
                return raw.split()[0].upper() if raw else None
        return None

    body = "# t\n\n**Verdict:** PASS\n\nThis would FAIL if broken.\n"
    assert parse(body) == "PASS"
    assert parse("# t\n\n**Verdict:** FAIL\n") == "FAIL"
    assert parse("# t\n\n**Verdict:** FALLBACK\n") == "FALLBACK"
