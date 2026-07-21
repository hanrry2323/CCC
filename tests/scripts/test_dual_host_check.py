"""F2-2: dual-host version check — Hub /api/desktop/version + check script."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CCC_CHAT_USER", "ccc")
    monkeypatch.setenv("CCC_CHAT_PASS", "ccc")
    from chat_server.app import create_app

    return TestClient(create_app())


def _auth():
    return ("ccc", "ccc")


def test_desktop_version_endpoint_readonly(client: TestClient):
    r = client.get("/api/desktop/version", auth=_auth())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert "version" in d and "commit" in d and "hub_api_version" in d
    assert d["hub_api_version"] == "v1"
    # VERSION file should match when present
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert d["version"] == ver
    assert isinstance(d["commit"], str)
    assert len(d["commit"]) >= 7


def test_desktop_version_requires_auth(client: TestClient):
    r = client.get("/api/desktop/version")
    assert r.status_code == 401


def test_read_hub_version_payload_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from chat_server.routers import desktop as desk

    (tmp_path / "VERSION").write_text("v9.9.9\n", encoding="utf-8")
    monkeypatch.setattr(desk, "_repo_root", lambda: tmp_path)
    # no .git → commit empty is ok
    payload = desk._read_hub_version_payload()
    assert payload["ok"] is True
    assert payload["version"] == "v9.9.9"
    assert payload["hub_api_version"] == "v1"


def _run_check(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["bash", str(SCRIPTS / "ccc-dual-host-check.sh")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=merged,
        timeout=30,
        check=False,
    )


def test_script_aligned_yes_with_mock():
    local_ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    local_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()
    mock = json.dumps(
        {
            "ok": True,
            "version": local_ver,
            "commit": local_commit,
            "hub_api_version": "v1",
        }
    )
    proc = _run_check({"CCC_DUAL_HOST_MOCK_JSON": mock})
    assert proc.returncode == 0, proc.stderr + proc.stdout
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    assert lines[0].startswith("M1: ")
    assert lines[1].startswith("2017: ") and " v1" in lines[1]
    assert lines[2] == "aligned: yes"


def test_script_version_mismatch_exits_1():
    local_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()
    mock = json.dumps(
        {
            "ok": True,
            "version": "v0.0.0-mismatch",
            "commit": local_commit,
            "hub_api_version": "v1",
        }
    )
    proc = _run_check({"CCC_DUAL_HOST_MOCK_JSON": mock})
    assert proc.returncode == 1
    assert "aligned: no" in proc.stdout
    assert "mismatch: version" in proc.stdout


def test_script_unsupported_hub_api_exits_1():
    local_ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    local_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
    ).strip()
    mock = json.dumps(
        {
            "ok": True,
            "version": local_ver,
            "commit": local_commit,
            "hub_api_version": "v9",
        }
    )
    proc = _run_check({"CCC_DUAL_HOST_MOCK_JSON": mock})
    assert proc.returncode == 1
    assert "hub_api_version" in proc.stdout
    assert "aligned: no" in proc.stdout


def test_script_hub_unreachable_exits_nonzero():
    env = os.environ.copy()
    env["CCC_SERVER"] = "http://127.0.0.1:1"
    env.pop("CCC_DUAL_HOST_MOCK_JSON", None)
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "ccc-dual-host-check.sh")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0
    assert "Hub unreachable" in (proc.stderr + proc.stdout)
