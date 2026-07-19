import asyncio
import json
import os
import re
import time
from pathlib import Path

from .. import config


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00")


_SAFE_PROJECT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
# 允许 Desktop `{project}::main`；禁止路径分隔与 `..`
_SAFE_SESSION_RE = re.compile(r"^[a-zA-Z0-9_.:-]+$")


def _safe_project_id(project_id: str) -> str:
    pid = str(project_id or "").strip() or "ccc"
    if ".." in pid or "/" in pid or "\\" in pid or not _SAFE_PROJECT_RE.match(pid):
        raise ValueError(f"invalid project_id: {project_id!r}")
    return pid


def _safe_session_id(session_id: str) -> str:
    sid = str(session_id or "").strip()
    if (
        not sid
        or ".." in sid
        or "/" in sid
        or "\\" in sid
        or not _SAFE_SESSION_RE.match(sid)
    ):
        raise ValueError(f"invalid session_id: {session_id!r}")
    return sid


def _project_chat_dir(project_id: str) -> Path:
    d = config.CHAT_DIR / _safe_project_id(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str, project_id: str = "ccc") -> Path:
    """会话文件路径；校验后 resolve，确保仍在 CHAT_DIR 下。"""
    root = config.CHAT_DIR.resolve()
    path = (_project_chat_dir(project_id) / f"{_safe_session_id(session_id)}.json").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"session path escapes CHAT_DIR: {session_id!r}") from exc
    return path


def _index_path(project_id: str) -> Path:
    return _project_chat_dir(project_id) / "_index.json"


def _write_index(project_id: str, sessions: list[dict]) -> None:
    """Phase 2.2: 写轻量 index.json；文件锁 + 原子写，避免 to_thread TOCTOU。"""
    import fcntl
    import tempfile

    idx_path = _index_path(project_id)
    lock_path = idx_path.with_suffix(".json.lock")
    payload = json.dumps(
        {
            "updated_at": now_iso(),
            "count": len(sessions),
            "sessions": sessions,
        },
        ensure_ascii=False,
    )
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                fd, tmp_name = tempfile.mkstemp(
                    dir=str(idx_path.parent), prefix=".index-", suffix=".tmp"
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tf:
                        tf.write(payload)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(tmp_name, str(idx_path))
                except Exception:
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def _read_index(project_id: str) -> list[dict] | None:
    idx_path = _index_path(project_id)
    if not idx_path.exists():
        return None
    try:
        data = json.loads(idx_path.read_text(encoding="utf-8"))
        return data.get("sessions") or []
    except (json.JSONDecodeError, OSError):
        return None


def save_session(
    session_id: str,
    messages: list,
    reply: str = "",
    project: str = "ccc",
    mode: str = "chat",
    execution_results: list | None = None,
    total_cost_usd: float | None = None,
    status: str | None = None,
    claude_session_id: str | None = None,
):
    """Phase 2.2: 同步包装保留给非 async 调用方；内部走 asyncio.to_thread 避免阻塞事件循环。"""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已在事件循环中：调度到线程池，不阻塞
            asyncio.ensure_future(
                _save_session_async(
                    session_id, messages, reply, project, mode,
                    execution_results, total_cost_usd, status, claude_session_id,
                ),
                loop=loop,
            )
            return
    except RuntimeError:
        pass
    # 不在事件循环：直接同步写
    _save_session_sync(
        session_id, messages, reply, project, mode,
        execution_results, total_cost_usd, status, claude_session_id,
    )


async def _save_session_async(
    session_id, messages, reply, project, mode,
    execution_results, total_cost_usd, status, claude_session_id,
):
    await asyncio.to_thread(
        _save_session_sync,
        session_id, messages, reply, project, mode,
        execution_results, total_cost_usd, status, claude_session_id,
    )


def _save_session_sync(
    session_id, messages, reply, project, mode,
    execution_results, total_cost_usd, status, claude_session_id,
):
    path = _session_path(session_id, project)
    title_src = ""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            title_src = m["content"]
            break
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    # Keep user-renamed titles
    if existing.get("renamed") and existing.get("title"):
        title = str(existing["title"])[:80]
    else:
        title = title_src[:60] if title_src else "New Chat"

    data: dict = {
        "session_id": session_id,
        "title": title,
        "project": project,
        "messages": messages,
        "mode": mode,
        "updated_at": now_iso(),
    }
    if existing.get("renamed"):
        data["renamed"] = True
    if status:
        data["status"] = status
    if existing:
        data["created_at"] = existing.get("created_at", now_iso())
    else:
        data["created_at"] = now_iso()
    if reply:
        data["reply"] = reply
    if execution_results is not None:
        data["execution_results"] = execution_results
    if total_cost_usd is not None:
        data["total_cost_usd"] = total_cost_usd
    bound = (claude_session_id or "").strip() or str(
        existing.get("claude_session_id") or ""
    ).strip()
    if bound:
        data["claude_session_id"] = bound
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # Phase 2.2: 更新轻量 index（只存元数据，不存 messages）
    _update_index_entry(project, {
        "session_id": session_id,
        "title": title,
        "updated_at": data["updated_at"],
        "mode": mode,
        "source": data.get("source", "hub"),
    })


def _update_index_entry(project: str, entry: dict) -> None:
    """单条更新 index.json，避免重扫全目录"""
    sessions = _read_index(project) or []
    sessions = [s for s in sessions if s.get("session_id") != entry["session_id"]]
    sessions.insert(0, entry)
    sessions = sessions[:500]  # 上限 500 条
    _write_index(project, sessions)


def rename_session(
    session_id: str, project: str = "ccc", title: str = ""
) -> dict | None:
    """Rename a Hub session; sets renamed=True so save_session won't overwrite."""
    path = _session_path(session_id, project)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    new_title = (title or "").strip()[:80]
    if not new_title:
        return None
    data["title"] = new_title
    data["renamed"] = True
    data["updated_at"] = now_iso()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    _update_index_entry(project, {
        "session_id": session_id,
        "title": new_title,
        "updated_at": data["updated_at"],
        "mode": data.get("mode", "chat"),
        "source": data.get("source", "hub"),
    })
    return data

def list_sessions(project: str = "ccc", *, include_tests: bool = False) -> list[dict]:
    """Phase 2.2: 优先读 _index.json；缺失或失效时回退全扫并重建 index。"""
    from .claude_history import is_test_session_id

    chat_dir = _project_chat_dir(project)
    # 先试 index
    indexed = _read_index(project)
    # 校验 index 是否与目录一致（文件数对得上）
    if indexed is not None:
        try:
            file_count = len(list(chat_dir.glob("*.json")))
        except OSError:
            file_count = -1
        # 数量匹配（误差 ≤1：index 可能刚更新而文件未落盘，或反之）
        if file_count >= 0 and abs(len(indexed) - file_count) <= 1:
            if not include_tests:
                indexed = [s for s in indexed if not is_test_session_id(s.get("session_id", ""))]
            return indexed

    # 回退：全扫重建
    sessions = []
    for f in sorted(
        chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            if not include_tests and is_test_session_id(f.stem):
                continue
            data = json.loads(f.read_text())
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "title": str(data.get("title", "Unknown"))[:80],
                "updated_at": data.get("updated_at", ""),
                "mode": data.get("mode", "chat"),
                "source": data.get("source", "hub"),
            })
        except (json.JSONDecodeError, OSError):
            pass
    _write_index(project, sessions)
    return sessions


