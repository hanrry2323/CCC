"""_workspace_registry.py — Engine 可消费 workspace 登记（v0.42.1）

产品规则：
- Engine 默认只扫 CCC（防全盘 invent）
- 用户在 Hub/Board **显式下达**到某项目时，把该 path 写入 ~/.ccc/workspaces.json
- 只增不删、幂等；绝不回退到 CCC_DISCOVER_ALL 全扫
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.workspace_registry")

REGISTRY_FILE = Path.home() / ".ccc" / "workspaces.json"


def registry_path() -> Path:
    return REGISTRY_FILE


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


def list_registered_paths(registry: Path | None = None) -> list[Path]:
    data = _load(registry or REGISTRY_FILE)
    out: list[Path] = []
    seen: set[str] = set()
    for item in data.get("workspaces") or []:
        raw = item if isinstance(item, str) else (item.get("path") if isinstance(item, dict) else None)
        if not raw:
            continue
        p = Path(str(raw)).expanduser().resolve()
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def register_workspace(
    path: Path | str,
    *,
    name: str | None = None,
    registry: Path | None = None,
) -> dict[str, Any]:
    """幂等登记 workspace。返回 {ok, path, name, added, registry}。"""
    root = Path(path).expanduser().resolve()
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
        existing = item if isinstance(item, str) else (item.get("path") if isinstance(item, dict) else None)
        if existing and str(Path(str(existing)).expanduser().resolve()) == key:
            return {
                "ok": True,
                "path": key,
                "name": name or root.name,
                "added": False,
                "registry": str(reg),
            }

    label = (name or root.name).strip() or root.name
    items.append({"name": label, "path": key})
    data["workspaces"] = items
    reg.parent.mkdir(parents=True, exist_ok=True)
    tmp = reg.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(reg)
    _log.info("registered workspace %s → %s", label, key)
    return {
        "ok": True,
        "path": key,
        "name": label,
        "added": True,
        "registry": str(reg),
    }
