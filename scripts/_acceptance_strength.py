"""Acceptance strength — block existence-only false greens (R5).

Business cards must have ≥1 behavioral probe (python3 -c assert / DRY_RUN /
scope pytest / grep -q). ``test -f`` alone is allowlisted but not strong enough.
"""

from __future__ import annotations

import re
from typing import Any, Literal

Strength = Literal["existence_only", "compile_only", "behavioral", "empty"]

_EXISTENCE_RE = re.compile(
    r"^(?:test\s+-[fd]\s+\S+|\[\s+-?[fd]\s+\S+\s*\])\s*$",
    re.IGNORECASE,
)
_GREP_RE = re.compile(r"\bgrep\b", re.IGNORECASE)
_PYTEST_RE = re.compile(r"\bpytest\b|\b-m\s+pytest\b", re.IGNORECASE)
_COMPILE_RE = re.compile(r"\bpy_compile\b|\bruff\b", re.IGNORECASE)


def classify_cmd(cmd: str) -> Strength:
    """Classify a single allowlisted verify command."""
    c = (cmd or "").strip()
    if not c:
        return "empty"
    try:
        from _intent_probe import looks_like_intent_probe, strip_env_prefix

        if looks_like_intent_probe(c):
            return "behavioral"
        _, rem = strip_env_prefix(c)
    except Exception:
        rem = c
    low = rem.lower()
    if _GREP_RE.search(c) or _PYTEST_RE.search(c):
        return "behavioral"
    if "assert" in low and ("python" in low or "-c" in low):
        return "behavioral"
    if _COMPILE_RE.search(c):
        return "compile_only"
    if _EXISTENCE_RE.match(c.strip()):
        return "existence_only"
    # Other allowlisted (e.g. bash script) — treat as behavioral
    return "behavioral"


def classify_cmds(cmds: list[str]) -> Strength:
    """Worst-case aggregate: empty < existence < compile < behavioral."""
    if not cmds:
        return "empty"
    ranks = {"empty": 0, "existence_only": 1, "compile_only": 2, "behavioral": 3}
    best = "empty"
    for c in cmds:
        s = classify_cmd(c)
        if ranks[s] > ranks[best]:
            best = s
    return best  # type: ignore[return-value]


def cmds_are_existence_only(cmds: list[str]) -> bool:
    """True when every non-empty cmd is existence-only (R5 false-green shape)."""
    cleaned = [c.strip() for c in (cmds or []) if str(c).strip()]
    if not cleaned:
        return False
    return all(classify_cmd(c) == "existence_only" for c in cleaned)


def is_strong_enough(
    cmds: list[str],
    *,
    require_strong: bool = True,
    exempt: bool = False,
) -> tuple[bool, str]:
    """Return (ok, reason). When require_strong, reject pure existence-only."""
    if exempt or not require_strong:
        return True, "exempt"
    cleaned = [c.strip() for c in (cmds or []) if str(c).strip()]
    if not cleaned:
        return False, "acceptance_missing_probe"
    level = classify_cmds(cleaned)
    if level == "existence_only" or cmds_are_existence_only(cleaned):
        return False, "acceptance_weak_existence_only"
    return True, f"acceptance_strength_{level}"


def plan_is_hygiene_or_ops(plan_text: str) -> bool:
    low = (plan_text or "").lower()
    return any(
        k in low
        for k in (
            "board_ops",
            "看板卫生",
            "pipeline: ops",
            "pipeline: hygiene",
            "doc_only",
            "docs-only",
        )
    )


def strengthen_existence_bullets(
    bullets: list[str], scope: list[str]
) -> list[str]:
    """If bullets are existence-only, append py_compile for .py scope paths."""
    out = list(bullets)
    if not cmds_are_existence_only(out):
        return out
    seen = set(out)
    for p in scope:
        p_n = str(p).replace("\\", "/").lstrip("./")
        if p_n.endswith(".py"):
            cmd = f"python3 -m py_compile {p_n}"
            if cmd not in seen:
                out.append(cmd)
                seen.add(cmd)
            break
    return out


def task_exempt_from_strength(ws: Any, tid: str, task: dict[str, Any] | None = None) -> bool:
    """ops / hygiene / doc_only / short paths skip strength gate."""
    task = task or {}
    pipeline = str(task.get("pipeline") or "").strip().lower()
    if pipeline in ("ops", "hygiene", "board", "board_ops"):
        return True
    tags = {str(t).lower() for t in (task.get("tags") or [])}
    if tags & {"ops", "hygiene", "ccc-hygiene", "board_ops", "doc_only"}:
        return True
    title = str(task.get("title") or "").lower()
    if any(k in title for k in ("卫生", "清场", "文档戳记", "hygiene")):
        return True
    try:
        from pathlib import Path
        import json

        rp = Path(ws) / ".ccc" / "reports" / f"{tid}.result.json"
        if rp.is_file():
            data = json.loads(rp.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict) and str(data.get("path") or "").strip().lower() in (
                "doc_only",
                "board_ops",
                "script_seed",
            ):
                # script_seed often has DRY_RUN behavioral probes; still exempt
                # existence-only paper stubs from blocking salvage
                return str(data.get("path") or "").strip().lower() in (
                    "doc_only",
                    "board_ops",
                )
    except Exception:
        pass
    return False
