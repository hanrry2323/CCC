"""board.context — workspace 上下文（废除模块级 ROOT 猴子补丁）。

调用方应 set_workspace(ws) 或向 API 显式传 workspace=。
读取路径一律经 get_workspace() / board_dir()。

F4-1: 显式 per-role context manifest + build_role_context()。
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_ws_var: ContextVar[Path | None] = ContextVar("ccc_board_workspace", default=None)


def set_workspace(ws: Path | str) -> Path:
    """设置当前协程/线程的 workspace（及 CCC_WORKSPACE env）。"""
    path = Path(ws).resolve()
    os.environ["CCC_WORKSPACE"] = str(path)
    _ws_var.set(path)
    return path


def clear_workspace() -> None:
    _ws_var.set(None)


def get_workspace(explicit: Path | str | None = None) -> Path:
    """解析 workspace：显式参数 > ContextVar > CCC_WORKSPACE env > Config 默认。"""
    if explicit is not None:
        return Path(explicit).resolve()
    cur = _ws_var.get()
    if cur is not None:
        return cur
    env = os.environ.get("CCC_WORKSPACE", "").strip()
    if env:
        return Path(env).resolve()
    # 延迟导入，避免 board ↔ _config 循环
    from _config import Config

    return Config().workspace.resolve()


def board_dir(ws: Path | str | None = None) -> Path:
    return get_workspace(ws) / ".ccc" / "board"


def events_dir(ws: Path | str | None = None) -> Path:
    return board_dir(ws) / "events"


def ccc_home() -> Path:
    from _config import Config

    return Config().ccc_home


# ── F4-1: per-role context manifest ─────────────────────────────────

# 每角色声明所需 context 项（字符串 key）。缺项且非 optional → 空串（不抛）。
ROLE_CONTEXT_MANIFEST: dict[str, list[str]] = {
    "product": [
        "skill",
        "baseline",
        "profile",
        "code_ctx",
        "ref_plans",
        "recent_lessons",
        "current_epic",
        "plan_template",
    ],
    "dev": [
        "plan",
        "phases",
        "skill_hints",
        "pytest_failure",
        "current_epic",
    ],
    "reviewer": [
        "skill",
        "plan",
        "verdict",
        "current_epic",
    ],
    # F4-1: 下列角色尚未迁移；manifest 先占位便于审计
    "tester": ["plan", "phases", "current_epic"],
    "kb": ["plan", "current_epic"],
    "ops": ["profile", "current_epic"],
    "regress": ["plan", "recent_lessons", "current_epic"],
}

# 缺文件/缺数据时返回空串，不报错（其余 key 同样兜底为空串）
OPTIONAL_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "skill",
        "baseline",
        "code_ctx",
        "ref_plans",
        "recent_lessons",
        "plan_template",
        "plan",
        "phases",
        "skill_hints",
        "pytest_failure",
        "verdict",
    }
)


def _ccc_home_path() -> Path:
    return ccc_home()


def _load_role_skill(role: str) -> str:
    """注入 skills/ccc-<role>/SKILL.md（对称 product/reviewer）。"""
    home = _ccc_home_path()
    candidates = [
        home / "skills" / f"ccc-{role}" / "SKILL.md",
        Path.home()
        / ".claude"
        / "skills"
        / "ccc-protocol"
        / "skills"
        / f"ccc-{role}"
        / "SKILL.md",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")[:6000]
        except OSError:
            continue
    return ""


def _collect_profile() -> str:
    profile_path = get_workspace() / ".ccc" / "profile.md"
    try:
        if profile_path.is_file():
            return profile_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return "(no profile.md)"


def _collect_baseline() -> str:
    try:
        from _project_baseline import collect_baseline

        bl = collect_baseline(get_workspace())
        return (
            f"{bl.get('summary', '')}\n"
            f"dirty_sample: {bl.get('git', {}).get('dirty_sample', [])[:15]}\n"
        )
    except Exception:
        return ""


def _collect_code_ctx() -> str:
    # 延迟导入：避免 product ↔ context 循环（仅在调用时加载）
    try:
        from board.roles import product as _product

        return _product._get_code_context(get_workspace()) or ""
    except Exception:
        return ""


def _collect_ref_plans(*, include_ref_plans: bool = True) -> str:
    if not include_ref_plans:
        return "（无，重试模式）"
    plan_dir = get_workspace() / ".ccc" / "plans"
    if not plan_dir.is_dir():
        return ""
    chunks: list[str] = []
    try:
        plan_files = sorted(
            plan_dir.glob("*.plan.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for pf in plan_files[:2]:
            try:
                chunks.append(f"--- {pf.name} ---\n{pf.read_text()}\n\n")
            except OSError:
                continue
    except OSError:
        return ""
    return "".join(chunks)


def _collect_recent_lessons() -> str:
    """格式化近期教训；保留 fixed 过滤（stub 已在 get_recent_lessons 内滤）。"""
    try:
        from _lessons import get_recent_lessons

        recent = get_recent_lessons(get_workspace())
        if not recent:
            return ""
        lines = [
            f"- [{lesson.get('task_id', '?')}] phase={lesson.get('phase')}: "
            f"{lesson.get('error', '')[:100]}"
            for lesson in recent[:20]
            if not lesson.get("fixed")
        ]
        return "\n".join(lines)
    except Exception:
        return ""


def _collect_current_epic(task: dict | None) -> str:
    if not task:
        return ""
    try:
        from _utils import sanitize_prompt_input as _sanitize
    except ImportError:

        def _sanitize(x: str) -> str:  # type: ignore[misc]
            return str(x or "")

    tid = str(task.get("id") or "")
    title = _sanitize(str(task.get("title") or ""))
    desc = _sanitize(str(task.get("description") or ""))
    return f"- id: {tid}\n- title: {title}\n- description: {desc}\n"


def _collect_plan_template() -> str:
    ws = get_workspace()
    candidates = [
        ws / "templates" / "plan.plan.md",
        _ccc_home_path() / "templates" / "plan.plan.md",
        Path(__file__).resolve().parents[2] / "templates" / "plan.plan.md",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return ""


def _task_id(task: dict | None) -> str:
    if not task:
        return ""
    return str(task.get("id") or "")


def _collect_plan(task: dict | None) -> str:
    tid = _task_id(task)
    if not tid:
        return ""
    path = get_workspace() / ".ccc" / "plans" / f"{tid}.plan.md"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def _collect_phases(task: dict | None) -> str:
    tid = _task_id(task)
    if not tid:
        return ""
    path = get_workspace() / ".ccc" / "phases" / f"{tid}.phases.json"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def _collect_verdict(task: dict | None) -> str:
    tid = _task_id(task)
    if not tid:
        return ""
    path = get_workspace() / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def _collect_pytest_failure(task: dict | None) -> str:
    tid = _task_id(task)
    if not tid:
        return ""
    path = get_workspace() / ".ccc" / "pids" / f"{tid}.pytest_fail.md"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        pass
    return ""


def _collect_skill_hints(task: dict | None) -> str:
    tid = _task_id(task)
    if not tid:
        return ""
    try:
        from _skills_catalog import format_skill_hints_block
        from _board_store import sanitize_id
        from board.store_ops import list_tasks
    except ImportError:
        return ""
    sid = sanitize_id(tid)
    for col in ("in_progress", "planned", "testing", "backlog", "verified"):
        try:
            tasks = list_tasks(col)
        except Exception:
            continue
        task_row = next((t for t in tasks if t.get("id") == sid), None)
        if not task_row:
            continue
        hints = task_row.get("hints") if isinstance(task_row.get("hints"), dict) else {}
        skills = hints.get("skills") if isinstance(hints.get("skills"), list) else []
        note = hints.get("note") if isinstance(hints.get("note"), str) else ""
        return format_skill_hints_block(skills, note)
    return ""


_COLLECTORS: dict[str, Any] = {
    "profile": lambda **_: _collect_profile(),
    "baseline": lambda **_: _collect_baseline(),
    "code_ctx": lambda **_: _collect_code_ctx(),
    "ref_plans": lambda **kw: _collect_ref_plans(
        include_ref_plans=bool(kw.get("include_ref_plans", True))
    ),
    "recent_lessons": lambda **_: _collect_recent_lessons(),
    "current_epic": lambda **kw: _collect_current_epic(kw.get("task")),
    "plan_template": lambda **_: _collect_plan_template(),
    "plan": lambda **kw: _collect_plan(kw.get("task")),
    "phases": lambda **kw: _collect_phases(kw.get("task")),
    "verdict": lambda **kw: _collect_verdict(kw.get("task")),
    "pytest_failure": lambda **kw: _collect_pytest_failure(kw.get("task")),
    "skill_hints": lambda **kw: _collect_skill_hints(kw.get("task")),
}


def build_role_context(
    role: str,
    task: dict | None = None,
    *,
    include_ref_plans: bool = True,
) -> dict[str, str]:
    """按 ROLE_CONTEXT_MANIFEST 收集该角色所需 context，返回 key→文本。

    缺文件 / 收集失败 → 空串（不抛）。未知 role → 空 dict。
    """
    keys = ROLE_CONTEXT_MANIFEST.get(role) or []
    out: dict[str, str] = {}
    kw = {"task": task, "include_ref_plans": include_ref_plans}
    for key in keys:
        if key == "skill":
            try:
                out[key] = _load_role_skill(role)
            except Exception:
                out[key] = ""
            continue
        collector = _COLLECTORS.get(key)
        if collector is None:
            out[key] = ""
            continue
        try:
            val = collector(**kw)
            out[key] = val if isinstance(val, str) else str(val or "")
        except Exception:
            out[key] = ""
    return out