def purge_test_sessions(project: str = "ccc") -> dict:
    """Move pytest/e2e session files to .ccc/chat/_trash/<project>/."""
    from .claude_history import is_test_session_id

    _TRIVIAL_TITLES = frozenset({
        "hi", "ping", "hello", "test", "ok", "echo hello", "count to 3",
        "say hello in 3 words", "persist test", "delete test", "disk test",
        "fields test", "test session", "test ccc", "say hi 1 word",
        "say hi in 3 words", "say hi in 1 word", "say hello in one word",
        "say hello in one word only", "up to 3 words about the sky color",
        "read _config.py and tell me the port",
        "read _config.py line 12 and tell me the port number",
    })

    chat_dir = _project_chat_dir(project)
    trash = config.CHAT_DIR / "_trash" / project
    trash.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in list(chat_dir.glob("*.json")):
        move = is_test_session_id(f.stem)
        if not move:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                title = str(data.get("title") or "").strip().lower()
                if title in _TRIVIAL_TITLES or (
                    title.startswith("say hi") or title.startswith("say hello")
                ):
                    move = True
            except (json.JSONDecodeError, OSError):
                pass
        if not move:
            continue
        dest = trash / f.name
        if dest.exists():
            dest = trash / f"{f.stem}-{int(time.time())}.json"
        try:
            f.rename(dest)
            moved += 1
        except OSError:
            pass
    return {"moved": moved, "trash": str(trash)}


def get_session(session_id: str, project: str = "ccc") -> dict | None:
    path = _session_path(session_id, project)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def delete_session(session_id: str, project: str = "ccc") -> bool:
    path = _session_path(session_id, project)
    if path.exists():
        path.unlink()
        return True
    return False
