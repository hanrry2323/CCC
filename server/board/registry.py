"""Load docs/projects/registry.yaml — project prefix SSOT (ccc005 / north-star S2b)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = _PROJECT_ROOT / "docs" / "projects" / "registry.yaml"


@dataclass(frozen=True)
class ProjectEntry:
    prefix: str | None
    id: str
    name: str
    display: str
    taskable: bool
    forbidden: bool
    status: str
    dossier: str | None
    role: str
    path_m1: str | None
    path_mac2017: str | None


def _as_bool(v: Any) -> bool:
    return bool(v) if not isinstance(v, str) else v.strip().lower() in {"1", "true", "yes"}


def _parse_entry(raw: dict[str, Any]) -> ProjectEntry:
    paths = raw.get("paths") or {}
    prefix = raw.get("prefix")
    if prefix is not None:
        prefix = str(prefix).strip() or None
    dossier = raw.get("dossier")
    if dossier is not None:
        dossier = str(dossier).strip() or None
    return ProjectEntry(
        prefix=prefix,
        id=str(raw.get("id") or "").strip(),
        name=str(raw.get("name") or "").strip(),
        display=str(raw.get("display") or raw.get("name") or "").strip(),
        taskable=_as_bool(raw.get("taskable")),
        forbidden=_as_bool(raw.get("forbidden")),
        status=str(raw.get("status") or "").strip(),
        dossier=dossier,
        role=str(raw.get("role") or "").strip(),
        path_m1=(str(paths["m1"]) if paths.get("m1") not in (None, "") else None),
        path_mac2017=(
            str(paths["mac2017"]) if paths.get("mac2017") not in (None, "") else None
        ),
    )


@lru_cache(maxsize=4)
def load_projects(registry_path: str | None = None) -> tuple[ProjectEntry, ...]:
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"project registry missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("registry root must be a mapping")
    projects = data.get("projects")
    if not isinstance(projects, list):
        raise ValueError("registry.projects must be a list")
    out: list[ProjectEntry] = []
    for i, item in enumerate(projects):
        if not isinstance(item, dict):
            raise ValueError(f"projects[{i}] must be a mapping")
        out.append(_parse_entry(item))
    return tuple(out)


def clear_registry_cache() -> None:
    load_projects.cache_clear()


def card_prefixes(registry_path: str | None = None) -> dict[str, str]:
    """PREFIXES: non-null prefix and not forbidden → display name."""
    result: dict[str, str] = {}
    for p in load_projects(registry_path):
        if not p.prefix or p.forbidden:
            continue
        result[p.prefix] = p.display or p.name or p.prefix
    return result


def forbidden_prefixes(registry_path: str | None = None) -> frozenset[str]:
    return frozenset(p.prefix for p in load_projects(registry_path) if p.prefix and p.forbidden)


def taskable_names(registry_path: str | None = None) -> frozenset[str]:
    """Names/ids used by GET /projects is_taskable (forbidden forced false)."""
    names: set[str] = set()
    for p in load_projects(registry_path):
        if p.forbidden or not p.taskable:
            continue
        if p.name:
            names.add(p.name)
        if p.id:
            names.add(p.id)
        if p.display:
            names.add(p.display)
    return frozenset(names)
