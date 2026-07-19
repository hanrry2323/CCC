"""_workspace_registry.py — Engine 可消费 workspace 登记（v0.51+ orch 分离）

产品规则：
- Engine 默认只扫 registry 中 engine-eligible 条目（防全盘 invent / 防 CCC 自消费）
- CCC 本体 role=orch、engine=false：Hub 可见运维，Engine 不消费看板
- 用户在 Hub/Board **显式下达**到业务项目时，把该 path 写入 ~/.ccc/workspaces.json
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

ROLE_ORCH = "orch"
ROLE_APP = "app"
SCHEMA_VERSION = "1.1"


def registry_path() -> Path:
    return REGISTRY_FILE


def orch_home() -> Path:
    """CCC orchestration repo (this package's parent)."""
    return Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "workspaces": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "workspaces": []}
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "workspaces": []}
    ws = data.get("workspaces")
    if not isinstance(ws, list):
        data["workspaces"] = []
    data.setdefault("schema_version", SCHEMA_VERSION)
    return data


def _save(reg: Path, data: dict[str, Any]) -> None:
    reg.parent.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = data.get("schema_version") or SCHEMA_VERSION
    tmp = reg.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as tf:
        tf.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        tf.flush()
        os.fsync(tf.fileno())
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


def _normalize_role(raw: Any, *, path: Path, name: str) -> str:
    s = str(raw or "").strip().lower()
    if s in (ROLE_ORCH, ROLE_APP):
        return s
    # Infer orch: CCC home or name CCC
    try:
        if path.resolve() == orch_home().resolve():
            return ROLE_ORCH
    except OSError:
        pass
    if name.strip().upper() == "CCC":
        return ROLE_ORCH
    return ROLE_APP


def _normalize_engine(raw: Any, *, role: str) -> bool:
    if role == ROLE_ORCH:
        return False
    if raw is False or str(raw).strip().lower() in ("0", "false", "no", "off"):
        return False
    return True


def is_ephemeral_path(path: Path | str) -> bool:
    """True if path looks like tmp / pytest scratch (must not enter live registry)."""
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        p = Path(str(path))
    s = str(p)
    if "pytest-of-" in s or _TMP_NAME_RE.search(s):
        return True
    if re.search(r"/pytest-\d+/", s):
        return True
    if s.startswith("/tmp/") or s.startswith("/private/tmp/"):
        return True
    if re.search(r"/T/tmp[^/]+", s):
        return True
    return False


def entry_engine_eligible(entry: dict[str, Any]) -> bool:
    """Whether Engine should consume this workspace's board."""
    role = str(entry.get("role") or ROLE_APP).lower()
    if role == ROLE_ORCH:
        return False
    eng = entry.get("engine")
    if eng is False:
        return False
    if isinstance(eng, str) and eng.strip().lower() in ("0", "false", "no", "off"):
        return False
    return True


def is_orch_path(path: Path | str) -> bool:
    try:
        p = Path(path).expanduser().resolve()
        return p == orch_home().resolve()
    except OSError:
        return False


def list_registered_entries(registry: Path | None = None) -> list[dict[str, Any]]:
    """Return [{name, path, role, engine, ...}, ...] (resolved paths, deduped)."""
    data = _load(registry or REGISTRY_FILE)
    out: list[dict[str, Any]] = []
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
        if isinstance(item, dict):
            role = _normalize_role(item.get("role"), path=p, name=name)
            engine = _normalize_engine(item.get("engine"), role=role)
            entry: dict[str, Any] = {
                "name": name,
                "path": key,
                "role": role,
                "engine": engine,
            }
            if item.get("registered_at"):
                entry["registered_at"] = item["registered_at"]
        else:
            role = _normalize_role(None, path=p, name=name)
            entry = {
                "name": name,
                "path": key,
                "role": role,
                "engine": _normalize_engine(None, role=role),
            }
        out.append(entry)
    return out


def list_registered_paths(registry: Path | None = None) -> list[Path]:
    return [Path(e["path"]) for e in list_registered_entries(registry)]


def list_engine_paths(registry: Path | None = None) -> list[Path]:
    """Paths Engine should tick (excludes orch / engine:false)."""
    return [
        Path(e["path"])
        for e in list_registered_entries(registry)
        if entry_engine_eligible(e)
    ]


def lookup_entry(
    path_or_name: Path | str,
    *,
    registry: Path | None = None,
) -> dict[str, Any] | None:
    needle = str(path_or_name).strip()
    needle_path: str | None = None
    try:
        needle_path = str(Path(needle).expanduser().resolve())
    except OSError:
        needle_path = None
    for e in list_registered_entries(registry):
        if needle_path and e["path"] == needle_path:
            return e
        if e.get("name") == needle:
            return e
        if e["path"] == needle:
            return e
    # Unregistered but path is orch home
    if needle_path and is_orch_path(needle_path):
        return {
            "name": "CCC",
            "path": needle_path,
            "role": ROLE_ORCH,
            "engine": False,
        }
    if needle.upper() == "CCC":
        home = orch_home()
        return {
            "name": "CCC",
            "path": str(home),
            "role": ROLE_ORCH,
            "engine": False,
        }
    return None


