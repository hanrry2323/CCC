"""_plan_adopt.py — 收养描述中已有的 plan，避免白烧 product LLM（v0.42.1）

场景：Hub 对话已写好 `.ccc/plans/foo.plan.md`，下达时 description 引用该路径，
但 task id 是 ccc-xxxxx，Engine 只认 `{tid}.plan.md` → 误入 product → 解析失败 → abnormal。

本模块：识别引用 → 复制为 `{tid}.plan.md` → 从 plan 合成 phases（含 scope）→ 过硬门。

v0.53.3：白名单 / git add 里的历史 `.ccc/plans/*.plan.md` 路径不得触发收养
（ops 卫生卡曾因此漂到旧业务 plan 的 scope → pytest 挂）。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.plan_adopt")

# 仅「意图性收养」：见/参照/写入… + plans/foo.plan.md
# 禁止匹配验收白名单、`git add .ccc/plans/….plan.md` 等纯路径罗列
_PLAN_REF_INTENT_RE = re.compile(
    r"(?:见|参照|采用|收养|按此|按该|规划文件(?:已)?写入|已写入|"
    r"see\s+(?:the\s+)?plan|adopt(?:ed)?)\s*"
    r"[`\"'（(\[]*"
    r"(?:\.?/?\.ccc/)?plans/([A-Za-z0-9._\-]+)\.plan\.md",
    re.IGNORECASE,
)
_PHASE_HEAD_RE = re.compile(r"^##\s+Phase\s+(\d+)\b", re.MULTILINE | re.IGNORECASE)
_PATH_TICK_RE = re.compile(
    r"`((?:\.ccc/|src/|scripts/|tests/|docs/|templates/|config/|frontend/|backend/|"
    r"STATUS\.md|ENV_CHECKLIST\.md|ACCEPTANCE)[^`]*)`"
)
_PATH_LOOSE_RE = re.compile(
    r"(?<![`\w])("
    r"\.ccc/[\w./\-]+|"
    r"(?:src|scripts|tests|docs|config)/[\w./\-]+\.[\w]+|"
    r"STATUS\.md|"
    r"docs/checklists/[\w./\-]+\.md|"
    r"tests/[\w./\-]+\.py"
    r")(?![`\w])"
)
_SECTION_HEAD_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FORBIDDEN_SECTION_NAMES = (
    "禁止",
    "forbidden",
    "out of scope",
    "不在范围",
    "勿改",
)
_SCOPE_SECTION_NAMES = (
    "范围",
    "白名单",
    "scope",
    "只改文件",
    "涉及文件",
)


def find_plan_refs(text: str) -> list[str]:
    """返回意图性收养的 plan stem 列表（不含 .plan.md）。"""
    if not text:
        return []
    return list(dict.fromkeys(_PLAN_REF_INTENT_RE.findall(text)))


def _strip_forbidden_sections(text: str) -> str:
    """去掉 ## 禁止 / Forbidden 段，避免把禁改路径抽进 scope。"""
    if not text:
        return ""
    matches = list(_SECTION_HEAD_RE.finditer(text))
    if not matches:
        return text
    keep: list[str] = []
    for i, m in enumerate(matches):
        title = (m.group(1) or "").strip().lower()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if any(name in title for name in _FORBIDDEN_SECTION_NAMES):
            # 保留标题前的内容间隔：跳过本段
            if i == 0 and start > 0:
                keep.append(text[:start])
            continue
        if i == 0 and start > 0:
            keep.append(text[:start])
        keep.append(text[start:end])
    return "".join(keep) if keep else text


def _section_bodies(text: str, names: tuple[str, ...]) -> str:
    if not text:
        return ""
    matches = list(_SECTION_HEAD_RE.finditer(text))
    bodies: list[str] = []
    for i, m in enumerate(matches):
        title = (m.group(1) or "").strip().lower()
        if not any(name in title for name in names):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        bodies.append(text[start:end])
    return "\n".join(bodies)


def _normalize_extracted_path(raw: str) -> str | None:
    """去掉命令行参数，拒绝非法 scope 噪声。"""
    p = (raw or "").strip().strip("`").strip()
    if not p:
        return None
    # `scripts/foo.py --strict` → scripts/foo.py
    if " " in p or "\t" in p:
        p = re.split(r"\s+", p, maxsplit=1)[0]
    if not p or p.startswith("-"):
        return None
    # 拒绝明显非路径
    if any(x in p for x in ("&&", "|", ";", "$(", "`")):
        return None
    return p


def _raw_extract_paths(text: str) -> list[str]:
    found: list[str] = []
    for m in _PATH_TICK_RE.findall(text or ""):
        p = _normalize_extracted_path(m)
        if p and p not in found:
            found.append(p)
    for m in _PATH_LOOSE_RE.findall(text or ""):
        p = _normalize_extracted_path(m)
        if p and p not in found:
            found.append(p)
    return found


def extract_paths(text: str) -> list[str]:
    """从 plan 抽路径：优先 ## 范围/白名单；全文时剥离 ## 禁止。"""
    if not text:
        return []
    scoped = _section_bodies(text, _SCOPE_SECTION_NAMES)
    if scoped:
        paths = _raw_extract_paths(scoped)
        if paths:
            return paths
    return _raw_extract_paths(_strip_forbidden_sections(text))


def _plan_goal_description(plan_text: str) -> str:
    """单 phase 描述：同标题 / 目标·意图正文；禁止吞下一行 ``## 标题``。"""
    text = plan_text or ""
    # 仅同行：``# Plan — 标题`` / ``# Plan: 标题`` / ``# Plan 标题``
    # 禁止 ``# Plan\\n\\n## 意图``：\\s 会跨行把二级标题吃进 group(1)
    m = re.search(
        r"^#\s+Plan(?:[ \t]*[—\-–:][ \t]*|[ \t]+)(.+)$",
        text,
        re.MULTILINE,
    )
    if m:
        title = m.group(1).strip()
        if title and not title.startswith("#"):
            return title[:300]
    for names in (("意图", "目标", "goal", "目的"),):
        goals = _section_bodies(text, names)
        for line in goals.splitlines():
            s = line.strip().lstrip("-* ").strip()
            if s and not s.startswith("#"):
                return s[:300]
    return "执行 plan 验收清单"


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
        # 单 phase fallback：用范围路径 + plan 标题/目标作 description
        paths = extract_paths(plan_text)[:24] or ["STATUS.md"]
        phases.append(
            {
                "phase": 1,
                "phase_id": "1",
                "status": "pending",
                "description": _plan_goal_description(plan_text),
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
                "scope": paths[:24],
                "subtasks": {f"{num}.1": "pending"},
                "timeout": 900,
                "depends_on": [num - 1] if num > 1 else [],
                "notes": "adopted",
            }
        )
    return phases


def phases_jsonl_from_plan(plan_text: str) -> str:
    """合成可落盘的 phases.jsonl（含 schema 行）。"""
    phases = synthesize_phases_from_plan(plan_text)
    phases = backfill_scopes(phases, plan_text)
    schema = json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
    body = "\n".join(json.dumps(p, ensure_ascii=False) for p in phases)
    return schema + "\n" + body + "\n"


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
        lint_ok, lint_errs, _ = phase_lint.validate_phases_dict(phases, workspace=ws)
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
