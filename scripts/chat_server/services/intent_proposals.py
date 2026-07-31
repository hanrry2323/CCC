"""Intent proposals — 方案文件落盘 / 串行队列 / 触发 splitter / 读结果。

契约：业务仓 `.ccc/intent-proposals/`（一级目录）。
- `<proposal_id>.md`            方案文件（4 节格式）
- `proposal_queue.jsonl`        串行队列（flock 写入）
- `<proposal_id>.result.jsonl`  拆卡审计日志（事件流）

参见 docs/product/ccc-new-architecture-overview.md 四层分工。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config

_log = logging.getLogger("ccc.chat_server.intent_proposals")

SPLITTER_SCRIPT = config.PROJECT_ROOT / "scripts" / "ccc-intent-splitter.py"
SPLITTER_TIMEOUT_S = 120
SPLITTER_LOCK = Path.home() / ".ccc" / "intent-splitter.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def proposal_dir(workspace_root: Path | str) -> Path:
    """业务仓 `.ccc/intent-proposals/`（幂等创建）。"""
    d = Path(workspace_root) / ".ccc" / "intent-proposals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_proposal_id(title: str, project_id: str) -> str:
    """`prop-<timestamp>-<8位hash>`，hash 基于 title+project_id+timestamp 防碰撞。"""
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    raw = f"{title}|{project_id}|{ts}|{os.urandom(4).hex()}"
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"prop-{ts}-{h}"


def save_proposal(
    workspace_root: Path | str,
    proposal_id: str,
    *,
    project_id: str,
    title: str,
    proposal_md: str,
    skill_ref: str,
    prompt_ref: str,
) -> Path:
    """落盘方案文件（带 frontmatter，供 splitter 读取）。"""
    d = proposal_dir(workspace_root)
    meta = [
        "---",
        f"proposal_id: {proposal_id}",
        f"project_id: {project_id}",
        f"title: {title[:80]}",
        f"skill_ref: {skill_ref}",
        f"prompt_ref: {prompt_ref}",
        f"created_at: {_now_iso()}",
        "status: queued",
        "---",
        "",
        proposal_md.strip(),
        "",
    ]
    path = d / f"{proposal_id}.md"
    path.write_text("\n".join(meta), encoding="utf-8")
    return path


def enqueue(workspace_root: Path | str, proposal_id: str, project_id: str) -> None:
    """入串行队列（flock 互斥写入 proposal_queue.jsonl）。"""
    d = proposal_dir(workspace_root)
    queue_path = d / "proposal_queue.jsonl"
    entry = {
        "proposal_id": proposal_id,
        "project_id": project_id,
        "ts": _now_iso(),
    }
    # flock 保证多 IDE 并发提交不冲突
    with open(queue_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append_result(
    workspace_root: Path | str,
    proposal_id: str,
    event: dict[str, Any],
) -> None:
    """追加事件到 <proposal_id>.result.jsonl（splitter / Hub 共用）。"""
    d = proposal_dir(workspace_root)
    path = d / f"{proposal_id}.result.jsonl"
    line = json.dumps({**event, "ts": event.get("ts") or _now_iso()}, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_result(workspace_root: Path | str, proposal_id: str) -> dict[str, Any]:
    """聚合 result.jsonl 最后一行事件，返回状态摘要。"""
    d = proposal_dir(workspace_root)
    path = d / f"{proposal_id}.result.jsonl"
    if not path.is_file():
        return {
            "status": "queued",
            "cards_produced": 0,
            "error": "",
            "started_at": "",
            "finished_at": "",
        }
    last: dict[str, Any] = {}
    started_at = ""
    finished_at = ""
    cards_produced = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        last = evt
        st = str(evt.get("status") or "").strip()
        if st == "running" and not started_at:
            started_at = str(evt.get("ts") or "")
        if st in ("ok", "failed"):
            finished_at = str(evt.get("ts") or "")
        if "cards_produced" in evt:
            cards_produced = int(evt.get("cards_produced") or 0)
    return {
        "status": last.get("status") or "queued",
        "cards_produced": cards_produced,
        "error": str(last.get("error") or ""),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def trigger_splitter(
    proposal_id: str,
    project_id: str,
    *,
    workspace_root: Path | str | None = None,
) -> subprocess.Popen | None:
    """异步触发 splitter 子进程（非阻塞）。

    单实例保护：flock(SPLITTER_LOCK) try-lock，拿不到则跳过（splitter 内部串行消费队列）。
    """
    if not SPLITTER_SCRIPT.is_file():
        _log.warning("splitter script not found: %s", SPLITTER_SCRIPT)
        return None
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(Path.home() / ".ccc" / "intent-splitter")}
    cmd = [
        "python3",
        str(SPLITTER_SCRIPT),
        "--proposal",
        proposal_id,
        "--project",
        project_id,
    ]
    if workspace_root:
        env["CCC_TARGET_WORKSPACE"] = str(Path(workspace_root).resolve())
    try:
        # 非阻塞 Popen；splitter 自己消费队列 + flock 单实例
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        _log.info(
            "triggered splitter pid=%s proposal=%s project=%s",
            proc.pid,
            proposal_id,
            project_id,
        )
        return proc
    except OSError as exc:
        _log.warning("trigger_splitter failed: %s", exc)
        return None
