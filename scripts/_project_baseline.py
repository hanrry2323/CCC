"""_project_baseline.py — 项目对齐基线快照（v0.41+）

供 Hub「对齐基线」与 product harness 共用。纯程序，不调 LLM。
v0.42.4：快照含 git log / 热路径 / 完整 control policy，收紧 Claude prompt。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    from _utils import now_iso_utc

    return now_iso_utc()


def _run_git(ws: Path, *args: str, timeout: int | None = None) -> tuple[int, str]:
    # 大仓库可 export CCC_BASELINE_GIT_TIMEOUT=60
    if timeout is None:
        try:
            timeout = int(os.environ.get("CCC_BASELINE_GIT_TIMEOUT", "30"))
        except ValueError:
            timeout = 30
        timeout = max(5, min(timeout, 600))
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


def _read_version(ws: Path) -> str | None:
    p = ws / "VERSION"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip().splitlines()[0].strip() or None
    except OSError:
        return None


def _readme_badge_version(ws: Path) -> str | None:
    p = ws / "README.md"
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return None
    m = re.search(r"badge/version-(v?[\d.]+)", text)
    return m.group(1) if m else None


def _hot_paths(ws: Path) -> dict[str, bool]:
    checks = {
        "scripts/board/roles": (ws / "scripts" / "board" / "roles").is_dir(),
        "scripts/engine": (ws / "scripts" / "engine").is_dir(),
        "scripts/ccc-engine.py": (ws / "scripts" / "ccc-engine.py").is_file(),
        "scripts/chat_server": (ws / "scripts" / "chat_server").is_dir(),
        "docs/architecture-core.md": (ws / "docs" / "architecture-core.md").is_file(),
    }
    return checks


def _board_summary(ws: Path) -> dict[str, Any]:
    board = ws / ".ccc" / "board"
    if not board.is_dir():
        return {"present": False}
    counts: dict[str, int] = {}
    for col in (
        "backlog",
        "planned",
        "in_progress",
        "testing",
        "verified",
        "released",
        "abnormal",
    ):
        d = board / col
        n = 0
        if d.is_dir():
            n = sum(1 for p in d.glob("*.jsonl") if p.is_file())
        counts[col] = n
    return {
        "present": True,
        "counts": counts,
        "empty_pipeline": all(
            counts.get(c, 0) == 0
            for c in ("backlog", "planned", "in_progress", "testing", "abnormal")
        ),
    }


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

    log_rc, log_out = _run_git(ws, "log", "-5", "--oneline")
    recent_commits = (
        [ln for ln in log_out.splitlines() if ln.strip()] if log_rc == 0 else []
    )

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
    claude = ""
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
    try:
        for cand in (ws / "CLAUDE.md", ws / "AGENTS.md", ws / ".claude" / "CLAUDE.md"):
            if cand.is_file():
                claude = cand.read_text(encoding="utf-8", errors="replace")[:1500]
                break
    except OSError:
        pass

    control_full: dict[str, Any] = {}
    try:
        from _ccc_control import status_dict

        control_full = status_dict()
    except Exception as exc:
        control_full = {"error": str(exc)}

    policy = control_full.get("policy") if isinstance(control_full.get("policy"), dict) else {}
    mode = control_full.get("mode", "unknown")
    invent_hard = bool(
        control_full.get("invent_hard_disabled")
        or policy.get("invent_hard_disabled")
        or not control_full.get("invent_allowed", True)
    )
    queue_only = bool(
        policy.get("queue_consumer_only")
        or control_full.get("queue_consumer_only")
    )

    version = _read_version(ws)
    readme_ver = _readme_badge_version(ws)
    hot = _hot_paths(ws)
    board = _board_summary(ws)

    dirty = len(dirty_lines) > 0
    risks: list[str] = []
    if dirty:
        risks.append(f"工作区有 {len(dirty_lines)} 处未提交变更")
    if ahead_behind and ahead_behind.get("ahead", 0) > 0:
        risks.append(f"本地领先远端 {ahead_behind['ahead']} commit（未推送）")
    if ahead_behind and ahead_behind.get("behind", 0) > 0:
        risks.append(f"本地落后远端 {ahead_behind['behind']} commit")
    if version and readme_ver and version.lstrip("v") not in readme_ver and readme_ver.lstrip("v") not in version:
        risks.append(f"版本不一致：VERSION={version} vs README badge≈{readme_ver}")
    if mode == "disabled":
        risks.append("控制面 disabled：下达任务将自动切到 enabled 并唤醒 Engine")
    elif mode == "ui":
        risks.append("控制面 ui：下达任务将自动切到 enabled 并唤醒 Engine")
    if board.get("empty_pipeline") and invent_hard and mode == "enabled":
        risks.append(
            "看板管道空 + invent 硬关：Engine 闲置属正常（勿建议降控制面/勿 invent）"
        )

    can_dispatch = True
    ready = not dirty

    control_compact = {
        "mode": mode,
        "engine_allowed": control_full.get("engine_allowed"),
        "invent_hard_disabled": invent_hard,
        "queue_consumer_only": queue_only,
        "invent_allowed": control_full.get("invent_allowed"),
        "auto_inject_tasks": control_full.get("auto_inject_tasks"),
    }

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
            "recent_commits": recent_commits[:5],
        },
        "version": {"VERSION": version, "readme_badge": readme_ver},
        "hot_paths": hot,
        "board": board,
        "layout": {"top_entries": top_dirs},
        "profile_excerpt": profile,
        "state_excerpt": state,
        "claude_excerpt": claude,
        "control": control_compact,
        "risks": risks,
        "ready_for_task": ready,
        "can_dispatch": can_dispatch,
        "summary": _format_summary(
            branch if branch_rc == 0 else "?",
            dirty,
            len(dirty_lines),
            mode,
            invent_hard,
            queue_only,
            risks,
            ready,
            recent_commits[:3],
        ),
    }


def _format_summary(
    branch: str,
    dirty: bool,
    dirty_n: int,
    mode: str,
    invent_hard: bool,
    queue_only: bool,
    risks: list[str],
    ready: bool,
    recent: list[str],
) -> str:
    lines = [
        f"分支 `{branch}` · 控制面 `{mode}`"
        + (" · invent硬关" if invent_hard else "")
        + (" · 仅队列消费" if queue_only else "")
        + " · "
        + ("工作区干净" if not dirty else f"未提交 {dirty_n} 项"),
        (
            "✅ 基线较干净，可定方案；下达需人确认 plan（空板时勿期望 Engine 自跑）"
            if ready
            else "⚠️ 建议先处理未提交变更，再下达任务（仍可强制下达）"
        ),
    ]
    if recent:
        lines.append("近提交：" + " · ".join(recent[:3]))
    if risks:
        lines.append("风险：")
        lines.extend(f"- {r}" for r in risks)
    return "\n".join(lines)


def baseline_prompt_for_claude(baseline: dict[str, Any]) -> str:
    """发给方案 Agent 的对齐提示：功课深度对齐 Cursor，回复可拍板。"""
    git = baseline.get("git") or {}
    compact = {
        "branch": git.get("branch"),
        "dirty": git.get("dirty"),
        "dirty_count": git.get("dirty_count"),
        "dirty_sample": (git.get("dirty_sample") or [])[:12],
        "ahead_behind": git.get("ahead_behind"),
        "recent_commits": git.get("recent_commits") or [],
        "version": baseline.get("version"),
        "hot_paths": baseline.get("hot_paths"),
        "board": baseline.get("board"),
        "top": (baseline.get("layout") or {}).get("top_entries", [])[:20],
        "control": baseline.get("control"),
        "risks": baseline.get("risks") or [],
        "ready_for_task": baseline.get("ready_for_task"),
        "workspace": baseline.get("workspace"),
        "project_id": baseline.get("project_id"),
    }
    profile = (baseline.get("profile_excerpt") or "")[:800]
    state = (baseline.get("state_excerpt") or "")[:800]
    claude = (baseline.get("claude_excerpt") or "")[:800]
    return (
        "【对用户回复】中文白话；先结论后理由；功课深度对齐 Cursor Agent。"
        "禁止复述工具过程、大段代码、裸 JSON；路径仅在拍板必需时点到。"
        "禁止编造未核实事实。用户若要看实现细节，需明确说「工程师模式」。\n\n"
        "# 任务：对齐项目基线（先静默核实，再给人话结论）\n"
        "程序已给出快照，你必须再核实，但回复不要复述 JSON/路径清单。\n\n"
        "## 静默探测（勿写入回复）\n"
        "1. 先读 `CLAUDE.md`（或 `AGENTS.md`）+ `README.md` 建立「这是什么项目」；再读 profile/state；核对 VERSION。\n"
        "2. 跑 `git log -5`，与快照交叉；state 可能滞后。\n"
        "3. 读完整 control：`invent_hard_disabled` / `queue_consumer_only` 等。\n"
        "4. 看板是否空转；空 + invent 关 → Engine 闲置正常。\n"
        "5. dirty 可疑则自行抽样；禁止编造。\n"
        "6. 需要时 Grep/Read 关键入口，确认「定位」不是空话；勿用旧顶层路径当工作区。\n\n"
        "## 禁止对用户说\n"
        "- 禁止建议降控制面 / 关机（除非对方问闲置/省资源）\n"
        "- invent / 自造 backlog / 无人值守全链（红线 12）\n"
        "- 文件树、角色实现路径堆砌\n\n"
        "## 输出格式（4 段 · 有实质，勿灌水）\n"
        "### 现状\n"
        "- 这个项目是干什么的（含版本）\n"
        "- 当前大概卡在哪 / 是否可开工（≤3 短句，要有依据意识）\n\n"
        "### 风险\n"
        "- 只列会挡下达或发布的事；空板可写「闲置属正常」\n\n"
        "### 建议选项\n"
        "- 2～3 个下一步（业务动作 + 为何优先）；最后一行：`最佳：… — <一句理由>`\n\n"
        "### 可下达任务\n"
        "- 适合（人确认后转任务）：1 个标题 ≤20 字\n"
        "- 不适合无人值守：写「先处理：…」或「需人定稿」\n\n"
        "请现在输出完整可见答复；禁止只回 No response requested 或空内容。\n\n"
        f"程序快照：\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```\n"
        f"摘要：{baseline.get('summary', '')}\n"
        + (f"\nCLAUDE/AGENTS 摘录：\n{claude}\n" if claude else "")
        + (f"\nprofile 摘录：\n{profile}\n" if profile else "")
        + (f"\nstate 摘录：\n{state}\n" if state else "")
    )
