"""Hub remote-chat thread partition helpers."""

import pytest

from chat_server.routers.remote_chat import (
    HUB_THREAD_PREFIX,
    normalize_hub_thread_id,
)


def test_default_thread_id():
    assert normalize_hub_thread_id("ccc-demo", None) == "hub::ccc-demo::main"
    assert normalize_hub_thread_id("ccc-demo", "") == "hub::ccc-demo::main"


def test_accepts_hub_prefix():
    tid = "hub::ccc-demo::smoke-1"
    assert normalize_hub_thread_id("ccc-demo", tid) == tid


def test_rejects_desktop_thread():
    with pytest.raises(ValueError) as ei:
        normalize_hub_thread_id("ccc-demo", "ccc-demo::main")
    assert "hub::" in str(ei.value)


def test_prefix_constant():
    assert HUB_THREAD_PREFIX == "hub::"
