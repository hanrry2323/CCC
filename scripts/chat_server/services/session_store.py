import json
import time
from pathlib import Path

from .. import config


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _project_chat_dir(project_id: str) -> Path:
    d = config.CHAT_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str, project_id: str = "ccc") -> Path:
    return _project_chat_dir(project_id) / f"{session_id}.json"


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
    path = _session_path(session_id, project)
    title_src = ""
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            title_src = m["content"]
            break
    data: dict = {
        "session_id": session_id,
        "title": (title_src[:60] if title_src else "New Chat"),
        "project": project,
        "messages": messages,
        "mode": mode,
        "updated_at": now_iso(),
    }
    if status:
        data["status"] = status
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            data["created_at"] = existing.get("created_at", now_iso())
        except (json.JSONDecodeError, OSError):
            data["created_at"] = now_iso()
    else:
        data["created_at"] = now_iso()
    if reply:
        data["reply"] = reply
    if execution_results is not None:
        data["execution_results"] = execution_results
    if total_cost_usd is not None:
        data["total_cost_usd"] = total_cost_usd
    # Persist Claude Code session binding for continuous / cold resume
    bound = (claude_session_id or "").strip() or str(
        existing.get("claude_session_id") or ""
    ).strip()
    if bound:
        data["claude_session_id"] = bound
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def list_sessions(project: str = "ccc", *, include_tests: bool = False) -> list[dict]:
    chat_dir = _project_chat_dir(project)
    sessions = []
    for f in sorted(
        chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            from .claude_history import is_test_session_id

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
