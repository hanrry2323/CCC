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
        if project_id:
            pid = str(data.get("project_id") or "").strip()
            if pid and pid != project_id:
                continue
            # 旧事件无 project_id：仅在带 epic_id 过滤时放行，避免串项目
            if not pid and not epic_id:
                continue
        if epic_id and str(data.get("epic_id") or "") != epic_id:
            continue
        if after_ts and str(rec.get("ts") or "") <= after_ts:
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def read_events_from_offset(
    offset: int,
    *,
    project_id: str | None = None,
    epic_id: str | None = None,
    after_ts: str | None = None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int, int]:
    """Phase 2.4: offset 增量读 — 只 seek + 读新行，不整文件 splitlines。

    Returns (new_events, new_offset, inode)。inode 变化表示日志被轮转，调用方应重置 offset。
    """
    path = events_log_path()
    if not path.is_file():
        return [], 0, 0
    try:
        st = path.stat()
    except OSError:
        return [], 0, 0
    inode = st.st_ino
    size = st.st_size
    # 文件被截断/轮转 → 从头读
    if offset > size:
        offset = 0
    out: list[dict[str, Any]] = []
    try:
        with path.open("rb") as f:
            f.seek(offset)
            for raw in f:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                data = rec.get("data") or {}
                if project_id:
                    pid = str(data.get("project_id") or "").strip()
                    if pid and pid != project_id:
                        continue
                    if not pid and not epic_id:
                        continue
                if epic_id and str(data.get("epic_id") or "") != epic_id:
                    continue
                if after_ts and str(rec.get("ts") or "") <= after_ts:
                    continue
                out.append(rec)
                if len(out) >= limit:
                    break
            new_offset = f.tell()
        # 若没读到行尾，回退到上一个 offset（半行下次再读）
        if new_offset > size:
            new_offset = size
        return out, new_offset, inode
    except OSError:
        return [], offset, inode


def latest_transfer_epic_id(project_id: str) -> str | None:
    """从事件日志取该项目最近一次 epic_created。"""
    events = read_events(project_id=project_id, limit=500)
    for rec in reversed(events):
        if rec.get("event") == "epic_created":
            eid = (rec.get("data") or {}).get("epic_id")
            if eid:
                return str(eid)
    return None


_STATUS_USER = {
    "backlog": "待办",
    "planned": "排队",
    "in_progress": "执行中",
    "testing": "验收中",
    "verified": "已通过",
    "released": "已完成",
    "abnormal": "异常",
}

_EXECUTOR_USER = {
    "opencode": "写码",
    "python": "脚本",
    "ollama": "本地模型",
    "cli": "命令行",
    "auto": "自动",
}


def _goal_summary_from_epic(epic: dict) -> str:
    desc = str(epic.get("description") or "")
    for marker in ("## 目标", "## Goal"):
        if marker in desc:
            part = desc.split(marker, 1)[1]
            for stop in ("## 验收", "## 验证", "## Plan", "## Transfer", "\n## "):
                if stop in part:
                    part = part.split(stop, 1)[0]
            line = " ".join(part.strip().split())
            if line:
                return line[:120]
    title = str(epic.get("title") or "").strip()
    return title[:120]


def _pipeline_from_epic(epic: dict) -> str:
    note = epic.get("note")
    if isinstance(note, str) and note.strip().startswith("{"):
        try:
            data = json.loads(note)
            tg = (data or {}).get("transfer_gate") or {}
            if tg.get("pipeline"):
                return str(tg["pipeline"])
        except json.JSONDecodeError:
            pass
    desc = str(epic.get("description") or "")
    for line in desc.splitlines():
        if "pipeline:" in line.lower():
            return line.split(":", 1)[-1].strip()[:40]
    return ""


