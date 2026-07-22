"""M1 transfer outbox 后台冲刷：Desktop 关了也继续投 Hub。

用户确认转任务 → 写入
~/Library/Application Support/CCCDesktop/transfer-outbox.json
→ 本模块由 sidecar（launchd 常驻）周期冲刷 → Hub POST /api/desktop/transfer
→ 成功写 transfer-receipts.json 供 Desktop 再开 hydrate

契约：docs/product/loop-engineer-authority.md · Desktop 流畅原则
唯一 Hub POST writer = sidecar（Desktop 只 enqueue + nudge）
"""

from __future__ import annotations

import asyncio
import base64
import fcntl
import json
import logging
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

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


def outbox_lock_path(outbox: Path | None = None) -> Path:
    p = outbox or outbox_path()
    return p.with_name("transfer-outbox.lock")


def receipts_path(outbox: Path | None = None) -> Path:
    p = outbox or outbox_path()
    return p.with_name("transfer-receipts.json")


def hub_base() -> str:
    return (
        os.environ.get("CCC_HUB_URL")
        or os.environ.get("CCC_HUB_BASE")
        or "http://192.168.3.116:7777"
    ).rstrip("/")


def hub_auth_header() -> dict[str, str]:
    """与 lens/sidecar 对齐：优先 CCC_HUB_AUTH，再 CCC_CHAT_USER/PASS，默认 ccc:ccc。"""
    explicit = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if explicit:
        auth = explicit
    else:
        user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip() or "ccc"
        password = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip() or "ccc"
        auth = f"{user}:{password}"
    token = base64.b64encode(auth.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


@contextmanager
def outbox_file_lock(path: Path | None = None) -> Iterator[None]:
    """advisory flock；与 Desktop Swift transfer-outbox.lock 互通。"""
    lock_p = outbox_lock_path(path)
    lock_p.parent.mkdir(parents=True, exist_ok=True)
    lock_p.touch(exist_ok=True)
    with open(lock_p, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


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


def load_receipts(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or receipts_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else []


def save_receipts(items: list[dict[str, Any]], path: Path | None = None) -> None:
    p = path or receipts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items[:200], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def write_receipt(
    *,
    client_request_id: str,
    epic_id: str,
    project_id: str,
    thread_id: str,
    outbox: Path | None = None,
) -> None:
    """投递成功收据；Desktop reopen hydrate 优先读此文件。"""
    crid = (client_request_id or "").strip()
    eid = (epic_id or "").strip()
    if not crid or not eid:
        return
    p = receipts_path(outbox)
    q = load_receipts(p)
    rec = {
        "client_request_id": crid,
        "epic_id": eid,
        "project_id": (project_id or "").strip(),
        "thread_id": (thread_id or "").strip(),
        "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }
    replaced = False
    for i, row in enumerate(q):
        if isinstance(row, dict) and row.get("client_request_id") == crid:
            q[i] = rec
            replaced = True
            break
    if not replaced:
        q.insert(0, rec)
    save_receipts(q, p)


def _claim_batch(path: Path) -> tuple[list[dict[str, Any]], int]:
    """锁内取出待投递副本；已耗尽条移入 failed。

    Returns (claimed_copies, exhausted_count). claimed 仍留在 outbox，
    投递结束后由 _merge_after_flush 删除/更新，避免冲刷窗口丢掉 Desktop 新入队。
    """
    with outbox_file_lock(path):
        items = load_outbox(path)
        if not items:
            return [], 0
        claimed: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []
        exhausted_n = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            attempts = int(item.get("attempts") or 0)
            if attempts >= MAX_ATTEMPTS:
                enqueue_failed(item, outbox=path)
                exhausted_n += 1
                continue
            claimed.append(dict(item))
            remaining.append(item)
        save_outbox(remaining, path)
        return claimed, exhausted_n


def _merge_after_flush(
    path: Path,
    *,
    delivered_crids: set[str],
    bumped: dict[str, dict[str, Any]],
    exhausted: list[dict[str, Any]],
) -> int:
    """锁内合并：删已投递；更新重试 attempts；写 failed；保留 Desktop 新入队项。"""
    with outbox_file_lock(path):
        current = load_outbox(path)
        by_crid: dict[str, dict[str, Any]] = {}
        orphan: list[dict[str, Any]] = []
        for x in current:
            if not isinstance(x, dict):
                continue
            crid = str(x.get("client_request_id") or "").strip()
            if crid:
                by_crid[crid] = x
            else:
                orphan.append(x)
        for crid, item in bumped.items():
            if crid in delivered_crids:
                continue
            by_crid[crid] = item
        for crid in delivered_crids:
            by_crid.pop(crid, None)
        for item in exhausted:
            enqueue_failed(item, outbox=path)
            crid = str(item.get("client_request_id") or "").strip()
            if crid:
                by_crid.pop(crid, None)
        remaining = list(by_crid.values()) + orphan
        save_outbox(remaining, path)
        return len(remaining)


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
        "bump_version": bool(item.get("bump_version")),
        "human_note": item.get("human_note") or "",
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
    claimed, pre_exhausted = _claim_batch(p)
    if not claimed:
        with outbox_file_lock(p):
            pending = len(load_outbox(p))
        return {
            "ok": True,
            "pending": pending,
            "delivered": 0,
            "failed": pre_exhausted,
            "path": str(p),
        }

    delivered = 0
    failed = pre_exhausted
    details: list[dict[str, Any]] = []
    delivered_crids: set[str] = set()
    bumped: dict[str, dict[str, Any]] = {}
    exhausted: list[dict[str, Any]] = []

    for item in claimed:
        crid = str(item.get("client_request_id") or "")
        attempts = int(item.get("attempts") or 0)
        ok, detail, payload = _post_transfer(item)
        if ok:
            delivered += 1
            if crid:
                delivered_crids.add(crid)
            write_receipt(
                client_request_id=crid,
                epic_id=detail,
                project_id=str(item.get("project_id") or ""),
                thread_id=str(item.get("thread_id") or ""),
                outbox=p,
            )
            details.append(
                {
                    "client_request_id": crid,
                    "status": "delivered",
                    "epic_id": detail,
                    "idempotent": bool(payload.get("idempotent_replay")),
                }
            )
            continue
        item = dict(item)
        item["attempts"] = attempts + 1
        if item["attempts"] >= MAX_ATTEMPTS:
            failed += 1
            exhausted.append(item)
            details.append(
                {"client_request_id": crid, "status": "exhausted", "error": detail}
            )
        else:
            if crid:
                bumped[crid] = item
            details.append(
                {
                    "client_request_id": crid,
                    "status": "retry",
                    "attempts": item["attempts"],
                    "error": detail[:200],
                }
            )

    pending = _merge_after_flush(
        p,
        delivered_crids=delivered_crids,
        bumped=bumped,
        exhausted=exhausted,
    )
    return {
        "ok": True,
        "pending": pending,
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
