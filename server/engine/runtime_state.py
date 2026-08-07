"""Engine 运行时卡状态（非 git）——主树干净化的地基。

卡文件只做 main 镜像（永不写脏）；「待分派→执行中→已回写→打回」等流程态、
重试计数与重派指令写入 ``EXECUTOR_LOG_DIR/state/cards.jsonl``（append-only，
同一 id 末条为准）。看板以「git 卡真相 + 运行时状态 + 分支信封证据」合成视图。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.engine.runtime_state")

STATE_REL = Path("state/cards.jsonl")


def _utcnow_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def read_card_state(log_dir: str | Path) -> dict[str, dict[str, Any]]:
    """读全部运行时卡状态（last-wins）；文件缺失/坏行容错。"""
    path = Path(log_dir) / STATE_REL
    out: dict[str, dict[str, Any]] = {}
    try:
        if not path.is_file():
            return out
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("id"):
                out[str(rec["id"])] = rec
    except OSError:
        logger.exception("读取运行时卡状态失败: %s", path)
    return out


def write_card_state(
    log_dir: str | Path,
    card_id: str,
    *,
    state: str | None = None,
    retry_count: int | None = None,
    reason: str = "",
    redispatch: str | None = None,
    infra_cooldown_until: str | None = None,
) -> None:
    """追加一条运行时状态（调用方给定字段；缺省保持历史不变）。"""
    rec: dict[str, Any] = {"id": card_id, "ts": _utcnow_iso()}
    if state is not None:
        rec["state"] = state
    if retry_count is not None:
        rec["retry_count"] = int(retry_count)
    if reason:
        rec["reason"] = reason[:200]
    if redispatch is not None:
        rec["redispatch"] = redispatch
    if infra_cooldown_until is not None:
        rec["infra_cooldown_until"] = infra_cooldown_until
    try:
        path = Path(log_dir) / STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("写运行时卡状态失败: %s (%s)", path, card_id)
