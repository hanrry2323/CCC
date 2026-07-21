"""Hub 只读透镜：在 2017 权威仓上读 board / tree / file / grep / git。

契约：docs/product/loop-engineer-authority.md
供 /api/desktop/lens/* 与 scripts/ccc-hub-lens.py 复用。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
}
EXCLUDE_FILE_NAMES = {".DS_Store"}
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".pyc",
    ".so",
    ".dylib",
    ".rdb",
}
MAX_FILE_BYTES = 100 * 1024
MAX_TREE_ENTRIES = 400
MAX_GREP_HITS = 40
MAX_GREP_LINE = 240
BOARD_COLS = (
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
)
INFLIGHT_COLS = ("planned", "in_progress", "testing", "verified")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_under(root: Path, rel: str) -> Path:
    rel = (rel or "").strip().lstrip("/")
    if ".." in Path(rel).parts:
        raise ValueError("path traversal not allowed")
    target = (root / rel).resolve() if rel else root.resolve()
    target.relative_to(root.resolve())
    return target


def _task_title(path: Path) -> str:
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        data = json.loads(line)
        return str(data.get("title") or path.stem)[:80]
    except Exception:
        return path.stem


def collect_board(root: Path, *, project_id: str) -> dict[str, Any]:
    board = root / ".ccc" / "board"
    counts: dict[str, int] = {}
    inflight: list[dict[str, str]] = []
    present = board.is_dir()
    if present:
        for col in BOARD_COLS:
            col_dir = board / col
            files = sorted(col_dir.glob("*.jsonl")) if col_dir.is_dir() else []
            counts[col] = len(files)
            if col in INFLIGHT_COLS:
                for f in files[:20]:
                    inflight.append(
                        {
                            "column": col,
                            "id": f.stem,
                            "title": _task_title(f),
                        }
                    )
    else:
        counts = {c: 0 for c in BOARD_COLS}
    return {
        "ok": True,
        "project_id": project_id,
        "workspace": str(root),
        "as_of": _now_iso(),
        "board_present": present,
        "counts": counts,
        "inflight": inflight,
        "inflight_total": len(inflight),
        "summary": (
            f"as_of={_now_iso()} backlog={counts.get('backlog', 0)} "
            f"planned={counts.get('planned', 0)} in_progress={counts.get('in_progress', 0)} "
            f"testing={counts.get('testing', 0)} verified={counts.get('verified', 0)} "
            f"released={counts.get('released', 0)} abnormal={counts.get('abnormal', 0)} "
            f"inflight={len(inflight)}"
        ),
    }


def collect_tree(
    root: Path,
    *,
    project_id: str,
    path: str = "",
    depth: int = 3,
) -> dict[str, Any]:
    depth = max(0, min(int(depth or 3), 5))
    base = _safe_under(root, path) if path else root.resolve()
    if not base.exists():
        return {"ok": False, "error": "path not found", "project_id": project_id}
    entries: list[dict[str, Any]] = []
    truncated = False
    root_res = root.resolve()
    base_prefix = path.strip().strip("/")

    def _rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(root_res)).replace(os.sep, "/")
        except Exception:
            return p.name

    def _skip_name(name: str) -> bool:
        if name in EXCLUDE_FILE_NAMES:
            return True
        if name == ".ccc":
            return False
        if name.startswith("."):
            return True
        return name in EXCLUDE_DIRS

    def walk(cur: Path, d: int) -> None:
        nonlocal truncated
        if truncated or d > depth:
            return
        try:
            children = sorted(cur.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            if len(entries) >= MAX_TREE_ENTRIES:
                truncated = True
                return
            name = child.name
            if _skip_name(name):
                continue
            rel = _rel(child)
            if child.is_dir():
                entries.append({"name": name, "type": "dir", "path": rel, "depth": d})
                walk(child, d + 1)
            else:
                try:
                    size = child.stat().st_size
                except OSError:
                    size = 0
                entries.append(
                    {
                        "name": name,
                        "type": "file",
                        "path": rel,
                        "depth": d,
                        "size": size,
                    }
                )

    if base.is_file():
        entries.append(
            {
                "name": base.name,
                "type": "file",
                "path": base_prefix or base.name,
                "depth": 0,
                "size": base.stat().st_size,
            }
        )
    else:
        walk(base, 0)

    return {
        "ok": True,
        "project_id": project_id,
        "path": path or ".",
        "as_of": _now_iso(),
        "entries": entries,
        "truncated": truncated,
        "count": len(entries),
    }


def collect_file(root: Path, *, project_id: str, path: str) -> dict[str, Any]:
    if not path:
        raise ValueError("path required")
    target = _safe_under(root, path)
    if any(p in EXCLUDE_DIRS for p in Path(path).parts if p != ".ccc"):
        # allow .ccc/profile etc.
        parts = Path(path).parts
        if parts and parts[0] in EXCLUDE_DIRS - {".ccc"}:
            raise ValueError(f"access denied: {path}")
    if not target.is_file():
        raise FileNotFoundError(path)
    if target.suffix.lower() in BINARY_EXTS:
        raise ValueError("binary file not readable")
    size = target.stat().st_size
    truncated = size > MAX_FILE_BYTES
    raw = target.read_bytes()[:MAX_FILE_BYTES]
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")
    return {
        "ok": True,
        "project_id": project_id,
        "path": path,
        "as_of": _now_iso(),
        "size": size,
        "truncated": truncated,
        "content": content,
    }


def collect_grep(
    root: Path,
    *,
    project_id: str,
    q: str,
    glob: str = "",
    max_hits: int = MAX_GREP_HITS,
) -> dict[str, Any]:
    q = (q or "").strip()
    if not q:
        raise ValueError("q required")
    max_hits = max(1, min(int(max_hits or MAX_GREP_HITS), 80))
    cmd = ["rg", "-n", "--no-heading", "-m", str(max_hits), "-S", q]
    if glob:
        cmd.extend(["-g", glob])
    for d in EXCLUDE_DIRS:
        cmd.extend(["-g", f"!{d}/**"])
    cmd.append(str(root))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except FileNotFoundError:
        return _grep_python(root, project_id=project_id, q=q, max_hits=max_hits)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "project_id": project_id,
            "error": "grep timeout",
            "as_of": _now_iso(),
            "hits": [],
        }
    hits: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        if len(hits) >= max_hits:
            break
        # path:line:text
        m = re.match(r"^(.+?):(\d+):(.*)$", line)
        if not m:
            continue
        fpath, lno, text = m.group(1), m.group(2), m.group(3)
        try:
            rel = str(Path(fpath).resolve().relative_to(root.resolve()))
        except Exception:
            rel = fpath
        hits.append(
            {
                "path": rel.replace(os.sep, "/"),
                "line": int(lno),
                "text": text[:MAX_GREP_LINE],
            }
        )
    return {
        "ok": True,
        "project_id": project_id,
        "q": q,
        "as_of": _now_iso(),
        "hits": hits,
        "count": len(hits),
        "truncated": len(hits) >= max_hits,
    }


def _grep_python(
    root: Path,
    *,
    project_id: str,
    q: str,
    max_hits: int,
) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    pattern = re.compile(re.escape(q), re.I)
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fname in files:
            if len(hits) >= max_hits:
                break
            if fname in EXCLUDE_FILE_NAMES:
                continue
            fp = Path(cur) / fname
            if fp.suffix.lower() in BINARY_EXTS:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    rel = str(fp.relative_to(root)).replace(os.sep, "/")
                    hits.append({"path": rel, "line": i, "text": line[:MAX_GREP_LINE]})
                    if len(hits) >= max_hits:
                        break
        if len(hits) >= max_hits:
            break
    return {
        "ok": True,
        "project_id": project_id,
        "q": q,
        "as_of": _now_iso(),
        "hits": hits,
        "count": len(hits),
        "truncated": len(hits) >= max_hits,
        "via": "python",
    }


def collect_git_summary(root: Path, *, project_id: str) -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            p = subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return (p.stdout or "").strip()
        except Exception:
            return ""

    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    status = _run(["status", "--porcelain"])
    dirty_lines = [ln for ln in status.splitlines() if ln.strip()]
    log = _run(["log", "-5", "--oneline"])
    return {
        "ok": True,
        "project_id": project_id,
        "workspace": str(root),
        "as_of": _now_iso(),
        "branch": branch,
        "dirty": bool(dirty_lines),
        "dirty_count": len(dirty_lines),
        "dirty_sample": dirty_lines[:15],
        "recent_commits": [ln for ln in log.splitlines() if ln.strip()][:5],
    }


def format_board_for_prompt(board: dict[str, Any]) -> str:
    """短文本块，注入对齐基线 / 讨论轮次。"""
    lines = [
        f"【Hub live board · {board.get('as_of', '')}】",
        board.get("summary") or "",
    ]
    inflight = board.get("inflight") or []
    if inflight:
        lines.append("在飞：")
        for item in inflight[:15]:
            lines.append(
                f"- [{item.get('column')}] {item.get('id')}: {item.get('title')}"
            )
    else:
        lines.append("在飞：无（planned/in_progress/testing/verified 为空）")
    lines.append("（此块为权威仓 live；勿用更早 baseline 覆盖。）")
    return "\n".join(lines)
