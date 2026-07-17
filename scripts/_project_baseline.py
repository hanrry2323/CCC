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
    """发给 Claude 的对齐提示：功课做足，回复精简。"""
    import json

    git = baseline.get("git") or {}
    compact = {
        "branch": git.get("branch"),
        "dirty": git.get("dirty"),
        "dirty_count": git.get("dirty_count"),
        "dirty_sample": (git.get("dirty_sample") or [])[:12],
        "ahead_behind": git.get("ahead_behind"),
        "top": (baseline.get("layout") or {}).get("top_entries", [])[:20],
        "control": baseline.get("control"),
        "risks": baseline.get("risks") or [],
        "ready_for_task": baseline.get("ready_for_task"),
        "workspace": baseline.get("workspace"),
        "project_id": baseline.get("project_id"),
    }
    profile = (baseline.get("profile_excerpt") or "")[:800]
    state = (baseline.get("state_excerpt") or "")[:800]
    return (
        "【对用户回复】中文、短句；总字数 ≤280；禁止复述工具过程；禁止大段代码。\n\n"
        "# 任务：对齐项目基线（先探测，再结论）\n"
        "程序已给出快照，但你必须再做一轮核实，不可只复述 JSON。\n\n"
        "## 必修探测\n"
        "1. 读 `.ccc/profile.md`、`.ccc/state.md`、`README.md`/`GOAL.md`/`CLAUDE.md`（存在则读开头）。\n"
        "2. 核对快照里的 dirty_sample：对可疑文件 Read 或 `git diff` 抽样。\n"
        "3. **优先**用 codebase-memory / 代码地图：`list_projects` → `get_architecture` "
        "或 `search_graph` 抓 3～5 个主模块；不可用则 Glob 顶层 + 读入口文件。\n"
        "4. 若有 `.ccc/board/`：扫 backlog/abnormal 是否有卡死任务。\n"
        "5. 禁止编造快照与探测都未出现的路径。\n\n"
        "## 输出格式（严格 4 段）\n"
        "### 现状\n"
        "- 项目一句话\n"
        "- 顶层模块 ≤5 条短句（可带路径）\n\n"
        "### 风险\n"
        "- 只列阻碍下达/发布的项；无则「无明显风险」\n\n"
        "### 建议选项\n"
        "- 2～3 个可执行下一步（动词开头）\n"
        "- 最后一行：`最佳：… — <一句理由>`\n\n"
        "### 可下达任务\n"
        "- 适合开工：给 1 个任务标题（≤20 字）\n"
        "- 不适合：写「先处理：…」\n\n"
        f"程序快照：\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```\n"
        f"摘要：{baseline.get('summary', '')}\n"
        + (f"\nprofile 摘录：\n{profile}\n" if profile else "")
        + (f"\nstate 摘录：\n{state}\n" if state else "")
    )

