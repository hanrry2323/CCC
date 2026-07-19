"""Product fail counter — persist retries without wipe-to-zero decay.

Root cause (2026-07-19): engine reset fail_count→0 after 15min idle, so
desktop-smoke epics never hit ``_MAX_PRODUCT_RETRIES`` and re-launched forever
(``process not running`` / async timeout loops).

Upstream downtime already skips without incrementing; full reset is wrong.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

def load_product_fail_count(
    path: Path,
    *,
    now: float | None = None,
    decay_sec: int = 900,
    max_retries: int = 3,
    step_decay: bool = True,
) -> tuple[int, str | None]:
    """Load fail_count from ``.ccc/.product-fail-counter/<tid>.json``.

    Returns ``(fail_count, log_message_or_None)``.

    Rules:
    - Missing/corrupt → 0
    - ``fail_count >= max_retries`` → freeze (no decay); exhausted stays exhausted
    - After ``decay_sec`` since last fail: optionally step down by 1 (not wipe to 0)
    """
    if not path.is_file():
        return 0, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, None

    fail_count = int(data.get("fail_count") or 0)
    last_failed = float(data.get("last_failed_at") or 0)
    if fail_count <= 0:
        return 0, None

    if fail_count >= max_retries:
        return fail_count, None

    if not last_failed or not step_decay or decay_sec <= 0:
        return fail_count, None

    ts = time.time() if now is None else now
    elapsed = ts - last_failed
    if elapsed <= decay_sec:
        return fail_count, None

    new_count = max(0, fail_count - 1)
    msg = (
        f"fail_counter {fail_count} → {new_count} "
        f"(step decay after {elapsed:.0f}s > {decay_sec}s; never wipe to 0 in one shot)"
    )
    try:
        path.write_text(
            json.dumps(
                {"fail_count": new_count, "last_failed_at": ts},
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return fail_count, None
    return new_count, msg


def write_product_fail_count(path: Path, fail_count: int, *, now: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.time() if now is None else now
    path.write_text(
        json.dumps({"fail_count": fail_count, "last_failed_at": ts}, indent=2),
        encoding="utf-8",
    )


def clear_product_fail_count(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass
