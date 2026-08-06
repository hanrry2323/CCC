"""Parse ``ccc-plan`` blocks for plan-to-cards (north-star W1).

Supports JSON objects and a minimal YAML subset matching the north-star schema.
No PyYAML dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


class PlanError(ValueError):
    """Invalid ccc-plan input."""


@dataclass
class PlanSlice:
    title: str
    slug: str
    acceptance: list[str] = field(default_factory=list)
    whitelist: list[str] = field(default_factory=list)
    executor: str = "OpenCode"


@dataclass
class CccPlan:
    title: str
    project: str
    slices: list[PlanSlice] = field(default_factory=list)


_FENCE_RE = re.compile(
    r"```ccc-plan\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_PREFIX_RE = re.compile(r"^[a-z]{2,4}$")


def extract_plan_text(raw: str) -> str:
    """Return fenced ccc-plan body, or whole stripped text if no fence."""
    text = raw.strip()
    if not text:
        raise PlanError("empty plan input")
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


def parse_ccc_plan(raw: str) -> CccPlan:
    """Parse plan text (fence optional) into CccPlan; validate hard rules."""
    body = extract_plan_text(raw)
    if body.startswith("{"):
        data = json.loads(body)
    else:
        data = _parse_minimal_yaml(body)
    return plan_from_dict(data)


def plan_from_dict(data: Any) -> CccPlan:
    if not isinstance(data, dict):
        raise PlanError("plan root must be an object")
    title = str(data.get("title") or "").strip()
    project = str(data.get("project") or "").strip()
    slices_raw = data.get("slices")
    if not title:
        raise PlanError("title is required")
    if not _PREFIX_RE.match(project):
        raise PlanError(f"illegal project prefix: {project!r} (need 2-4 lowercase letters)")
    if project == "qh":
        raise PlanError("prefix qh (QuantHive) is forbidden on CCC")
    if not isinstance(slices_raw, list) or not slices_raw:
        raise PlanError("slices must be a non-empty list")

    slices: list[PlanSlice] = []
    for i, item in enumerate(slices_raw):
        if not isinstance(item, dict):
            raise PlanError(f"slices[{i}] must be an object")
        st = str(item.get("title") or "").strip()
        slug = str(item.get("slug") or "").strip()
        if not st:
            raise PlanError(f"slices[{i}].title is required")
        if not _SLUG_RE.match(slug):
            raise PlanError(f"slices[{i}].slug illegal: {slug!r}")
        acc = item.get("acceptance") or []
        if not isinstance(acc, list) or not acc:
            raise PlanError(f"slices[{i}].acceptance must be a non-empty list")
        acc_list = [str(a).strip() for a in acc if str(a).strip()]
        if not acc_list:
            raise PlanError(f"slices[{i}].acceptance empty after trim")
        wl = item.get("whitelist") or []
        if not isinstance(wl, list):
            raise PlanError(f"slices[{i}].whitelist must be a list")
        wl_list = [str(w).strip() for w in wl if str(w).strip()]
        executor = str(item.get("executor") or "OpenCode").strip() or "OpenCode"
        slices.append(
            PlanSlice(
                title=st,
                slug=slug,
                acceptance=acc_list,
                whitelist=wl_list,
                executor=executor,
            )
        )
    return CccPlan(title=title, project=project, slices=slices)


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML for north-star ccc-plan (maps + lists of scalars/maps)."""
    lines = text.splitlines()
    root: dict[str, Any] = {}
    i = 0
    n = len(lines)

    def indent_of(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def skip_blank(idx: int) -> int:
        while idx < n and (not lines[idx].strip() or lines[idx].strip().startswith("#")):
            idx += 1
        return idx

    def parse_scalar(raw: str) -> Any:
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                return json.loads(s.replace("'", '"'))
            except json.JSONDecodeError as exc:
                raise PlanError(f"bad inline list: {s}") from exc
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        if s in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[s]
        return s

    def parse_block_list(start: int, base_indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        idx = start
        while idx < n:
            idx = skip_blank(idx)
            if idx >= n:
                break
            line = lines[idx]
            ind = indent_of(line)
            if ind < base_indent:
                break
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            rest = stripped[2:].strip()
            idx += 1
            if rest and ":" in rest and not rest.startswith("["):
                # map entry on same line as `- key: val` then nested keys
                key, _, val = rest.partition(":")
                obj: dict[str, Any] = {}
                val = val.strip()
                if val:
                    obj[key.strip()] = parse_scalar(val)
                else:
                    # value is nested block
                    nested, idx = parse_value_block(idx, ind + 2)
                    obj[key.strip()] = nested
                # more keys at ind+2
                while idx < n:
                    idx = skip_blank(idx)
                    if idx >= n:
                        break
                    nl = lines[idx]
                    nind = indent_of(nl)
                    if nind <= ind:
                        break
                    if nl.strip().startswith("- "):
                        break
                    if ":" not in nl:
                        break
                    k, _, v = nl.strip().partition(":")
                    idx += 1
                    v = v.strip()
                    if v:
                        obj[k.strip()] = parse_scalar(v)
                    else:
                        nested, idx = parse_value_block(idx, nind + 2)
                        obj[k.strip()] = nested
                items.append(obj)
            elif rest:
                items.append(parse_scalar(rest))
            else:
                nested, idx = parse_value_block(idx, ind + 2)
                items.append(nested)
        return items, idx

    def parse_value_block(start: int, base_indent: int) -> tuple[Any, int]:
        idx = skip_blank(start)
        if idx >= n:
            return {}, idx
        line = lines[idx]
        ind = indent_of(line)
        if ind < base_indent:
            return {}, idx
        if line.strip().startswith("- "):
            return parse_block_list(idx, ind)
        # map
        obj: dict[str, Any] = {}
        while idx < n:
            idx = skip_blank(idx)
            if idx >= n:
                break
            line = lines[idx]
            ind = indent_of(line)
            if ind < base_indent:
                break
            if line.strip().startswith("- "):
                break
            if ":" not in line:
                raise PlanError(f"expected key: at line {idx + 1}: {line}")
            key, _, val = line.strip().partition(":")
            idx += 1
            val = val.strip()
            if val:
                obj[key.strip()] = parse_scalar(val)
            else:
                nested, idx = parse_value_block(idx, ind + 2)
                obj[key.strip()] = nested
        return obj, idx

    while i < n:
        i = skip_blank(i)
        if i >= n:
            break
        line = lines[i]
        if indent_of(line) != 0:
            raise PlanError(f"top-level must be flush left (line {i + 1})")
        if ":" not in line:
            raise PlanError(f"expected key: at line {i + 1}")
        key, _, val = line.strip().partition(":")
        i += 1
        val = val.strip()
        if val:
            root[key.strip()] = parse_scalar(val)
        else:
            nested, i = parse_value_block(i, 2)
            root[key.strip()] = nested
    return root

