"""Inbox proposals — 外部顾问提案；默认不进 backlog，需 adopt → transfer。

契约：项目根 `inbox/`（一级目录）。见 inbox/README.md。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import config

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def inbox_dir() -> Path:
    d = config.PROJECT_ROOT / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    (d / "adopted").mkdir(parents=True, exist_ok=True)
    return d


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT_RE.match(text.strip() + ("\n" if not text.endswith("\n") else ""))
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta, (m.group(2) or "").strip()


def list_proposals(*, include_adopted: bool = False) -> list[dict[str, Any]]:
    root = inbox_dir()
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        items.append(_proposal_from_path(path, status_default="pending"))
    if include_adopted:
        for path in sorted((root / "adopted").glob("*.md")):
            items.append(_proposal_from_path(path, status_default="adopted"))
    return items


def get_proposal(prop_id: str) -> dict[str, Any] | None:
    prop_id = Path(prop_id).name
    if not prop_id.endswith(".md"):
        prop_id = f"{prop_id}.md"
    path = inbox_dir() / prop_id
    if path.is_file():
        return _proposal_from_path(path, status_default="pending")
    path = inbox_dir() / "adopted" / prop_id
    if path.is_file():
        return _proposal_from_path(path, status_default="adopted")
    return None


def _proposal_from_path(path: Path, *, status_default: str) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(raw)
    pid = meta.get("project") or meta.get("project_id") or ""
    return {
        "id": path.stem,
        "path": str(path.relative_to(config.PROJECT_ROOT)),
        "project_id": pid,
        "title": meta.get("title") or path.stem,
        "action": meta.get("action") or "transfer",
        "status": meta.get("status") or status_default,
        "pipeline": meta.get("pipeline") or "dev",
        "complexity": meta.get("complexity") or "small",
        "executor_intent": meta.get("executor_intent") or "python",
        "acceptance": [
            a.strip()
            for a in (meta.get("acceptance") or "").split("|")
            if a.strip()
        ],
        "body": body,
        "raw_meta": meta,
    }


def proposal_to_transfer_body(prop: dict[str, Any], *, client_request_id: str) -> dict[str, Any]:
    acc = prop.get("acceptance") or []
    if not acc:
        acc = ["提案已采纳并进 backlog"]
    goal = (prop.get("body") or "").strip().split("\n\n")[0][:500] or prop["title"]
    plan = prop.get("body") or f"# Plan\n\n## 目标\n{prop['title']}\n\n## 验收\n" + "\n".join(
        f"- {a}" for a in acc
    )
    return {
        "project_id": prop["project_id"],
        "thread_id": f"{prop['project_id']}::inbox-{prop['id']}",
        "client_request_id": client_request_id,
        "title": str(prop["title"])[:80],
        "goal": goal[:2000],
        "acceptance": acc,
        "pipeline": prop.get("pipeline") or "dev",
        "feasibility": "ok",
        "executor_intent": prop.get("executor_intent") or "python",
        "complexity": prop.get("complexity") or "small",
        "plan_md": plan,
    }


def mark_adopted(prop_id: str) -> Path | None:
    prop_id = Path(prop_id).name
    if not prop_id.endswith(".md"):
        prop_id = f"{prop_id}.md"
    src = inbox_dir() / prop_id
    if not src.is_file():
        return None
    dst = inbox_dir() / "adopted" / prop_id
    text = src.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(text)
    meta["status"] = "adopted"
    lines = ["---"] + [f"{k}: {v}" for k, v in meta.items()] + ["---", "", body, ""]
    dst.write_text("\n".join(lines), encoding="utf-8")
    src.unlink()
    return dst
