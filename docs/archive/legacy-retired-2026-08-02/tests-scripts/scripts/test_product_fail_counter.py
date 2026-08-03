"""Product fail counter: no wipe-to-zero decay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _product_fail_counter import (  # noqa: E402
    load_product_fail_count,
    write_product_fail_count,
)


def test_no_full_wipe_after_idle(tmp_path: Path):
    p = tmp_path / "t.json"
    write_product_fail_count(p, 2, now=1000.0)
    count, msg = load_product_fail_count(
        p, now=1000.0 + 901, decay_sec=900, max_retries=3
    )
    assert count == 1
    assert msg and "→ 1" in msg
    assert json.loads(p.read_text())["fail_count"] == 1


def test_freeze_at_max_retries(tmp_path: Path):
    p = tmp_path / "t.json"
    write_product_fail_count(p, 3, now=1000.0)
    count, msg = load_product_fail_count(
        p, now=1000.0 + 10_000, decay_sec=900, max_retries=3
    )
    assert count == 3
    assert msg is None


def test_within_window_unchanged(tmp_path: Path):
    p = tmp_path / "t.json"
    write_product_fail_count(p, 2, now=1000.0)
    count, msg = load_product_fail_count(
        p, now=1000.0 + 100, decay_sec=900, max_retries=3
    )
    assert count == 2
    assert msg is None
