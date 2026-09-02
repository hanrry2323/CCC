"""scripts/ops/dsh_key_probe.py 三态判定测试（P0-1）。

不访问真实网络：monkeypatch urllib.request.urlopen（正常响应 / HTTPError / 网络异常）。
所有非 PASS 状态断言退出码非 0（P0-1 红线：异常不得 PASS）。
"""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

_PROBE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "dsh_key_probe.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("dsh_key_probe", _PROBE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dsh_key_probe = _load_probe()


class _FakeResp:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture()
def fake_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsh_key_probe, "_resolve_probe_url", lambda: "http://127.0.0.1:3456/v1/messages")
    monkeypatch.setattr(dsh_key_probe, "_resolve_probe_model", lambda: "claude-4-5-haiku")


def _ok_body() -> bytes:
    return json.dumps({"content": [{"type": "text", "text": "ok"}], "model": "claude-4-5-haiku"}).encode()


def _monkey_urlopen(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    monkeypatch.setattr(dsh_key_probe.urllib.request, "urlopen", fn)


def _exit_of(r: dict) -> int:
    return dsh_key_probe.EXIT_BY_STATUS[r["status"]]


def test_probe_ok(fake_probe, monkeypatch) -> None:
    _monkey_urlopen(monkeypatch, lambda req, **k: _FakeResp(200, _ok_body()))
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "ok"
    assert _exit_of(r) == 0


def test_probe_quota_exhausted(fake_probe, monkeypatch) -> None:
    def _boom(req, **k):
        raise urllib.error.HTTPError("http://x", 429, "x", {}, None)

    _monkey_urlopen(monkeypatch, _boom)
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "quota_exhausted"
    assert _exit_of(r) == 2


@pytest.mark.parametrize("code", [401, 403])
def test_probe_auth_error(fake_probe, monkeypatch, code: int) -> None:
    def _boom(req, **k):
        raise urllib.error.HTTPError("http://x", code, "x", {}, None)

    _monkey_urlopen(monkeypatch, _boom)
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "auth_error"
    assert _exit_of(r) == 3


@pytest.mark.parametrize("code", [500, 503])
def test_probe_upstream_error(fake_probe, monkeypatch, code: int) -> None:
    def _boom(req, **k):
        raise urllib.error.HTTPError("http://x", code, "x", {}, None)

    _monkey_urlopen(monkeypatch, _boom)
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "upstream_error"
    assert _exit_of(r) == 4


def test_probe_unknown_http_is_error(fake_probe, monkeypatch) -> None:
    def _boom(req, **k):
        raise urllib.error.HTTPError("http://x", 418, "x", {}, None)

    _monkey_urlopen(monkeypatch, _boom)
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "error"
    assert _exit_of(r) == 7


def test_probe_empty_200_unavailable(fake_probe, monkeypatch) -> None:
    _monkey_urlopen(monkeypatch, lambda req, **k: _FakeResp(200, b""))
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "unavailable"
    assert _exit_of(r) == 5


def test_probe_unparseable_200_unavailable(fake_probe, monkeypatch) -> None:
    _monkey_urlopen(monkeypatch, lambda req, **k: _FakeResp(200, b"garbage-not-json"))
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "unavailable"
    assert _exit_of(r) == 5


def test_probe_no_marker_200_unavailable(fake_probe, monkeypatch) -> None:
    _monkey_urlopen(monkeypatch, lambda req, **k: _FakeResp(200, b'{"foo": 1}'))
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "unavailable"


def test_probe_network_error_unavailable(fake_probe, monkeypatch) -> None:
    def _boom(req, **k):
        raise urllib.error.URLError("dns resolution failed")

    _monkey_urlopen(monkeypatch, _boom)
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "unavailable"
    assert _exit_of(r) == 5


def test_probe_no_config_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(dsh_key_probe, "_resolve_probe_url", lambda: "")
    monkeypatch.setattr(dsh_key_probe, "_resolve_probe_model", lambda: "")
    r = dsh_key_probe.probe("sk-fake")
    assert r["status"] == "unavailable"


def test_classify_never_ok_on_anomaly() -> None:
    """红线：000/空/解析失败/无标记/未知/上游/配额 → 一律非 ok。"""
    assert dsh_key_probe.classify(0, "") != "ok"
    assert dsh_key_probe.classify(200, "", "") != "ok"
    assert dsh_key_probe.classify(200, "", "garbage") != "ok"
    assert dsh_key_probe.classify(200, "", '{"foo":1}') != "ok"
    assert dsh_key_probe.classify(418, "") != "ok"
    assert dsh_key_probe.classify(500, "") != "ok"
    assert dsh_key_probe.classify(429, "") != "ok"


def test_resolve_key_env_priority(monkeypatch) -> None:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "sk-env-fake")
    assert dsh_key_probe.resolve_key() == "sk-env-fake"


def test_no_key_and_error_exit_codes() -> None:
    assert dsh_key_probe.EXIT_BY_STATUS["no_key"] == 6
    assert dsh_key_probe.EXIT_BY_STATUS["error"] == 7
    assert dsh_key_probe.EXIT_BY_STATUS["unavailable"] == 5
    assert dsh_key_probe.EXIT_BY_STATUS["quota_exhausted"] == 2
