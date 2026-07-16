"""upstream probe + reviewer fallback mode unit tests (v0.40.1)"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "ccc_engine", SCRIPTS / "ccc-engine.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Avoid running main on import side effects beyond module body
    spec.loader.exec_module(mod)
    return mod


def test_upstream_4xx_is_healthy(monkeypatch):
    engine = _load_engine()
    engine._upstream_health_cache.clear()
    monkeypatch.delenv("CCC_UPSTREAM_STRICT", raising=False)

    class FakeHTTPError(Exception):
        def __init__(self):
            self.code = 401
            self.reason = "Unauthorized"

    import urllib.error

    # Use real HTTPError
    err = urllib.error.HTTPError(
        url="http://127.0.0.1:4000/v1/messages",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=err):
        assert engine._is_upstream_healthy() is True


def test_upstream_strict_requires_200(monkeypatch):
    engine = _load_engine()
    engine._upstream_health_cache.clear()
    monkeypatch.setenv("CCC_UPSTREAM_STRICT", "1")

    import urllib.error

    err = urllib.error.HTTPError(
        url="http://127.0.0.1:4000/v1/messages",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=err):
        assert engine._is_upstream_healthy() is False


def test_reviewer_fallback_default_static(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "ccc_board", SCRIPTS / "ccc-board.py"
    )
    board = importlib.util.module_from_spec(spec)
    monkeypatch.delenv("CCC_REVIEWER_FALLBACK", raising=False)
    spec.loader.exec_module(board)
    assert board._reviewer_fallback_mode() == "static"
    monkeypatch.setenv("CCC_REVIEWER_FALLBACK", "quarantine")
    assert board._reviewer_fallback_mode() == "quarantine"
