"""M1 repair-queue：编排异常自动 SOP 入队；Desktop/sidecar 冲刷注入 Agent。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def queue_path() -> Path:
    raw = os.environ.get("CCC_REPAIR_QUEUE", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / ".ccc" / "repair-queue.jsonl"


def enqueue(
    *,
    project_id: str,
    epic_id: str,
    hint: str,
    thread_id: str = "",
    prompt: str = "",
) -> dict[str, Any]:
    """同一 project|epic 去重：已有 pending 则跳过。"""
    pid = (project_id or "").strip()
    eid = (epic_id or "").strip()
    key = f"{pid}|{eid}"
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_pending()
    if any(f"{x.get('project_id')}|{x.get('epic_id')}" == key for x in existing):
        return {"ok": True, "deduped": True, "key": key}
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "status": "pending",
        "project_id": pid,
        "epic_id": eid,
        "thread_id": (thread_id or "").strip(),
        "hint": (hint or "")[:400],
        "prompt": (prompt or "")[:4000],
        "key": key,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "deduped": False, "key": key}


def load_pending() -> list[dict[str, Any]]:
    path = queue_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and (row.get("status") or "pending") == "pending":
                out.append(row)
    except OSError:
        return []
    return out


def mark_done(key: str) -> None:
    path = queue_path()
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    new_lines: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except json.JSONDecodeError:
            new_lines.append(ln)
            continue
        if isinstance(row, dict) and row.get("key") == key:
            row["status"] = "done"
            row["done_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            new_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            new_lines.append(ln)
    try:
        path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    except OSError:
        pass


def sop_prompt(*, project_id: str, epic_id: str, hint: str) -> str:
    return (
        "【编排自愈 · 自动 SOP · 勿问老板】\n"
        f"项目：{project_id}\n"
        f"大卡：{epic_id}\n"
        f"摘要：{hint}\n"
        "请严格按 references/board-auto-repair-sop.md：\n"
        "hub_repair(status) → 可恢复先 reopen → clear_blockers（只归档不可恢复）→ 回报板面数字。\n"
        "禁止先藏还可重试的 abnormal；禁止甩锅让老板复制/去运维页；禁止 invent；禁止写业务源码。\n"
    )
