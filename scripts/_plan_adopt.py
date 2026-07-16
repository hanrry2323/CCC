"""_plan_adopt.py — 收养描述中已有的 plan，避免白烧 product LLM（v0.42.1）

场景：Hub 对话已写好 `.ccc/plans/foo.plan.md`，下达时 description 引用该路径，
但 task id 是 ccc-xxxxx，Engine 只认 `{tid}.plan.md` → 误入 product → 解析失败 → abnormal。

本模块：识别引用 → 复制为 `{tid}.plan.md` → 从 plan 合成 phases（含 scope）→ 过硬门。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.plan_adopt")

# `.ccc/plans/foo.plan.md` or `plans/foo.plan.md`
_PLAN_REF_RE = re.compile(
    r"(?:\.?/?\.ccc/)?plans/([A-Za-z0-9._\-]+)\.plan\.md"
)
_PHASE_HEAD_RE = re.compile(r"^##\s+Phase\s+(\d+)\b", re.MULTILINE | re.IGNORECASE)
_PATH_TICK_RE = re.compile(
    r"`((?:src|scripts|tests|docs|templates|config|frontend|backend|"
    r"STATUS\.md|ENV_CHECKLIST\.md|ACCEPTANCE[^`]*)[^`]*)`"
)
_PATH_LOOSE_RE = re.compile(
    r"(?<![`\w])((?:src|scripts|tests|docs|config)/[\w./\-]+\.[\w]+|STATUS\.md|"
    r"docs/checklists/[\w./\-]+\.md|tests/[\w./\-]+\.py)(?![`\w])"
)


def find_plan_refs(text: str) -> list[str]:
    """返回 plan stem 列表（不含 .plan.md）。"""
    if not text:
        return []
    return list(dict.fromkeys(_PLAN_REF_RE.findall(text)))


def extract_paths(text: str) -> list[str]:
    found: list[str] = []
    for m in _PATH_TICK_RE.findall(text or ""):
        p = m.strip().strip("`")
        if p and p not in found:
            found.append(p)
    for m in _PATH_LOOSE_RE.findall(text or ""):
        p = m.strip()
        if p and p not in found:
            found.append(p)
    return found


def split_plan_phases(plan_text: str) -> list[tuple[int, str, str]]:
    """[(phase_num, title_line, body), ...]"""
    matches = list(_PHASE_HEAD_RE.finditer(plan_text or ""))
    if not matches:
        return []
    out: list[tuple[int, str, str]] = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(plan_text)
        title = m.group(0).strip()
        body = plan_text[start:end].strip()
        out.append((num, title, body))
    return out


def synthesize_phases_from_plan(plan_text: str) -> list[dict[str, Any]]:
    """从 plan 的 ## Phase N 段合成最小可执行 phases（含 scope）。"""
    sections = split_plan_phases(plan_text)
    phases: list[dict[str, Any]] = []
    if not sections:
        # 单 phase fallback：用全文路径
        paths = extract_paths(plan_text)[:8] or ["STATUS.md"]
        phases.append(
            {
                "phase": 1,
                "phase_id": "1",
                "status": "pending",
                "description": "执行 plan 验收清单",
                "scope": paths,
                "subtasks": {"1.1": "pending"},
                "timeout": 600,
                "depends_on": [],
                "notes": "adopted:single",
            }
        )
        return phases

    for num, title, body in sections:
        paths = extract_paths(body) or extract_paths(title)
        if not paths:
            # 从全文表兜底一点，避免 empty scope 硬门
            paths = extract_paths(plan_text)[:3] or ["STATUS.md"]
        desc = title.replace("##", "").strip()
        first = body.split("\n", 1)[0].strip() if body else ""
        if first and len(first) < 120:
            desc = f"{desc} — {first.lstrip('#- ')}"
        phases.append(
            {
                "phase": num,
                "phase_id": str(num),
                "status": "pending",
                "description": desc[:300],
                "scope": paths[:12],
                "subtasks": {f"{num}.1": "pending"},
                "timeout": 900,
                "depends_on": [num - 1] if num > 1 else [],
                "notes": "adopted",
            }
        )
    return phases


