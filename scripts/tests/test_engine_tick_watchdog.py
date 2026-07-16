"""H7: engine tick heartbeat helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        "ccc_engine_wd", SCRIPTS / "ccc-engine.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mark_engine_tick_writes_loop_heartbeat(tmp_path, monkeypatch):
    engine = _load_engine()
    hb = tmp_path / "engine-loop-heartbeat.json"
    monkeypatch.setattr(engine, "_loop_heartbeat_path", lambda: hb)
    before = time.monotonic()
    engine._mark_engine_tick()
    assert hb.is_file()
    data = json.loads(hb.read_text(encoding="utf-8"))
    assert "timestamp" in data
    assert data["pid"] > 0
    assert engine._last_tick_mono >= before
