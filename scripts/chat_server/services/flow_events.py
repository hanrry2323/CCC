"""编排流程事件 — Desktop 右栏 SSE / 快照。

契约：docs/product/flow-events.md
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from .. import config

_DEFAULT_LOG = Path.home() / ".ccc" / "flow-events.jsonl"


def events_log_path() -> Path:
    raw = os.environ.get("CCC_FLOW_EVENTS_LOG", "").strip()
    return Path(raw) if raw else _DEFAULT_LOG


def append_event(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """追加一条事件到 Server 本地 JSONL。"""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "event": event_type,
        "data": data,
    }
    path = events_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_events(
    *,
    project_id: str | None = None,
    epic_id: str | None = None,
    after_ts: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    path = events_log_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-max(limit * 4, 400) :]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        data = rec.get("data") or {}
        if project_id and str(data.get("project_id") or "") != project_id:
            continue
        if epic_id and str(data.get("epic_id") or "") != epic_id:
            continue
        if after_ts and str(rec.get("ts") or "") <= after_ts:
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def latest_transfer_epic_id(project_id: str) -> str | None:
    """从事件日志取该项目最近一次 epic_created。"""
    events = read_events(project_id=project_id, limit=500)
    for rec in reversed(events):
        if rec.get("event") == "epic_created":
            eid = (rec.get("data") or {}).get("epic_id")
            if eid:
                return str(eid)
    return None


def snapshot_from_board(
    store_board: dict[str, list[dict]],
    *,
    epic_id: str,
    project_id: str,
) -> dict[str, Any]:
    """从看板快照合成右栏图数据。"""
    epic = None
    works: list[dict] = []
    for col, tasks in (store_board or {}).items():
        for t in tasks or []:
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or "")
            if tid == epic_id:
                epic = {**t, "column": col}
            elif str(t.get("parent_id") or "") == epic_id:
                works.append(
                    {
                        "id": tid,
                        "title": t.get("title") or tid,
                        "status": col,
                        "executor": t.get("executor") or "opencode",
                        "depends_on": t.get("depends_on_tasks") or [],
                        "split_status": t.get("split_status"),
                    }
                )
    return {
        "project_id": project_id,
        "epic_id": epic_id,
        "epic": epic,
        "works": works,
    }


def format_sse(event: str, data: dict | list | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def iter_sse_heartbeat_and_poll(
    *,
    fetch_snapshot,
    interval: float = 2.0,
    heartbeat: float = 15.0,
) -> Iterator[str]:
    """简易轮询合成 SSE（MVP）。"""
    last_sig = ""
    last_beat = 0.0
    while True:
        now = time.time()
        try:
            snap = fetch_snapshot()
            sig = json.dumps(snap, sort_keys=True, ensure_ascii=False)
            if sig != last_sig:
                last_sig = sig
                yield format_sse("fanout", {
                    "epic_id": snap.get("epic_id"),
                    "works": snap.get("works") or [],
                })
                for w in snap.get("works") or []:
                    yield format_sse(
                        "work_status",
                        {
                            "epic_id": snap.get("epic_id"),
                            "work_id": w.get("id"),
                            "status": w.get("status"),
                            "executor": w.get("executor"),
                        },
                    )
        except Exception as exc:
            yield format_sse("error", {"message": str(exc)[:200]})
        if now - last_beat >= heartbeat:
            last_beat = now
            yield format_sse("ping", {"t": int(now)})
        time.sleep(interval)


# 供测试注入 chat dir 旁路
def project_last_epic_file(project_id: str) -> Path:
    d = config.CHAT_DIR / "_desktop" / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "last_epic.json"


def remember_last_epic(project_id: str, epic_id: str, title: str = "") -> None:
    path = project_last_epic_file(project_id)
    path.write_text(
        json.dumps(
            {
                "epic_id": epic_id,
                "title": title,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_last_epic(project_id: str) -> dict | None:
    path = project_last_epic_file(project_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None