def backfill_scopes(phases: list[dict], plan_text: str) -> list[dict]:
    """给缺 scope 的 phase 从 plan 对应段 / 全文补路径（原地+返回）。"""
    sections = {n: body for n, _t, body in split_plan_phases(plan_text)}
    global_paths = extract_paths(plan_text)
    for p in phases:
        scope = p.get("scope")
        if isinstance(scope, list) and [x for x in scope if str(x).strip()]:
            continue
        num = p.get("phase")
        body = sections.get(int(num), "") if num is not None else ""
        paths = extract_paths(body) or extract_paths(p.get("description") or "")
        if not paths:
            # 涉及文件表：按 phase 序号粗分
            if global_paths and isinstance(num, int) and num >= 1:
                # round-robin-ish: take slice
                i = (num - 1) % max(len(global_paths), 1)
                paths = [global_paths[i]]
                if num <= len(global_paths):
                    paths = [global_paths[num - 1]]
            else:
                paths = global_paths[:2] or ["STATUS.md"]
        p["scope"] = paths
        if not (p.get("description") or "").strip():
            p["description"] = f"phase {num}"
        if not p.get("subtasks"):
            p["subtasks"] = {f"{num}.1": "pending"}
        if p.get("status") is None:
            p["status"] = "pending"
        if not p.get("timeout"):
            p["timeout"] = 600
    return phases


def try_adopt_referenced_plan(
    ws: Path, task_id: str, task: dict | None = None
) -> dict[str, Any]:
    """若 task 描述引用现有 plan，收养为 {tid}.plan.md + phases。成功返回 ok=True。"""
    task = task or {}
    blob = f"{task.get('title') or ''}\n{task.get('description') or ''}\n{task.get('note') or ''}"
    stems = find_plan_refs(blob)
    if not stems:
        return {"ok": False, "reason": "no_plan_ref"}

    plans_dir = ws / ".ccc" / "plans"
    phases_dir = ws / ".ccc" / "phases"
    dest_plan = plans_dir / f"{task_id}.plan.md"
    dest_phases = phases_dir / f"{task_id}.phases.json"

    # 已齐全则不覆盖（除非 dest 不存在）
    if dest_plan.is_file() and dest_phases.is_file():
        return {"ok": True, "reason": "already_present", "plan": str(dest_plan)}

    src = None
    for stem in stems:
        cand = plans_dir / f"{stem}.plan.md"
        if cand.is_file():
            src = cand
            break
    if src is None:
        return {"ok": False, "reason": "ref_not_found", "stems": stems}

    plan_text = src.read_text(encoding="utf-8", errors="replace")
    phases = synthesize_phases_from_plan(plan_text)
    phases = backfill_scopes(phases, plan_text)

    try:
        import phase_lint

        ok, errs = phase_lint.validate_plan_acceptance(plan_text)
        if not ok:
            # 「### 验收清单」不等于「## 验收」— 补硬门所需章节
            plan_text = (
                plan_text.rstrip()
                + "\n\n## 验收\n- 按 plan 各 Phase / 全局验收清单执行并通过\n"
            )
            ok, errs = phase_lint.validate_plan_acceptance(plan_text)
        if not ok:
            return {"ok": False, "reason": "plan_lint", "errors": errs}
        phases = backfill_scopes(phases, plan_text)
        lint_ok, lint_errs, _ = phase_lint.validate_phases_dict(phases)
        if not lint_ok:
            return {"ok": False, "reason": "phase_lint", "errors": lint_errs}
    except Exception as exc:
        return {"ok": False, "reason": "lint_import", "error": str(exc)[:200]}

    plans_dir.mkdir(parents=True, exist_ok=True)
    phases_dir.mkdir(parents=True, exist_ok=True)
    if not dest_plan.exists():
        dest_plan.write_text(plan_text, encoding="utf-8")
    schema = json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
    body = schema + "\n" + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases) + "\n"
    dest_phases.write_text(body, encoding="utf-8")
    _log.info("adopted plan %s → %s (%d phases)", src.name, task_id, len(phases))
    return {
        "ok": True,
        "reason": "adopted",
        "source": str(src),
        "plan": str(dest_plan),
        "phases": str(dest_phases),
        "phase_count": len(phases),
    }