def migrate_registry_roles(
    *,
    registry: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Ensure CCC entry is orch/engine:false; bump schema; fill defaults on apps."""
    reg = registry or REGISTRY_FILE
    data = _load(reg)
    items: list[Any] = list(data.get("workspaces") or [])
    changed = 0
    new_items: list[Any] = []
    orch = orch_home()
    found_orch = False

    for item in items:
        if isinstance(item, str):
            try:
                p = Path(item).expanduser().resolve()
            except OSError:
                new_items.append(item)
                continue
            role = _normalize_role(None, path=p, name=p.name)
            entry = {
                "name": p.name if role != ROLE_ORCH else "CCC",
                "path": str(p),
                "role": role,
                "engine": role != ROLE_ORCH,
                "registered_at": _now_iso(),
            }
            if role == ROLE_ORCH:
                found_orch = True
            changed += 1
            new_items.append(entry)
            continue
        if not isinstance(item, dict):
            new_items.append(item)
            continue
        raw = _item_path(item)
        if not raw:
            new_items.append(item)
            continue
        try:
            p = Path(str(raw)).expanduser().resolve()
        except OSError:
            new_items.append(item)
            continue
        name = _item_name(item) or p.name
        role = _normalize_role(item.get("role"), path=p, name=name)
        engine = _normalize_engine(item.get("engine"), role=role)
        entry = dict(item)
        entry["path"] = str(p)
        entry["name"] = "CCC" if role == ROLE_ORCH else name
        before = (item.get("role"), item.get("engine"), item.get("name"))
        entry["role"] = role
        entry["engine"] = engine
        if role == ROLE_ORCH:
            found_orch = True
        after = (entry.get("role"), entry.get("engine"), entry.get("name"))
        if before != after:
            changed += 1
        new_items.append(entry)

    if not found_orch and orch.is_dir() and (orch / ".ccc" / "board").is_dir():
        new_items.insert(
            0,
            {
                "name": "CCC",
                "path": str(orch.resolve()),
                "role": ROLE_ORCH,
                "engine": False,
                "registered_at": _now_iso(),
            },
        )
        changed += 1

    data["workspaces"] = new_items
    data["schema_version"] = SCHEMA_VERSION
    if not dry_run and changed:
        _save(reg, data)
        _log.info("migrated registry roles (%d change(s))", changed)
    return {
        "ok": True,
        "dry_run": dry_run,
        "changed": changed,
        "schema_version": SCHEMA_VERSION,
        "registry": str(reg),
        "workspaces": list_registered_entries(reg),
    }


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
    role: str | None = None,
    engine: bool | None = None,
) -> dict[str, Any]:
    """幂等登记 workspace。返回 {ok, path, name, added, role, engine, registry}。"""
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
    label = (name or root.name).strip() or root.name
    resolved_role = _normalize_role(role, path=root, name=label)
    if engine is None:
        resolved_engine = _normalize_engine(None, role=resolved_role)
    else:
        resolved_engine = _normalize_engine(engine, role=resolved_role)

    for i, item in enumerate(items):
        existing = _item_path(item)
        if not existing:
            continue
        try:
            resolved = str(Path(str(existing)).expanduser().resolve())
        except OSError:
            continue
        if resolved != key:
            continue
        # Update role/engine if caller forces orch or missing fields
        if isinstance(item, dict):
            updated = False
            if item.get("role") != resolved_role and role is not None:
                item["role"] = resolved_role
                updated = True
            elif "role" not in item:
                item["role"] = resolved_role
                updated = True
            if "engine" not in item or (
                engine is not None and bool(item.get("engine")) != resolved_engine
            ):
                item["engine"] = resolved_engine
                updated = True
            if resolved_role == ROLE_ORCH:
                item["name"] = "CCC"
                item["role"] = ROLE_ORCH
                item["engine"] = False
                updated = True
            if updated:
                items[i] = item
                data["workspaces"] = items
                data["schema_version"] = SCHEMA_VERSION
                _save(reg, data)
            return {
                "ok": True,
                "path": key,
                "name": item.get("name") or label,
                "role": item.get("role", resolved_role),
                "engine": bool(item.get("engine", resolved_engine)),
                "added": False,
                "registry": str(reg),
            }
        return {
            "ok": True,
            "path": key,
            "name": label,
            "role": resolved_role,
            "engine": resolved_engine,
            "added": False,
            "registry": str(reg),
        }

    if resolved_role == ROLE_ORCH:
        label = "CCC"
        resolved_engine = False

    entry: dict[str, Any] = {
        "name": label,
        "path": key,
        "role": resolved_role,
        "engine": resolved_engine,
        "registered_at": _now_iso(),
    }
    items.append(entry)
    data["workspaces"] = items
    data["schema_version"] = SCHEMA_VERSION
    _save(reg, data)
    _log.info(
        "registered workspace %s → %s role=%s engine=%s",
        label,
        key,
        resolved_role,
        resolved_engine,
    )
    return {
        "ok": True,
        "path": key,
        "name": label,
        "role": resolved_role,
        "engine": resolved_engine,
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
