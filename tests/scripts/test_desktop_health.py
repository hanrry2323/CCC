"""Desktop Hub 轻量 health 探活。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from chat_server.app import create_app  # noqa: E402


def _auth() -> tuple[str, str]:
    return (
        os.environ.get("CCC_CHAT_USER", "ccc"),
        os.environ.get("CCC_CHAT_PASS", "ccc"),
    )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_desktop_health_ok(client: TestClient):
    r = client.get("/api/desktop/health", auth=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("ts")


def test_desktop_health_requires_auth(client: TestClient):
    r = client.get("/api/desktop/health")
    assert r.status_code in (401, 403)
