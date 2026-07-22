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
        out = r.stdout or ""
        if r.stderr:
            out = f"{out}\n{r.stderr}" if out else r.stderr
        # 勿用 str.strip()：会吃掉 `git status --porcelain` 行首空格（XY 第一列），
        # 导致 ` M .ccc/x` 变成 `M .ccc/x`，dirty 分类把编排产物误判成业务脏。
        return r.returncode, out.rstrip("\n")
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
    """Active board summary — filters ui_hidden + epic split_status=done."""
    from _board_visibility import iter_active_jsonl

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
        counts[col] = len(iter_active_jsonl(d)) if d.is_dir() else 0
    inflight_active = sum(
        counts.get(c, 0)
        for c in ("planned", "in_progress", "testing", "verified", "abnormal")
    )
    # backlog active (pending/running epics) also blocks "empty" sense for invent tip
    empty_pipeline = all(
        counts.get(c, 0) == 0
        for c in ("planned", "in_progress", "testing", "abnormal")
    ) and inflight_active == 0
    return {
        "present": True,
        "counts": counts,
        "inflight_active": inflight_active,
        "empty_pipeline": empty_pipeline,
        "pipeline_idle": empty_pipeline and counts.get("backlog", 0) == 0,
    }


def _porcelain_paths(dirty_lines: list[str]) -> list[str]:
    """从 `git status --porcelain` 行提取路径（支持 rename `->`）。"""
    out: list[str] = []
    for ln in dirty_lines:
        s = (ln or "").rstrip("\n")
        if not s.strip():
            continue
        # porcelain v1：恰好两列 status（可含空格）+ 空格 + path
        if len(s) >= 4 and s[2] == " ":
            body = s[3:]
        else:
            # 兜底：按空白切开，丢掉 status token
            parts = s.split(None, 1)
            body = parts[1] if len(parts) > 1 else ""
        if " -> " in body:
            body = body.split(" -> ", 1)[-1]
        body = body.strip().strip('"')
        if body:
            out.append(body)
    return out