def snapshot_from_board(
    store_board: dict[str, list[dict]],
    *,
    epic_id: str,
    project_id: str,
) -> dict[str, Any]:
    """从看板快照合成右栏图数据（含用户向字段）。"""
    epic = None
    works: list[dict] = []
    title_by_id: dict[str, str] = {}
    for col, tasks in (store_board or {}).items():
        for t in tasks or []:
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or "")
            if tid:
                title_by_id[tid] = str(t.get("title") or tid)
            if tid == epic_id:
                epic = {**t, "column": col}
            elif str(t.get("parent_id") or "") == epic_id:
                deps = t.get("depends_on_tasks") or []
                if not isinstance(deps, list):
                    deps = []
                status = col
                works.append(
                    {
                        "id": tid,
                        "title": t.get("title") or tid,
                        "status": status,
                        "user_status": _STATUS_USER.get(status, status),
                        "executor": t.get("executor") or "opencode",
                        "executor_label": _EXECUTOR_USER.get(
                            str(t.get("executor") or "opencode").lower(),
                            str(t.get("executor") or "opencode"),
                        ),
                        "depends_on": deps,
                        "depends_on_titles": [
                            title_by_id.get(str(d), str(d)) for d in deps
                        ],
                        "split_status": t.get("split_status"),
                        "note": (str(t.get("note") or "")[:200] or None),
                        "failure_note": (
                            str(t.get("note") or "")[:200]
                            if status == "abnormal"
                            else None
                        ),
                    }
                )

    # 二次填充 depends titles（同批创建时第一轮可能缺）
    for w in works:
        deps = w.get("depends_on") or []
        w["depends_on_titles"] = [title_by_id.get(str(d), str(d)) for d in deps]

    split = (epic or {}).get("split_status") or "pending"
    active = next(
        (w for w in works if w.get("status") in ("in_progress", "testing")),
        None,
    )
    failed = next((w for w in works if w.get("status") == "abnormal"), None)
    if failed:
        headline = f"卡住：{failed.get('title')}"
        stage = "failed"
    elif active:
        headline = f"正在：{active.get('title')}"
        stage = "running" if active.get("status") == "in_progress" else "testing"
    elif split == "done" or (
        works and all(w.get("status") in ("verified", "released") for w in works)
    ):
        headline = "已完成"
        stage = "done"
    elif works:
        headline = f"已拆 {len(works)} 步"
        stage = "planned"
    else:
        headline = "待拆解"
        stage = "pending"

    epic_view = None
    if epic:
        epic_view = {
            **epic,
            "goal_summary": _goal_summary_from_epic(epic),
            "pipeline": _pipeline_from_epic(epic),
            "user_stage": stage,
            "headline": headline,
        }

    return {
        "project_id": project_id,
        "epic_id": epic_id,
        "epic": epic_view,
        "works": works,
        "headline": headline,
        "user_stage": stage,
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


def epic_history_file(project_id: str) -> Path:
    d = config.CHAT_DIR / "_desktop" / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "epic_history.json"


def remember_last_epic(
    project_id: str,
    epic_id: str,
    title: str = "",
    *,
    thread_id: str | None = None,
) -> None:
    """记录项目最近 epic；若带 thread_id，则与对话深度绑定。"""
    updated = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    tid = (thread_id or "").strip() or None
    rec: dict[str, Any] = {
        "epic_id": epic_id,
        "title": title,
        "updated_at": updated,
    }
    if tid:
        rec["thread_id"] = tid
    path = project_last_epic_file(project_id)
    path.write_text(
        json.dumps(rec, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 追加历史（去重、新在前，最多 40）
    hist_path = epic_history_file(project_id)
    items: list[dict[str, Any]] = []
    if hist_path.is_file():
        try:
            raw = json.loads(hist_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                items = [x for x in raw if isinstance(x, dict)]
        except (json.JSONDecodeError, OSError):
            items = []
    items = [x for x in items if str(x.get("epic_id") or "") != epic_id]
    items.insert(0, rec)
    hist_path.write_text(
        json.dumps(items[:40], ensure_ascii=False, indent=2),
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


def list_recent_epics(
    project_id: str,
    *,
    thread_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """转任务 epic 列表。传 thread_id 时只返回该对话绑定的任务（右栏深度绑定）。"""
    hist_path = epic_history_file(project_id)
    items: list[dict[str, Any]] = []
    if hist_path.is_file():
        try:
            raw = json.loads(hist_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                items = [x for x in raw if isinstance(x, dict) and x.get("epic_id")]
        except (json.JSONDecodeError, OSError):
            items = []
    if not items:
        last = load_last_epic(project_id)
        if last and last.get("epic_id"):
            items = [last]
    # 事件日志兜底
    if len(items) < limit:
        seen = {str(x.get("epic_id")) for x in items}
        for rec in reversed(read_events(project_id=project_id, limit=500)):
            if rec.get("event") != "epic_created":
                continue
            data = rec.get("data") or {}
            eid = str(data.get("epic_id") or "")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            items.append(
                {
                    "epic_id": eid,
                    "title": str(data.get("title") or eid),
                    "updated_at": str(rec.get("ts") or ""),
                    "thread_id": data.get("thread_id"),
                }
            )
            if len(items) >= limit:
                break
    tid = (thread_id or "").strip()
    if tid:
        items = [
            x
            for x in items
            if str(x.get("thread_id") or "") == tid
        ]
    return items[:limit]
