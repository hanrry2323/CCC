"""Claude Code local history — list/load transcripts under CLAUDE_CONFIG_DIR/projects
（优先）或 ~/.claude/projects（兼容回落）。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

def _claude_homes() -> list[Path]:
    """优先私有配置家，再回落个人 ~/.claude。"""
    homes: list[Path] = []
    cfg = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    if cfg:
        homes.append(Path(cfg).expanduser())
    # M1 Desktop 默认私有家（即使未 export）
    loop_home = Path.home() / ".ccc" / "loop-code"
    if loop_home not in homes:
        homes.append(loop_home)
    personal = Path.home() / ".claude"
    if personal not in homes:
        homes.append(personal)
    return homes


def _primary_claude_home() -> Path:
    for h in _claude_homes():
        if (h / "projects").is_dir() or h.is_dir():
            # 优先已有 projects 的；否则第一个存在的 config 根
            if (h / "projects").is_dir():
                return h
    for h in _claude_homes():
        if h.is_dir():
            return h
    return Path.home() / ".claude"


CLAUDE_HOME = _primary_claude_home()
HISTORY_INDEX = CLAUDE_HOME / "history.jsonl"
PROJECTS_DIR = CLAUDE_HOME / "projects"
TZ_CN = timezone(timedelta(hours=8))

# Hub / pytest 污染：不进侧栏
_HUB_NOISE = re.compile(r"^##\s*项目上下文|^##\s*Project\b", re.M)
_TEST_ID = re.compile(
    r"^(ch|sc|sp|ex|ss)\d|"
    r"^(cross|test|smoke)[-_]|"
    r"^sp\d+-",
    re.I,
)


def escape_project_path(project_path: str) -> str:
    """ /Users/apple/program/CCC → -Users-apple-program-CCC """
    p = str(Path(project_path).resolve())
    return p.replace("/", "-")


def claude_project_dir(project_path: str) -> Path:
    escaped = escape_project_path(project_path)
    for home in _claude_homes():
        cand = home / "projects" / escaped
        if cand.is_dir():
            return cand
    return _primary_claude_home() / "projects" / escaped


def _history_indexes() -> list[Path]:
    out: list[Path] = []
    for home in _claude_homes():
        p = home / "history.jsonl"
        if p.is_file() and p not in out:
            out.append(p)
    return out


def is_test_session_id(session_id: str) -> bool:
    sid = (session_id or "").strip()
    if sid.startswith("claude:"):
        return False
    return bool(_TEST_ID.match(sid))


def _ms_to_iso(ms: int | float | str | None) -> str:
    try:
        val = int(float(ms))
        # history.jsonl uses ms timestamps
        if val > 10_000_000_000:
            val = val / 1000.0
        dt = datetime.fromtimestamp(val, tz=TZ_CN)
        return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(str(block.get("text") or ""))
            elif btype == "tool_use":
                parts.append(f"[工具: {block.get('name') or 'tool'}]")
            elif btype == "tool_result":
                c = block.get("content")
                if isinstance(c, str) and c.strip():
                    parts.append(c[:500])
        return "\n".join(p for p in parts if p)
    return str(content)


def _looks_like_hub_noise(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _HUB_NOISE.search(t):
        return True
    # print-mode one-shots often tiny
    if t.lower() in {"hi", "ping", "test", "hello", "ok"}:
        return True
    return False


def list_claude_sessions(project_path: str, limit: int = 120) -> list[dict]:
    """Index Claude sessions for a project via history.jsonl (fast)."""
    project_path = str(Path(project_path).resolve())
    proj_dir = claude_project_dir(project_path)
    indexes = _history_indexes()
    if not indexes:
        return []

    by_id: dict[str, dict] = {}
    try:
        for hist in indexes:
            with hist.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(row.get("project") or "") != project_path:
                        continue
                    sid = str(row.get("sessionId") or "").strip()
                    if not sid:
                        continue
                    display = str(row.get("display") or "").strip()
                    ts = row.get("timestamp")
                    entry = by_id.get(sid)
                    if entry is None:
                        by_id[sid] = {
                            "session_id": f"claude:{sid}",
                            "claude_session_id": sid,
                            "title": (display[:60] if display else "Claude 对话"),
                            "updated_at": _ms_to_iso(ts),
                            "mode": "claude",
                            "source": "claude",
                            "_ts": float(ts or 0),
                            "_noise": _looks_like_hub_noise(display),
                        }
                    else:
                        try:
                            tsf = float(ts or 0)
                        except (TypeError, ValueError):
                            tsf = 0
                        if tsf >= entry.get("_ts", 0):
                            entry["_ts"] = tsf
                            entry["updated_at"] = _ms_to_iso(ts)
                            if display and not _looks_like_hub_noise(display):
                                entry["title"] = display[:60]
                                entry["_noise"] = False
    except OSError:
        return []

    sessions = []
    for sid, entry in by_id.items():
        if entry.get("_noise"):
            continue
        jsonl = proj_dir / f"{sid}.jsonl"
        if not jsonl.exists():
            # 跨 config 家再找一遍 transcript
            for home in _claude_homes():
                alt = home / "projects" / escape_project_path(project_path) / f"{sid}.jsonl"
                if alt.is_file():
                    jsonl = alt
                    break
            else:
                continue
        # Prefer ai-title from transcript tail if cheap
        title = _peek_ai_title(jsonl) or entry["title"]
        sessions.append({
            "session_id": entry["session_id"],
            "claude_session_id": sid,
            "title": title[:80],
            "updated_at": entry["updated_at"],
            "mode": "claude",
            "source": "claude",
        })

    sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
    return sessions[:limit]


def _peek_ai_title(jsonl: Path) -> str:
    try:
        # Read last ~64KB for recent ai-title
        size = jsonl.stat().st_size
        with jsonl.open("rb") as fh:
            if size > 65536:
                fh.seek(size - 65536)
                fh.readline()  # discard partial
            tail = fh.read().decode("utf-8", errors="replace")
        title = ""
        for line in tail.splitlines():
            if '"ai-title"' not in line and '"aiTitle"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "ai-title" and ev.get("aiTitle"):
                title = str(ev["aiTitle"]).strip()
        return title[:80]
    except OSError:
        return ""


def load_claude_session(session_id: str, project_path: str) -> dict | None:
    """Load a Claude transcript into Hub session shape."""
    sid = session_id
    if sid.startswith("claude:"):
        sid = sid[7:]
    proj_dir = claude_project_dir(project_path)
    path = proj_dir / f"{sid}.jsonl"
    if not path.exists():
        return None

    messages: list[dict] = []
    title = ""
    ai_title = ""
    updated_at = ""
    try:
        mtime = path.stat().st_mtime
        updated_at = datetime.fromtimestamp(mtime, tz=TZ_CN).strftime(
            "%Y-%m-%dT%H:%M:%S+08:00"
        )
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = ev.get("type")
                if et == "ai-title" and ev.get("aiTitle"):
                    ai_title = str(ev["aiTitle"]).strip()
                    continue
                if et not in ("user", "assistant"):
                    continue
                msg = ev.get("message") or {}
                role = msg.get("role") or et
                if role not in ("user", "assistant"):
                    continue
                text = _content_to_text(msg.get("content"))
                if not text.strip():
                    continue
                # Skip tool-only user turns that are empty after extraction
                if role == "user" and text.startswith("[工具:"):
                    continue
                messages.append({"role": role, "content": text, "mode": "claude"})
                if role == "user" and not title and not _looks_like_hub_noise(text):
                    title = text.strip().split("\n", 1)[0][:60]
                ts = ev.get("timestamp")
                if ts:
                    # ISO or ms
                    if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
                        updated_at = _ms_to_iso(ts) or updated_at
                    elif isinstance(ts, str) and "T" in ts:
                        updated_at = ts[:19] + "+08:00" if "+" not in ts else ts
    except OSError:
        return None

    if not messages:
        return None

    return {
        "session_id": f"claude:{sid}",
        "claude_session_id": sid,
        "title": (ai_title or title or "Claude 对话")[:80],
        "project": "",
        "messages": messages,
        "mode": "claude",
        "source": "claude",
        "updated_at": updated_at,
        "created_at": updated_at,
        "status": "imported",
    }


def parse_claude_session_id(session_id: str) -> str | None:
    """Return raw Claude UUID if this is a Claude-backed Hub session id."""
    if not session_id:
        return None
    if session_id.startswith("claude:"):
        return session_id[7:]
    return None
