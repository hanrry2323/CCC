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
    """读全部运行时卡状态（按字段 last-wins 合并）；文件缺失/坏行容错。

    追加记录可能只携带部分字段（如收单后 ``infra_count=0`` 记录不含 state）。
    若按「整条记录覆盖」，部分字段记录会顶掉先前写好的 state，导致
    已回写卡被误判回待分派（引擎死循环重跑开发体、机审永不启动）。
    """
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
                cid = str(rec["id"])
                # 支持 null/None 失效语义：若最后更新为 null 状态，则认为无状态
                if "state" in rec and rec["state"] is None:
                    out.pop(cid, None)
                else:
                    # 按字段合并：缺省字段沿用历史，避免部分字段记录顶掉 state
                    out.setdefault(cid, {}).update(rec)
    except OSError:
        logger.exception("读取运行时卡状态失败: %s", path)
    return out


def clear_card_state(log_dir: str | Path, card_id: str) -> None:
    """清除一个卡的 sidecar 流程态（追加一条 state=None/null 失效记录）。"""
    rec: dict[str, Any] = {
        "id": card_id,
        "ts": _utcnow_iso(),
        "state": None
    }
    try:
        path = Path(log_dir) / STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("写失效运行时卡状态失败: %s (%s)", path, card_id)


def write_card_state(
    log_dir: str | Path,
    card_id: str,
    *,
    state: str | None = None,
    retry_count: int | None = None,
    reason: str = "",
    redispatch: str | None = None,
    infra_cooldown_until: str | None = None,
    infra_count: int | None = None,
    conflict_strikes: int | None = None,
    light_fix_count: int | None = None,
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
    if infra_count is not None:
        rec["infra_count"] = int(infra_count)
    if conflict_strikes is not None:
        rec["conflict_strikes"] = int(conflict_strikes)
    if light_fix_count is not None:
        rec["light_fix_count"] = int(light_fix_count)
    try:
        path = Path(log_dir) / STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        logger.exception("写运行时卡状态失败: %s (%s)", path, card_id)
