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


_LATE_STAGE_MARKERS = (
    "paper_intent_probe",
    "paper-intent-probe",
    "60s",
    "end-to-end",
    "e2e",
)


def is_late_stage_probe(cmd: str) -> bool:
    """paper / e2e / long-running probes that must not ride on unit work cards."""
    low = (cmd or "").lower()
    return any(m in low for m in _LATE_STAGE_MARKERS)


def is_behavioral_probe(cmd: str) -> bool:
    return classify_cmd(cmd) == "behavioral"


def harden_work_acceptance_bullets(
    bullets: list[str],
    *,
    scope: list[str] | None = None,
    max_n: int = 2,
    strip_late: bool = True,
) -> list[str]:
    """Fanout second gate: prefer 1～2 strong probes; drop existence heap + mixed late.

    When ≥1 behavioral probe exists, drop pure ``test -f/-d``. Cap at max_n.
    Strip paper/e2e when strip_late (default for non-paper phases).
    """
    cleaned = [str(c).strip() for c in (bullets or []) if str(c).strip()]
    if strip_late:
        cleaned = [c for c in cleaned if not is_late_stage_probe(c)]
    behavioral = [c for c in cleaned if is_behavioral_probe(c)]
    if behavioral:
        out = behavioral[: max(1, max_n)]
    else:
        # keep compile / whatever remains, then strengthen
        non_exist = [
            c for c in cleaned if classify_cmd(c) != "existence_only"
        ]
        out = (non_exist or cleaned)[: max(1, max_n)]
        out = strengthen_existence_bullets(out, scope or [])
        # still existence-only after strengthen? keep py_compile result
        if cmds_are_existence_only(out) and scope:
            out = strengthen_existence_bullets(out, scope)
    # final cap
    return out[: max(1, max_n)] if out else out


def work_acceptance_gate_errors(cmds: list[str]) -> list[dict[str, str]]:
    """Mirror transfer_gate budget/strength for fanout work plans."""
    errs: list[dict[str, str]] = []
    uniq = []
    seen: set[str] = set()
    for c in cmds or []:
        key = " ".join(str(c).split())
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    ok_s, reason = is_strong_enough(uniq, require_strong=True)
    if not ok_s:
        errs.append(
            {
                "code": "acceptance_weak",
                "message": f"work 验收过弱（{reason}）",
            }
        )
    if len(uniq) > 3:
        errs.append(
            {
                "code": "acceptance_too_wide",
                "message": f"work 验收 {len(uniq)} 条（上限 3）",
            }
        )
    joined = "\n".join(uniq).lower()
    has_unit = "pytest" in joined or "python3 -c" in joined or "python -c" in joined
    has_late = any(m in joined for m in _LATE_STAGE_MARKERS)
    if has_unit and has_late and len(uniq) >= 2:
        errs.append(
            {
                "code": "acceptance_mixed_intent",
                "message": "work 同时含 unit 与 paper/e2e",
            }
        )
    return errs


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
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("ccc.acceptance_strength").warning(
            "read plan meta for doc_only/board_ops failed: %s", exc
        )
    return False
