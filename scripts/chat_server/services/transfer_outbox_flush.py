"""M1 transfer outbox 后台冲刷：Desktop 关了也继续投 Hub。

用户确认转任务 → 写入
~/Library/Application Support/CCCDesktop/transfer-outbox.json
→ 本模块由 sidecar（launchd 常驻）周期冲刷 → Hub POST /api/desktop/transfer

契约：docs/product/loop-engineer-authority.md · Desktop 流畅原则
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.transfer_outbox")

MAX_ATTEMPTS = 8
DEFAULT_INTERVAL_S = 5.0


def outbox_path() -> Path:
    override = (os.environ.get("CCC_TRANSFER_OUTBOX") or "").strip()
    if override:
        return Path(override).expanduser()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "CCCDesktop"
        / "transfer-outbox.json"
    )


def hub_base() -> str:
    return (
        os.environ.get("CCC_HUB_URL")
        or os.environ.get("CCC_HUB_BASE")
        or "http://192.168.3.116:7777"
    ).rstrip("/")


def hub_auth_header() -> dict[str, str]:
    user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip()
    password = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip()
    import base64

    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def load_outbox(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or outbox_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def save_outbox(items: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or outbox_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def failed_path(outbox: Path | None = None) -> Path:
    p = outbox or outbox_path()
    return p.with_name("transfer-failed.json")


def load_failed(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or failed_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def save_failed(items: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or failed_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def enqueue_failed(item: dict[str, Any], *, outbox: Path | None = None) -> None:
    p = failed_path(outbox)
    q = load_failed(p)
    crid = str(item.get("client_request_id") or "")
    tid = str(item.get("thread_id") or "")
    replaced = False
    for i, row in enumerate(q):
        if not isinstance(row, dict):
            continue
        if crid and row.get("client_request_id") == crid:
            q[i] = item
            replaced = True
            break
        if tid and row.get("thread_id") == tid:
            q[i] = item
            replaced = True
            break
    if not replaced:
        q.append(item)
    save_failed(q, p)


def _post_transfer(item: dict[str, Any], timeout: float = 25.0) -> tuple[bool, str, dict[str, Any]]:
    """Return (ok, detail, response_json)."""
    body = {
        "project_id": item.get("project_id") or "",
        "thread_id": item.get("thread_id") or "",
        "title": item.get("title") or "",
        "goal": item.get("goal") or "",
        "acceptance": item.get("acceptance") or [],
        "pipeline": item.get("pipeline") or "dev",
        "feasibility": item.get("feasibility") or "ok",
        "feasibility_reason": item.get("feasibility_reason"),
        "executor_intent": item.get("executor_intent") or "opencode",
        "skills_hint": [],
        "plan_md": item.get("plan_md") or "",
        "complexity": item.get("complexity") or "medium",
        "client_request_id": item.get("client_request_id") or "",
    }
    url = f"{hub_base()}/api/desktop/transfer"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hub_auth_header(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
            ok = bool(payload.get("ok", True)) and bool(
                str(payload.get("epic_id") or "").strip()
            )
            if ok:
                return True, str(payload.get("epic_id")), payload
            return False, str(payload.get("error") or "empty epic"), payload
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")[:400]
        return False, f"http_{e.code}:{body_txt}", {}
    except Exception as e:
        return False, f"{type(e).__name__}:{e}", {}


def flush_once(*, path: Path | None = None) -> dict[str, Any]:
    """同步冲刷一圈。返回摘要。"""
    p = path or outbox_path()
    items = load_outbox(p)
    if not items:
        return {"ok": True, "pending": 0, "delivered": 0, "failed": 0, "path": str(p)}

    remaining: list[dict[str, Any]] = []
    delivered = 0
    failed = 0
    details: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        crid = str(item.get("client_request_id") or "")
        attempts = int(item.get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS:
            failed += 1
            enqueue_failed(item, outbox=p)
            details.append({"client_request_id": crid, "status": "exhausted"})
            continue
        ok, detail, payload = _post_transfer(item)
        if ok:
            delivered += 1
            details.append(
                {
                    "client_request_id": crid,
                    "status": "delivered",
                    "epic_id": detail,
                    "idempotent": bool(payload.get("idempotent_replay")),
                }
            )
            continue
        # transient keep; bump attempts
        item = dict(item)
        item["attempts"] = attempts + 1
        if item["attempts"] >= MAX_ATTEMPTS:
            failed += 1
            enqueue_failed(item, outbox=p)
            details.append(
                {"client_request_id": crid, "status": "exhausted", "error": detail}
            )
        else:
            remaining.append(item)
            details.append(
                {
                    "client_request_id": crid,
                    "status": "retry",
                    "attempts": item["attempts"],
                    "error": detail[:200],
                }
            )

    save_outbox(remaining, p)
    return {
        "ok": True,
        "pending": len(remaining),
        "delivered": delivered,
        "failed": failed,
        "path": str(p),
        "details": details,
    }


async def flush_loop(
    stop: asyncio.Event,
    *,
    interval_s: float | None = None,
) -> None:
    interval = float(
        interval_s
        if interval_s is not None
        else os.environ.get("CCC_OUTBOX_FLUSH_INTERVAL", DEFAULT_INTERVAL_S)
    )
    interval = max(2.0, min(interval, 60.0))
    _log.info(
        "transfer outbox flusher started interval=%.1fs path=%s hub=%s",
        interval,
        outbox_path(),
        hub_base(),
    )
    while not stop.is_set():
        try:
            summary = await asyncio.to_thread(flush_once)
            if summary.get("delivered") or summary.get("failed"):
                _log.info("outbox flush %s", summary)
        except Exception:
            _log.exception("outbox flush error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
    _log.info("transfer outbox flusher stopped")
