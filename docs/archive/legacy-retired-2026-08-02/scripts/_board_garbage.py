"""Board garbage classification — probe/stamp/e2e/regress noise must not revive.

Used by regress skip + hard quarantine. Real business cards (e.g. qb L3b) stay.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from _logger import get_logger

_log = get_logger("board_garbage")

# id / title substrings → non-product noise (never regress / never fanout)
_GARBAGE_ID_SUBSTR = (
    "regression-",
    "ccc-v0-63-desktop-loop-probe",
    "ccc-open-intent",
    "qb-biz-small",
    "qb-test-v63",
    "backlog-8-done",
    "layer1-",
    "layer2-lpsn",
    "ccc-qb-paper",
    "dashboard-smoke",
    "dry-run-paper-smoke",
    "env-checklist",
    "ccc-5pdq",
    "data-engine-order-gateway-plist",
    "gate-retest-",
    "human-supervised-",
    "epic-backlog-8-done",
    "stress-mx-",
    "flow-smoke-",
    "flow-green-",
    "flow-opt-",
    "vip-v5-paper-dry-run",
    "cla-obs1-",
    "cla-obs2-",
    "cla-obs3-",
    "hp-biz-small-",
    "xianyu-biz-small-",
    "phase8-hp-",
    "phase11-xianyu-",
    # 旧 momentum/testnet 失败尝试（精确 id，禁止前缀误杀新 epic）
    "p0-momentum-cost-edge-close-d6df424d",
    "p0-momentum-edge-close-272fb4ce",
    "p0-momentum-edge-close-paper-74664552",
)

_GARBAGE_TITLE_SUBSTR = (
    "戳记",
    "冒烟",
    "stamp=",
    "loop probe",
    "open-intent",
    "零改动链路",
    "desktop loop",
    "Layer2 开程",
    "LPSN 证据",
    "流水线烟测",
    "流水线绿灯",
    "纸面探针复验",
    "VIP-V5 paper",
    "门禁放行烟测",
)

_GARBAGE_TAGS = {
    "regression",
    "probe",
    "loop-probe",
    "open-intent",
    "e2e-smoke",
    "stamp",
    "hygiene-epic",
    "stress-kpi",
}


def is_garbage_board_card(
    task_id: str,
    task: dict[str, Any] | None = None,
) -> bool:
    """True = probe/stamp/regress/e2e noise — do not regress or product-fanout."""
    tid = (task_id or "").strip()
    if not tid:
        return False
    low = tid.lower()
    if any(s in low for s in _GARBAGE_ID_SUBSTR):
        return True
    if "testnet-40bps-paper-strategy-json-ma-cro" in low:
        return True
    title = str((task or {}).get("title") or "").lower()
    if any(s.lower() in title for s in _GARBAGE_TITLE_SUBSTR):
        # bare 探针 removed 2026-07-29: 业务 work title "编写 e2e_pipeline_probe.py 统一探针"不该拦截
        if "l3b" in low and ("momentum" in low or "testnet-40bps" in low):
            return False
        return True
    tags = {str(t).lower() for t in ((task or {}).get("tags") or [])}
    if tags & _GARBAGE_TAGS and not (
        "l3b" in low and ("momentum" in low or "testnet-40bps" in low)
    ):
        # bare "regression" tag on a real bugfix would be rare; id prefix already catches
        if "regression" in tags and tid.startswith("regression-"):
            return True
        if tags & (_GARBAGE_TAGS - {"regression"}):
            return True
    return False


def is_regress_eligible(task: dict[str, Any]) -> bool:
    """released → regress only for real product works, never garbage/hidden."""
    if not task or task.get("ui_hidden"):
        return False
    tid = str(task.get("id") or "")
    if is_garbage_board_card(tid, task):
        return False
    tags = {str(t).lower() for t in (task.get("tags") or [])}
    if "skip-regress" in tags or "no-regress" in tags:
        return False
    return True


_BOARD_COLS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)


def hard_quarantine_task(
    workspace: Path,
    task_id: str,
    *,
    reason: str = "hard_purge_garbage",
) -> dict[str, Any]:
    """Move board JSONL off the board into quarantines/<tid>/board-purge/ (no revive)."""
    tid = (task_id or "").strip()
    ws = Path(workspace)
    if not tid:
        return {"ok": False, "error": "missing_id"}
    qdir = ws / ".ccc" / "quarantines" / tid / "board-purge"
    qdir.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    board = ws / ".ccc" / "board"
    for col in _BOARD_COLS:
        src = board / col / f"{tid}.jsonl"
        if not src.is_file():
            continue
        dest = qdir / f"{col}.jsonl"
        try:
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))
            moved.append(col)
        except OSError as exc:
            _log.warning("hard_quarantine move %s: %s", src, exc)
    meta = {
        "id": tid,
        "reason": reason,
        "moved_from": moved,
    }
    (qdir / "purge.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"ok": True, "id": tid, "moved_from": moved}


def hard_quarantine_garbage(
    workspace: Path,
    *,
    reason: str = "hard_purge_garbage",
    also_empty_released: bool = True,
    keep_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Quarantine all garbage cards; optionally strip non-keep released (anti-regress flood)."""
    from _board_store import FileBoardStore

    ws = Path(workspace)
    store = FileBoardStore(ws)
    keep = set(keep_ids or ())
    targets: set[str] = set()
    for col in _BOARD_COLS:
        for t in store.list_tasks(col, include_hidden=True):
            tid = str(t.get("id") or "")
            if not tid or tid in keep:
                continue
            if is_garbage_board_card(tid, t):
                targets.add(tid)
            elif also_empty_released and col == "released" and tid not in keep:
                # released leftovers revive via regress even if not "garbage" pattern
                targets.add(tid)
    purged: list[dict[str, Any]] = []
    for tid in sorted(targets):
        purged.append(hard_quarantine_task(ws, tid, reason=reason))
    # touch index — FileBoardStore caches; next list rebuilds from disk
    idx = ws / ".ccc" / "board" / "index.json"
    if idx.is_file():
        try:
            idx.unlink()
        except OSError as exc:
            _log.debug("drop index after purge: %s", exc)
    return {"ok": True, "count": len(purged), "ids": sorted(targets), "details": purged}
