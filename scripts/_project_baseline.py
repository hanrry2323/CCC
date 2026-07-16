"""_project_baseline.py — 项目对齐基线快照（v0.41）

供 Hub「对齐基线」与 product harness 共用。纯程序，不调 LLM。
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git(ws: Path, *args: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
        return r.returncode, out.strip()
    except Exception as exc:
        return 1, str(exc)


def collect_baseline(workspace: Path, *, project_id: str = "") -> dict[str, Any]:
    ws = Path(workspace).resolve()
    branch_rc, branch = _run_git(ws, "rev-parse", "--abbrev-ref", "HEAD")
    status_rc, status = _run_git(ws, "status", "--porcelain")
    dirty_lines = [ln for ln in status.splitlines() if ln.strip()] if status_rc == 0 else []
    ahead_rc, ahead = _run_git(ws, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    ahead_behind = None
    if ahead_rc == 0 and ahead:
        parts = ahead.split()
        if len(parts) >= 2:
            ahead_behind = {"behind": int(parts[0]), "ahead": int(parts[1])}

    top_dirs = []
    try:
        for p in sorted(ws.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                top_dirs.append(p.name + "/")
            else:
                top_dirs.append(p.name)
            if len(top_dirs) >= 40:
                break
    except OSError:
        pass

    profile = ""
    state = ""
    try:
        pf = ws / ".ccc" / "profile.md"
        if pf.is_file():
            profile = pf.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError:
        pass
    try:
        sf = ws / ".ccc" / "state.md"
        if sf.is_file():
            state = sf.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError:
        pass

    control: dict[str, Any] = {}
    try:
        from _ccc_control import status_dict

        control = status_dict()
    except Exception as exc:
        control = {"error": str(exc)}

    dirty = len(dirty_lines) > 0
    risks: list[str] = []
    if dirty:
        risks.append(f"工作区有 {len(dirty_lines)} 处未提交变更")
    if ahead_behind and ahead_behind.get("ahead", 0) > 0:
        risks.append(f"本地领先远端 {ahead_behind['ahead']} commit（未推送）")
    if ahead_behind and ahead_behind.get("behind", 0) > 0:
        risks.append(f"本地落后远端 {ahead_behind['behind']} commit")
    mode = control.get("mode", "unknown")
    if mode == "disabled":
        risks.append("控制面 disabled：下达任务将自动切到 enabled 并唤醒 Engine")
    elif mode == "ui":
        risks.append("控制面 ui：下达任务将自动切到 enabled 并唤醒 Engine")

    can_dispatch = True  # 产品规则：总可下达；下达即开工
    ready = not dirty  # 脏树仍可下达，但标「建议先清理」

    return {
        "ts": _now_iso(),
        "project_id": project_id,
        "workspace": str(ws),
        "git": {
            "ok": branch_rc == 0,
            "branch": branch if branch_rc == 0 else None,
            "dirty": dirty,
            "dirty_count": len(dirty_lines),
            "dirty_sample": dirty_lines[:30],
            "ahead_behind": ahead_behind,
        },
        "layout": {"top_entries": top_dirs},
        "profile_excerpt": profile,
        "state_excerpt": state,
        "control": {
            "mode": mode,
            "engine_allowed": control.get("engine_allowed"),
        },
        "risks": risks,
        "ready_for_task": ready,
        "can_dispatch": can_dispatch,
        "summary": _format_summary(
            branch if branch_rc == 0 else "?",
            dirty,
            len(dirty_lines),
            mode,
            risks,
            ready,
        ),
    }


def _format_summary(
    branch: str,
    dirty: bool,
    dirty_n: int,
    mode: str,
    risks: list[str],
    ready: bool,
) -> str:
    lines = [
        f"分支 `{branch}` · 控制面 `{mode}` · "
        + ("工作区干净" if not dirty else f"未提交 {dirty_n} 项"),
        ("✅ 基线较干净，可定方案 / 下达任务" if ready else "⚠️ 建议先处理未提交变更，再下达任务（仍可强制下达）"),
    ]
    if risks:
        lines.append("风险：")
        lines.extend(f"- {r}" for r in risks)
    return "\n".join(lines)


def baseline_prompt_for_claude(baseline: dict[str, Any]) -> str:
    """发给 Claude 的对齐提示（结构化上下文 + 任务）。"""
    import json

    compact = {
        "workspace": baseline.get("workspace"),
        "git": baseline.get("git"),
        "layout": baseline.get("layout"),
        "control": baseline.get("control"),
        "risks": baseline.get("risks"),
        "ready_for_task": baseline.get("ready_for_task"),
    }
    return (
        "请根据下列**项目基线快照**对齐当前仓库，用中文输出：\n"
        "1) 项目结构与模块职责（简明）\n"
        "2) git / 控制面风险是否阻碍下达任务\n"
        "3) 若要开发，建议的下一步（方案要点或可执行任务标题）\n"
        "不要编造快照中没有的文件。\n\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n```\n\n"
        f"摘要：\n{baseline.get('summary', '')}\n"
    )
