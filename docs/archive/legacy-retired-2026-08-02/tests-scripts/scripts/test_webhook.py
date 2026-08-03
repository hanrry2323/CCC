"""test_webhook.py — _webhook 模块单元测试 (v0.51.0 P1-10)

覆盖:
  - _guess_format: feishu / dingtalk / generic 三种 URL 推断
  - _build_payload: 三种格式的 payload 结构正确性
  - send_webhook: 空 URL 跳过 / HTTP 200 / HTTP 非 200 / URLError / OSError / ValueError

业务关键性：L3 告警通道，发不通会静默吞掉故障通知（engine 重启失败 / 紧急人工介入）。
"""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _webhook import _build_payload, _guess_format, send_webhook  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# _guess_format
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://open.feishu.cn/open-apis/bot/v2/hook/xxx", "feishu"),
        ("https://Feishu.example.com/hook", "feishu"),
        ("https://oapi.dingtalk.com/robot/send?access_token=xxx", "dingtalk"),
        ("https://DingTalk.example.com/hook", "dingtalk"),
        ("https://example.com/webhook", "generic"),
        ("https://hooks.slack.com/services/xxx", "generic"),
        ("", "generic"),  # 空 URL 也走 generic 分支（实际发送前会被跳过）
    ],
)
def test_guess_format(url: str, expected: str):
    assert _guess_format(url) == expected


# ──────────────────────────────────────────────────────────────────
# _build_payload
# ──────────────────────────────────────────────────────────────────


def test_build_payload_feishu_structure():
    payload = _build_payload("L3", "Engine 重启失败", "需人工介入", "feishu")
    assert payload["msg_type"] == "post"
    post = payload["content"]["post"]["zh_cn"]
    assert post["title"] == "[CCC L3] Engine 重启失败"
    # content 是嵌套列表结构
    assert isinstance(post["content"], list)
    assert any("需人工介入" in c.get("text", "") for row in post["content"] for c in row)
    # 时间戳应出现在文本里
    assert any("时间:" in c.get("text", "") for row in post["content"] for c in row)


def test_build_payload_dingtalk_structure():
    payload = _build_payload("L2", "Patrol alert", "stale task", "dingtalk")
    assert payload["msgtype"] == "markdown"
    md = payload["markdown"]
    assert md["title"] == "[CCC L2] Patrol alert"
    assert "stale task" in md["text"]
    assert "### [CCC L2] Patrol alert" in md["text"]


def test_build_payload_generic_structure():
    payload = _build_payload("L1", "Info", "ops tick", "generic")
    assert payload["title"] == "Info"
    assert payload["message"] == "ops tick"
    assert payload["level"] == "L1"
    assert payload["source"] == "patrol-v4"
    assert "timestamp" in payload
    # timestamp 应是 ISO8601 UTC（结尾 Z）
    assert payload["timestamp"].endswith("Z")


def test_build_payload_unknown_format_falls_back_to_generic():
    payload = _build_payload("L1", "t", "m", "totally-unknown-fmt")
    assert payload["source"] == "patrol-v4"
    assert payload["title"] == "t"


# ──────────────────────────────────────────────────────────────────
# send_webhook
# ──────────────────────────────────────────────────────────────────


class _FakeResponse:
    """urllib.request.urlopen 上下文管理器替身。"""

    def __init__(self, status: int = 200, body: bytes = b"OK"):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self.body


def test_send_webhook_empty_url_skipped():
    """空 URL / 纯空白 URL 应当跳过发送，返回 True。"""
    assert send_webhook("", "L1", "t", "m") is True
    assert send_webhook("   \t\n  ", "L1", "t", "m") is True


def test_send_webhook_http_200_success(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):  # noqa: ARG001
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["data"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = dict(req.headers)
        return _FakeResponse(status=200, body=b'{"ok":true}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert send_webhook(
        "https://example.com/webhook", "L2", "title", "msg"
    ) is True
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/webhook"
    assert captured["headers"].get("Content-type", "").startswith("application/json")
    assert captured["data"]["title"] == "title"
    assert captured["data"]["message"] == "msg"


def test_send_webhook_http_non_200_returns_false(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: _FakeResponse(status=500, body=b"server error"),  # noqa: ARG005
    )
    assert send_webhook("https://example.com/h", "L1", "t", "m") is False


def test_send_webhook_url_error_returns_false(monkeypatch):
    def raise_url_error(req, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", raise_url_error)
    assert send_webhook("https://example.com/h", "L3", "t", "m") is False


def test_send_webhook_os_error_returns_false(monkeypatch):
    def raise_os_error(req, timeout):  # noqa: ARG001
        raise OSError("network unreachable")

    monkeypatch.setattr("urllib.request.urlopen", raise_os_error)
    assert send_webhook("https://example.com/h", "L3", "t", "m") is False


def test_send_webhook_value_error_returns_false(monkeypatch):
    """urlopen 返回非法响应（read 出错抛 ValueError）应静默返回 False。"""

    class _BadResponse(_FakeResponse):
        def read(self) -> bytes:
            raise ValueError("bad bytes")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: _BadResponse(status=200),  # noqa: ARG005
    )
    assert send_webhook("https://example.com/h", "L1", "t", "m") is False


def test_send_webhook_feishu_payload_actually_posted(monkeypatch):
    """验证飞书 URL 会触发 feishu 格式 payload，并真正调用 urlopen。"""
    captured = {}

    def fake_urlopen(req, timeout):  # noqa: ARG001
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(status=200)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert send_webhook(
        "https://open.feishu.cn/open-apis/bot/v2/hook/xxx", "L3", "重启", "需介入"
    ) is True
    assert captured["data"]["msg_type"] == "post"
