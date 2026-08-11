"""Load docs/projects/registry.yaml — project prefix SSOT (ccc005 / north-star S2b).

Stdlib only (no PyYAML): production web-server is zero-dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

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
    location: str = ""
    # 业务仓隔离（2026-08-12 · 事故修复）：每卡独立 worktree + 同仓并发上限
    isolation_worktree_root: str = ""
    isolation_max_concurrent: int = 1


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes"}


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s in ("null", "~", ""):
        return None
    if s in ("true", "false"):
        return s == "true"
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _parse_registry_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML for registry.yaml (mapping + list of mappings + nested paths)."""
    lines = text.splitlines()
    root: dict[str, Any] = {}
    projects: list[dict[str, Any]] = []
    i = 0
    n = len(lines)
    in_projects = False
    current: dict[str, Any] | None = None
    in_paths = False
    in_isolation = False

    def indent_of(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    while i < n:
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = indent_of(line)
        stripped = line.strip()

        if not in_projects:
            if stripped.startswith("projects:"):
                in_projects = True
                root["projects"] = projects
                continue
            if ":" in stripped and ind == 0:
                key, _, val = stripped.partition(":")
                root[key.strip()] = _parse_scalar(val) if val.strip() else None
            continue

        if stripped.startswith("- "):
            current = {}
            projects.append(current)
            in_paths = False
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                key, _, val = rest.partition(":")
                current[key.strip()] = _parse_scalar(val)
            continue

        if current is None:
            continue

        if stripped.startswith("paths:"):
            in_paths = True
            in_isolation = False
            current["paths"] = {}
            continue

        if stripped.startswith("isolation:"):
            in_paths = False
            in_isolation = True
            current["isolation"] = {}
            continue

        # paths children are indented deeper than project fields (typically 6 spaces)
        if in_paths and ind >= 6 and ":" in stripped:
            key, _, val = stripped.partition(":")
            current.setdefault("paths", {})[key.strip()] = _parse_scalar(val)
            continue

        if in_isolation and ind >= 6 and ":" in stripped:
            key, _, val = stripped.partition(":")
            current.setdefault("isolation", {})[key.strip()] = _parse_scalar(val)
            continue

        if ":" in stripped:
            in_paths = False
            in_isolation = False
            key, _, val = stripped.partition(":")
            current[key.strip()] = _parse_scalar(val)

    return root


def _default_worktree_root(path_mac2017: str | None, prefix: str | None) -> str:
    """业务仓 worktree 默认根：`<业务仓父目录>/.ccc-wt/<prefix>/`。

    放业务仓同级（不在业务仓内），避免污染主仓工作区；前缀用于多项目并存的命名空间。
    """
    if not path_mac2017 or not prefix:
        return ""
    return str(Path(path_mac2017).expanduser().parent / ".ccc-wt" / prefix)


def _parse_entry(raw: dict[str, Any]) -> ProjectEntry:
    paths = raw.get("paths") or {}
    if not isinstance(paths, dict):
        paths = {}
    prefix = raw.get("prefix")
    if prefix is not None:
        prefix = str(prefix).strip() or None
    dossier = raw.get("dossier")
    if dossier is not None:
        dossier = str(dossier).strip() or None
    isolation = raw.get("isolation") or {}
    if not isinstance(isolation, dict):
        isolation = {}
    path_mac2017 = str(paths["mac2017"]) if paths.get("mac2017") not in (None, "") else None
    iso_root = str(isolation.get("worktree_root") or "").strip() or ""
    if not iso_root:
        # 默认隔离根只对 mac2017-apps 业务仓生成；平台例外（ccc）不走隔离
        location_tags = {t.strip() for t in str(raw.get("location") or "").split(",") if t.strip()}
        if _as_bool(raw.get("taskable")) and "mac2017-apps" in location_tags:
            iso_root = _default_worktree_root(path_mac2017, prefix)
    try:
        iso_max = int(isolation.get("max_concurrent") or 1)
    except (TypeError, ValueError):
        iso_max = 1
    if iso_max < 1:
        iso_max = 1
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
        path_mac2017=path_mac2017,
        location=str(raw.get("location") or "").strip(),
        isolation_worktree_root=iso_root,
        isolation_max_concurrent=iso_max,
    )


@lru_cache(maxsize=4)
def load_projects(registry_path: str | None = None) -> tuple[ProjectEntry, ...]:
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"project registry missing: {path}")
    data = _parse_registry_yaml(path.read_text(encoding="utf-8"))
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


def check_path_locations(
    projects: tuple[ProjectEntry, ...] | list[ProjectEntry] | None = None,
) -> list[str]:
    """仓库路径归属校验：非遗留项目路径必须落在所属 location 树内。

    location 取值（逗号分隔可多个）：
    - ``m1-program``：M1 业务根 ``~/program/``
    - ``mac2017-apps``：2017 业务根 ``~/program/apps/``
    - ``mac2017-platform``：2017 平台例外（CCC 本体 ``~/program/CCC``）
    - ``legacy``：散落仓豁免（只标注不迁移）

    返回问题清单（空 = 合规）。只做结构校验，不因校验失败阻断既有调用。
    """
    issues: list[str] = []
    projects = projects if projects is not None else load_projects()
    for p in projects:
        tags = {t.strip() for t in (p.location or "").split(",") if t.strip()}
        label = p.prefix or p.id or "?"
        if not tags:
            issues.append(
                f"{label}: 缺 location（mac2017-apps / m1-program / mac2017-platform / legacy）"
            )
            continue
        if "legacy" in tags:
            continue
        if p.path_m1:
            if "m1-program" not in tags:
                issues.append(f"{label}: M1 有路径 {p.path_m1} 但 location 缺 m1-program")
            elif "/program/" not in p.path_m1:
                issues.append(f"{label}: M1 路径越界 {p.path_m1}（须在 ~/program/ 下）")
        if p.path_mac2017:
            if "mac2017-apps" not in tags and "mac2017-platform" not in tags:
                issues.append(
                    f"{label}: 2017 有路径 {p.path_mac2017} 但 location 缺 mac2017-apps/platform"
                )
            elif "mac2017-apps" in tags and "/program/apps/" not in p.path_mac2017:
                issues.append(
                    f"{label}: 2017 路径越界 {p.path_mac2017}（业务仓须在 ~/program/apps/ 下）"
                )
            elif "mac2017-platform" in tags and (
                "/program/" not in p.path_mac2017 or "/program/apps/" in p.path_mac2017
            ):
                issues.append(
                    f"{label}: 2017 平台路径异常 {p.path_mac2017}（平台例外 ~/program/CCC）"
                )
        if p.isolation_worktree_root:
            wt = Path(p.isolation_worktree_root).expanduser()
            if "mac2017-apps" in tags and not str(wt).startswith("/Users/fan/program/"):
                issues.append(
                    f"{label}: 隔离 worktree 根越界 {p.isolation_worktree_root}（须在 ~/program/ 下）"
                )
            elif p.path_mac2017 and str(wt).startswith(str(Path(p.path_mac2017).expanduser()) + "/"):
                issues.append(
                    f"{label}: 隔离 worktree 根 {p.isolation_worktree_root} 不能位于业务仓内部"
                )
    return issues


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
