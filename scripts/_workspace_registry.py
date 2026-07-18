"""_workspace_registry.py — Engine 可消费 workspace 登记（v0.50+）

产品规则：
- Engine 默认只扫 registry（防全盘 invent）
- 用户在 Hub/Board **显式下达**到某项目时，把该 path 写入 ~/.ccc/workspaces.json
- 支持 prune / unregister；拒绝 tmp/pytest 路径污染
- 绝不回退到 CCC_DISCOVER_ALL 全扫
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.workspace_registry")

REGISTRY_FILE = Path.home() / ".ccc" / "workspaces.json"

# 禁止写入 Engine 登记表的路径模式（pytest / 系统临时目录）
_TMP_NAME_RE = re.compile(
    r"(^|/)(TemporaryDirectory|_pytest|pytest-of-|pytest-\d+)(/|$)",
    re.I,
)


def registry_path() -> Path:
    return REGISTRY_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "1.0", "workspaces": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "1.0", "workspaces": []}
    if not isinstance(data, dict):
        return {"schema_version": "1.0", "workspaces": []}
    ws = data.get("workspaces")
    if not isinstance(ws, list):
        data["workspaces"] = []
    data.setdefault("schema_version", "1.0")
    return data


def _save(reg: Path, data: dict[str, Any]) -> None:
    reg.parent.mkdir(parents=True, exist_ok=True)
    tmp = reg.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(reg)


def _item_path(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        raw = item.get("path")
        return str(raw) if raw else None
    return None


def _item_name(item: Any) -> str | None:
    if isinstance(item, dict):
        n = item.get("name")
        return str(n) if n else None
    return None


def is_ephemeral_path(path: Path | str) -> bool:
    """True if path looks like tmp / pytest scratch (must not enter live registry)."""
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        p = Path(str(path))
    s = str(p)
    # Explicit pytest / TemporaryDirectory markers (do not ban all /var/folders/.../T/)
    if "pytest-of-" in s or _TMP_NAME_RE.search(s):
        return True
    if re.search(r"/pytest-\d+/", s):
        return True
    if s.startswith("/tmp/") or s.startswith("/private/tmp/"):
        return True
    # tempfile.mkdtemp style under .../T/tmpXXXX
    if re.search(r"/T/tmp[^/]+", s):
        return True
    return False


def list_registered_entries(registry: Path | None = None) -> list[dict[str, str]]:
    """Return [{name, path}, ...] (resolved paths, deduped)."""
    data = _load(registry or REGISTRY_FILE)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in data.get("workspaces") or []:
        raw = _item_path(item)
        if not raw:
            continue
        try:
            p = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        name = _item_name(item) or p.name
        out.append({"name": name, "path": key})
    return out


def list_registered_paths(registry: Path | None = None) -> list[Path]:
    return [Path(e["path"]) for e in list_registered_entries(registry)]


def _ephemeral_guard_relaxed() -> bool:
    return os.environ.get("CCC_ALLOW_EPHEMERAL_REGISTRY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def register_workspace(
    path: Path | str,
    *,
    name: str | None = None,
    registry: Path | None = None,
    allow_ephemeral: bool = False,
) -> dict[str, Any]:
    """幂等登记 workspace。返回 {ok, path, name, added, registry}。"""
    try:
        root = Path(path).expanduser().resolve()
    except OSError as exc:
        return {"ok": False, "error": str(exc), "added": False}

    if is_ephemeral_path(root) and not allow_ephemeral and not _ephemeral_guard_relaxed():
        return {
            "ok": False,
            "error": f"ephemeral/tmp path refused: {root}",
            "added": False,
        }
    if not root.is_dir():
        return {"ok": False, "error": f"not a directory: {root}", "added": False}
    board = root / ".ccc" / "board"
    if not board.is_dir():
        return {
            "ok": False,
            "error": f"missing .ccc/board under {root}",
            "added": False,
        }

    reg = registry or REGISTRY_FILE
    data = _load(reg)
    items: list[Any] = list(data.get("workspaces") or [])
    key = str(root)
    for item in items:
        existing = _item_path(item)
        if existing and str(Path(str(existing)).expanduser().resolve()) == key:
            return {
                "ok": True,
                "path": key,
                "name": name or _item_name(item) or root.name,
                "added": False,
                "registry": str(reg),
            }

    label = (name or root.name).strip() or root.name
    entry: dict[str, Any] = {
        "name": label,
        "path": key,
        "registered_at": _now_iso(),
    }
    items.append(entry)
    data["workspaces"] = items
    _save(reg, data)
    _log.info("registered workspace %s → %s", label, key)
    return {
        "ok": True,
        "path": key,
        "name": label,
        "added": True,
        "registry": str(reg),
    }


def unregister_workspace(
    path_or_name: Path | str,
    *,
    registry: Path | None = None,
) -> dict[str, Any]:
    """按 path 或 name 移除登记。返回 {ok, removed, path?, name?}。"""
    reg = registry or REGISTRY_FILE
    data = _load(reg)
    items: list[Any] = list(data.get("workspaces") or [])
    needle = str(path_or_name).strip()
    needle_path: str | None = None
    try:
        needle_path = str(Path(needle).expanduser().resolve())
    except OSError:
        needle_path = None

    kept: list[Any] = []
    removed: list[dict[str, str]] = []
    for item in items:
        raw = _item_path(item)
        name = _item_name(item) or ""
        try:
            resolved = str(Path(str(raw)).expanduser().resolve()) if raw else ""
        except OSError:
            resolved = str(raw or "")
        match = False
        if needle_path and resolved == needle_path:
            match = True
        elif name and name == needle:
            match = True
        elif raw and str(raw) == needle:
            match = True
        if match:
            removed.append({"name": name or Path(resolved).name, "path": resolved})
        else:
            kept.append(item)

    if not removed:
        return {"ok": False, "removed": 0, "error": f"not found: {needle}"}

    data["workspaces"] = kept
    _save(reg, data)
    _log.info("unregistered %s", removed)
    return {
        "ok": True,
        "removed": len(removed),
        "entries": removed,
        "registry": str(reg),
    }


def prune_missing(
    *,
    dry_run: bool = True,
    registry: Path | None = None,
) -> dict[str, Any]:
    """移除不存在、无 .ccc/board、或 ephemeral 的登记项。"""
    reg = registry or REGISTRY_FILE
    data = _load(reg)
    items: list[Any] = list(data.get("workspaces") or [])
    kept: list[Any] = []
    pruned: list[dict[str, str]] = []

    for item in items:
        raw = _item_path(item)
        name = _item_name(item) or ""
        if not raw:
            pruned.append({"name": name, "path": "", "reason": "empty_path"})
            continue
        try:
            p = Path(str(raw)).expanduser().resolve()
        except OSError:
            pruned.append({"name": name, "path": str(raw), "reason": "unresolvable"})
            continue
        key = str(p)
        reason: str | None = None
        # Missing / no board always prune. Ephemeral survivors (pytest leftovers)
        # prune even if the dir still exists — must not stay on Engine fleet.
        if not p.is_dir():
            reason = "missing"
        elif not (p / ".ccc" / "board").is_dir():
            reason = "no_board"
        elif is_ephemeral_path(p):
            reason = "ephemeral"
        if reason:
            pruned.append({"name": name or p.name, "path": key, "reason": reason})
        else:
            kept.append(item)

    if not dry_run and pruned:
        data["workspaces"] = kept
        _save(reg, data)
        _log.info("pruned %d workspace(s)", len(pruned))

    return {
        "ok": True,
        "dry_run": dry_run,
        "pruned": pruned,
        "kept": len(kept),
        "registry": str(reg),
    }
