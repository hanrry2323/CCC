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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def list_sessions(project: str = "ccc") -> list[dict]:
    chat_dir = _project_chat_dir(project)
    sessions = []
    for f in sorted(
        chat_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "title": str(data.get("title", "Unknown"))[:80],
                "updated_at": data.get("updated_at", ""),
                "mode": data.get("mode", "chat"),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return sessions


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
