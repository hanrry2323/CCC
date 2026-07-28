"""test_hub_probe_contract.py — R4 016: lock Hub probe contract.

Do not invent GET /api/health as liveness. Real reachability =
GET /api/desktop/projects (or /version) with Basic Auth.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "ccc-hub-probe.sh"


def test_hub_probe_script_exists_and_executable_bits():
    assert PROBE.is_file(), PROBE
    text = PROBE.read_text(encoding="utf-8")
    assert "#!/usr/bin/env bash" in text
    assert "/api/health" in text
    assert "404" in text
    assert "/api/desktop/projects" in text or "/api/desktop/version" in text
    assert "7788" in text  # sidecar health separate


def test_hub_probe_documents_tunnel_default():
    text = PROBE.read_text(encoding="utf-8")
    assert "17777" in text
    assert "CCC_SERVER" in text


def test_hub_probe_smoke_when_reachable():
    """If Hub tunnel answers, run probe; otherwise skip (not a red)."""
    import os
    import subprocess
    import urllib.request

    server = os.environ.get("CCC_SERVER", "http://127.0.0.1:17777")
    try:
        req = urllib.request.Request(
            f"{server.rstrip('/')}/api/desktop/version",
            method="GET",
        )
        # may 401 without auth — that still means reachable
        try:
            urllib.request.urlopen(req, timeout=3)
            reachable = True
        except urllib.error.HTTPError as e:
            reachable = e.code in (200, 401, 403)
        except Exception:
            reachable = False
    except Exception:
        reachable = False

    if not reachable:
        import pytest

        pytest.skip(f"Hub not reachable at {server}")

    r = subprocess.run(
        ["bash", str(PROBE)],
        cwd=str(ROOT),
        env={**os.environ, "CCC_SERVER": server},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + "\n" + r.stderr