def classify_dirty(dirty_lines: list[str]) -> dict[str, Any]:
    """区分编排产物脏 vs 业务脏，供 Agent 勿把 .ccc 卫生当成业务风险。

    Returns:
      dirty_kind: clean | ccc_hygiene | business | mixed
      dirty_ccc_only: bool
      dirty_ccc_paths / dirty_business_paths: 样本路径
    """
    paths = _porcelain_paths(dirty_lines)
    ccc: list[str] = []
    biz: list[str] = []
    for p in paths:
        norm = p.replace("\\", "/")
        if norm == ".ccc" or norm.startswith(".ccc/"):
            ccc.append(p)
        else:
            biz.append(p)
    if not paths:
        kind = "clean"
    elif not biz:
        kind = "ccc_hygiene"
    elif not ccc:
        kind = "business"
    else:
        kind = "mixed"
    return {
        "dirty_kind": kind,
        "dirty_ccc_only": kind == "ccc_hygiene",
        "dirty_ccc_paths": ccc[:20],
        "dirty_business_paths": biz[:20],
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
    dirty_meta = classify_dirty(dirty_lines)
    dirty_kind = str(dirty_meta.get("dirty_kind") or "clean")
    dirty_ccc_only = bool(dirty_meta.get("dirty_ccc_only"))
    risks: list[str] = []
    if dirty_kind == "ccc_hygiene":
        risks.append(
            f"编排产物未提交（仅 .ccc/，{len(dirty_lines)} 处）："
            "定稿卫生卡落盘即可；非业务改码，不挡讨论与强制下达"
        )
    elif dirty_kind == "business":
        risks.append(
            f"业务工作区有 {len(dirty_lines)} 处未提交变更（含非 .ccc 路径）"
        )
    elif dirty_kind == "mixed":
        risks.append(
            f"工作区混合脏：.ccc {len(dirty_meta.get('dirty_ccc_paths') or [])} + "
            f"业务 {len(dirty_meta.get('dirty_business_paths') or [])}；先分清再下达"
        )
    if ahead_behind and ahead_behind.get("ahead", 0) > 0:
        risks.append(
            f"本地领先远端 {ahead_behind['ahead']} commit（未推送；备份风险，不挡 Engine 消费）"
        )
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
    inflight_active = int(board.get("inflight_active") or 0)
    git_clean = not dirty
    pipeline_idle = bool(board.get("pipeline_idle"))
    # ready：无在飞，且干净或仅 .ccc 卫生脏（卫生脏不挡业务开工）
    ready = inflight_active == 0 and (git_clean or dirty_ccc_only)

    control_compact = {
        "mode": mode,
        "engine_allowed": control_full.get("engine_allowed"),
        "invent_hard_disabled": invent_hard,
        "queue_consumer_only": queue_only,
        "invent_allowed": control_full.get("invent_allowed"),
        "auto_inject_tasks": control_full.get("auto_inject_tasks"),
    }

    result: dict[str, Any] = {
        "ts": _now_iso(),
        "project_id": project_id,
        "workspace": str(ws),
        "git": {
            "ok": branch_rc == 0,
            "branch": branch if branch_rc == 0 else None,
            "dirty": dirty,
            "dirty_count": len(dirty_lines),
            "dirty_sample": dirty_lines[:30],
            "dirty_kind": dirty_kind,
            "dirty_ccc_only": dirty_ccc_only,
            "dirty_ccc_paths": dirty_meta.get("dirty_ccc_paths") or [],
            "dirty_business_paths": dirty_meta.get("dirty_business_paths") or [],
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
        "risks": list(risks),
        "git_clean": git_clean,
        "pipeline_idle": pipeline_idle,
        "inflight_active": inflight_active,
        "ready_for_task": ready,
        "can_dispatch": can_dispatch,
        "dirty_kind": dirty_kind,
        "dirty_ccc_only": dirty_ccc_only,
        "next_product_goal": None,
        "summary": _format_summary(
            branch if branch_rc == 0 else "?",
            dirty,
            len(dirty_lines),
            dirty_kind,
            mode,
            invent_hard,
            queue_only,
            risks,
            ready,
            recent_commits[:3],
        ),
    }

    # LPSN · N: idle → suggest unfinished L1 product goal
    try:
        import sys as _sys

        _scripts = Path(__file__).resolve().parent
        if str(_scripts) not in _sys.path:
            _sys.path.insert(0, str(_scripts))
        from chat_server.services import agent_mind as _am

        decided = _am.load_decided(ws)
        nxt = _am.next_product_goal(decided)
        result["next_product_goal"] = nxt
        if pipeline_idle and (git_clean or dirty_ccc_only) and nxt:
            tip = (
                f"空闲优先产品目标：{nxt.get('text', '')[:80]}"
                + (
                    f"（exit: {str(nxt.get('exit_condition') or '')[:60]}）"
                    if nxt.get("exit_condition")
                    else ""
                )
            )
            result["risks"] = list(result.get("risks") or []) + [tip]
            result["summary"] = (result.get("summary") or "") + "\n" + tip
    except Exception:
        pass

    return result


def _format_summary(
    branch: str,
    dirty: bool,
    dirty_n: int,
    dirty_kind: str,
    mode: str,
    invent_hard: bool,
    queue_only: bool,
    risks: list[str],
    ready: bool,
    recent: list[str],
) -> str:
    dirty_label = "工作区干净"
    if dirty:
        if dirty_kind == "ccc_hygiene":
            dirty_label = f"仅 .ccc 卫生脏 {dirty_n} 项"
        elif dirty_kind == "business":
            dirty_label = f"业务未提交 {dirty_n} 项"
        elif dirty_kind == "mixed":
            dirty_label = f"混合脏 {dirty_n} 项"
        else:
            dirty_label = f"未提交 {dirty_n} 项"
    if ready and dirty_kind == "ccc_hygiene":
        gate = (
            "✅ 可开工（仅编排产物未提交）：优先定稿卫生卡；业务 epic 也可强制下达"
        )
    elif ready:
        gate = "✅ 基线较干净，可定方案；下达需人确认 plan（空板时勿期望 Engine 自跑）"
    elif dirty_kind in ("business", "mixed"):
        gate = "⚠️ 有业务未提交变更，建议先核账再下达（仍可强制下达）"
    else:
        gate = "⚠️ 建议先处理未提交变更，再下达任务（仍可强制下达）"
    lines = [
        f"分支 `{branch}` · 控制面 `{mode}`"
        + (" · invent硬关" if invent_hard else "")
        + (" · 仅队列消费" if queue_only else "")
        + " · "
        + dirty_label,
        gate,
    ]
    if recent:
        lines.append("近提交：" + " · ".join(recent[:3]))
    if risks:
        lines.append("风险：")
        lines.extend(f"- {r}" for r in risks)
    return "\n".join(lines)


def baseline_prompt_for_claude(baseline: dict[str, Any]) -> str:
    """发给 Desktop 方案 Agent 的对齐提示：功课要深，回复可拍板。"""
    git = baseline.get("git") or {}
    compact = {
        "branch": git.get("branch"),
        "dirty": git.get("dirty"),
        "dirty_count": git.get("dirty_count"),
        "dirty_kind": git.get("dirty_kind") or baseline.get("dirty_kind"),
        "dirty_ccc_only": git.get("dirty_ccc_only")
        if git.get("dirty_ccc_only") is not None
        else baseline.get("dirty_ccc_only"),
        "dirty_sample": (git.get("dirty_sample") or [])[:12],
        "dirty_ccc_paths": (git.get("dirty_ccc_paths") or [])[:12],
        "dirty_business_paths": (git.get("dirty_business_paths") or [])[:12],
        "ahead_behind": git.get("ahead_behind"),
        "recent_commits": git.get("recent_commits") or [],
        "version": baseline.get("version"),
        "hot_paths": baseline.get("hot_paths"),
        "board": baseline.get("board"),
        "top": (baseline.get("layout") or {}).get("top_entries", [])[:20],
        "control": baseline.get("control"),
        "risks": baseline.get("risks") or [],
        "ready_for_task": baseline.get("ready_for_task"),
        "can_dispatch": baseline.get("can_dispatch"),
        "git_clean": baseline.get("git_clean"),
        "pipeline_idle": baseline.get("pipeline_idle"),
        "inflight_active": baseline.get("inflight_active"),
        "workspace": baseline.get("workspace"),
        "project_id": baseline.get("project_id"),
    }
    profile = (baseline.get("profile_excerpt") or "")[:800]
    state = (baseline.get("state_excerpt") or "")[:800]
    claude = (baseline.get("claude_excerpt") or "")[:800]
    return (
        "【对用户回复】中文白话；先结论后理由。"
        "你是 Desktop 对话面产品搭档（不是 Hub 聊天、不是 Engine 角色）。"
        "禁止复述工具过程、大段代码、裸 JSON；路径仅在拍板必需时点到。"
        "禁止编造未核实事实。业务改码请定稿转任务；工程师模式仅平台仓 ccc。\n\n"
        "# 任务：对齐项目基线（Hub 快照开场 + live board）\n"
        "代码权威在 Mac2017 登记仓；GitHub 只是备份；M1 **没有**业务源码第二树。\n"
        "程序已给出快照与摘录作**开场材料**；"
        "你仍须在作答前用 Bash 至少跑一次 live 核实：\n"
        "  `python3 scripts/ccc-hub-lens.py board <project_id>`\n"
        "  `python3 scripts/ccc-hub-lens.py git <project_id>`\n"
        "（冲突以 live 为准；禁止跳过工具只凭注入 JSON 交差——用户要看见过程轨）。\n"
        "之后问「在飞/看板/文件」须再经透镜 live，勿用本轮记忆否定更新看板。\n"
        "禁止对本机跑 git / Read 业务树再核实（会串到 CCC 平台仓）。\n"
        "快照不足就直说缺什么；Hub 断则明说不可达，勿瞎编。\n\n"
        "## 静默（勿写入回复）\n"
        "1. 读快照：version / board / control / risks / recent_commits / dirty_kind；"
        "同时报 git_clean、pipeline_idle、inflight_active、ready_for_task、can_dispatch"
        "（ready≠仅 git 净；活跃计数已过滤 ui_hidden 与 done epic）。\n"
        "2. 优先读注入的 live board（as_of + inflight）；禁止把 raw backlog 文件数当待办挑卡；"
        "僵尸 done+hidden → 引导清账而非「挑一张转」；**state.md 看板表可能滞后，以 live board 为准**。\n"
        "3. 验收命令是 Engine 关门条件，不是散文。看板卫生类建议 executor=python + scope 仅 .ccc/。\n"
        "4. 结合 CLAUDE/profile/state 摘录建立「这是什么项目」；VERSION 以快照 `version.VERSION` 为准"
        "（摘录里旧版本号勿覆盖）。\n"
        "5. 完整理解 control：`invent_hard_disabled` / `queue_consumer_only` 等。\n"
        "6. 看板是否空转；空 + invent 关 → Engine 闲置正常。\n"
        "7. **dirty 分类（强制）**：看 `dirty_kind` / `dirty_sample` 路径前缀——\n"
        "   - `ccc_hygiene`（路径全是 `.ccc/`）：必须下结论「仅编排产物未提交」，"
        "**禁止**说「可能是业务改动」；`ready_for_task` 可为 true；"
        "「可下达任务」给卫生标题（≤20字），并说明业务 epic 也可强制下达。\n"
        "   - `business` / `mixed`：才强调业务核账；提醒「业务改码请定稿转任务」。\n"
        "   - `ahead` 未推送 = 备份风险，**不**等于不能开工。\n"
        "8. profile/state 与 live 冲突时，点明「摘录滞后」，以 live + VERSION 快照为准。\n\n"
        "## 禁止对用户说\n"
        "- 禁止建议降控制面 / 关机（除非对方问闲置/省资源）\n"
        "- invent / 自造 backlog / 无人值守 invent（红线 12）\n"
        "- 进队后逐步人批；对 CCC orch 下业务 epic\n"
        "- 推销多 IDE / 让用户先选固定角色\n"
        "- 文件树、角色实现路径堆砌\n"
        "- 「请先在本机 clone / 绑定工作区才能对齐」\n"
        "- 在 dirty_sample 已全是 `.ccc/` 时仍说「说不清是不是业务改动」\n"
        "- 用「暂不建议下达」搪塞「可下达任务」段（必须给 1 个 ≤20 字标题）\n\n"
        "## 输出格式（4 段 · 有实质，勿灌水）\n"
        "### 现状\n"
        "- 这个项目是干什么的（含版本）\n"
        "- 当前大概卡在哪 / 是否可开工（≤3 短句；写明 dirty_kind 与 ready/can_dispatch）\n\n"
        "### 风险\n"
        "- 只列会挡下达或发布的事；空板可写「闲置属正常」；"
        "仅 .ccc 脏写成卫生项，勿升格成业务风险\n\n"
        "### 建议选项\n"
        "- 2～3 个下一步（业务动作 + 为何优先）；最后一行：`最佳：… — <一句理由>`\n"
        "- 直接推荐最佳项，勿把核账当成无尽选择题\n\n"
        "### 可下达任务\n"
        "- 适合（人确认后转任务）：**必须** 1 个标题 ≤20 字"
        "（`ccc_hygiene` 例：提交清场残留编排产物）\n"
        "- 不适合无人值守：写「先处理：…」或「需人定稿」"
        "（不得以此段代替上一行必给标题）\n\n"
        "请现在输出完整可见答复；禁止只回 No response requested 或空内容。\n\n"
        f"程序快照：\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```\n"
        f"摘要：{baseline.get('summary', '')}\n"
        + (f"\nCLAUDE/AGENTS 摘录：\n{claude}\n" if claude else "")
        + (f"\nprofile 摘录：\n{profile}\n" if profile else "")
        + (f"\nstate 摘录：\n{state}\n" if state else "")
    )
