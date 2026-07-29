"""_project_baseline.py — 项目对齐基线快照（v0.41+）

供 Hub「对齐基线」与 product harness 共用。纯程序，不调 LLM。
v0.42.4：快照含 git log / 热路径 / 完整 control policy，收紧 Claude prompt。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from _logger import get_logger

_log = get_logger("project_baseline")


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
    except OSError as e:
        _log.debug("project_baseline top_dirs %s: %s", ws, e)

    profile = ""
    state = ""
    claude = ""
    try:
        pf = ws / ".ccc" / "profile.md"
        if pf.is_file():
            profile = pf.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError as e:
        _log.debug("project_baseline profile read %s: %s", pf, e)
    try:
        sf = ws / ".ccc" / "state.md"
        if sf.is_file():
            state = sf.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError as e:
        _log.debug("project_baseline state read %s: %s", sf, e)
    try:
        for cand in (ws / "CLAUDE.md", ws / "AGENTS.md", ws / ".claude" / "CLAUDE.md"):
            if cand.is_file():
                claude = cand.read_text(encoding="utf-8", errors="replace")[:1500]
                break
    except OSError as e:
        _log.debug("project_baseline claude read %s: %s", ws, e)

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
    except Exception as e:
        _log.debug("project_baseline tips append: %s", e)

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
    """发给 Desktop Agent 的对齐提示：后台深核技术；前台只聊项目方案。"""
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
        "next_product_goal": baseline.get("next_product_goal"),
    }
    profile = (baseline.get("profile_excerpt") or "")[:800]
    state = (baseline.get("state_excerpt") or "")[:800]
    claude = (baseline.get("claude_excerpt") or "")[:800]
    return (
        "【角色】你是 Desktop **架构/规划搭档**（和老板讨论项目往哪走）。"
        "技术核对在后台做；**前台正文禁止运维口吻与技术堆砌**。\n\n"
        "【对用户回复 · 硬】中文白话；先结论后理由；≤短文。"
        "正文只讲：项目是什么、做到哪了、下一步该推什么产品意图、取舍与风险（人话）。"
        "**禁止**正文出现：counts_raw / backlog=N / dirty_kind / ready_for_task / can_dispatch / "
        "pipeline_idle / invent / Engine / OpenCode / `.ccc/` / pytest 路径 / tid / "
        "hub_repair / lens / 文件树 / 提交哈希 / 「队列消费」「扇出」。"
        "板务若已静默清完，最多一句「板面我已理顺」——**不要复述工具过程**。"
        "技术细节若必须留给系统，只放在文末可选的一个 ```ccc-transfer```（未谈妥则不出块）。\n\n"
        "# 任务：对齐项目基线（可选深扫 · 非转意图卡硬门槛）\n"
        "代码权威在 Mac2017 登记仓；M1 **没有**业务源码第二树。\n"
        "程序快照是开场材料；你仍须在作答前 **静默** live 核实（过程勿写入回复）：\n"
        "  hub_board + hub_git（或等价透镜）；冲突以 live 为准。\n"
        "板堵/残卡/孤儿 running：本会话静默 hub_repair(clear_blockers)，"
        "清完再谈产品方向；禁止默认逼卫生 epic；禁止甩锅编排运维。\n"
        "禁止对本机 git/Read 业务树（会串到平台仓）。Hub 断则人话说明「仓况暂时看不清」，勿瞎编。\n\n"
        "## 后台静默核对（内化 · 勿复述字段名）\n"
        "1. 快照 + live：版本、板是否空/堵、是否可开新产品意图、脏是编排噪音还是真业务改动。\n"
        "2. 活跃板已过滤沉底卡；勿把磁盘残留文件数当待办。\n"
        "3. invent 硬关 + 空板 → 编排闲置=正常，不是故障，**不要**当风险恐吓老板。\n"
        "4. 仅编排产物脏 → 不当业务风险；ahead 未推 = 备份提醒，不挡讨论下一步产品。\n"
        "5. 结合 CLAUDE/profile/state 建立「这是什么产品」；VERSION 以快照为准。\n"
        "6. next_product_goal / 已拍板方向优先，勿逆着既定产品路线塞卫生活。\n\n"
        "## 禁止对用户说\n"
        "- 运维检修报告腔（「先跑 board」「counts 不一致」「index lag」）\n"
        "- 建议降控制面 / 关机（除非对方问闲置）\n"
        "- invent / 无人值守自造 / 进队后逐步人批 / 对 CCC orch 下业务卡\n"
        "- 推销多 IDE / 固定角色 / 「请本机 clone」\n"
        "- 把「可开工技术门闩」写成老板必懂的 checklist\n\n"
        "## 输出格式（项目讨论 · 4 段 · 禁技术黑话）\n"
        "### 项目与进度\n"
        "- 这是什么产品（一句定位 + 版本人话）\n"
        "- 现在走到哪一步（产品阶段，不是看板列名）\n"
        "- 是否适合继续谈下一步意图（人话：可以聊 / 先等在飞做完 / 板面我已理顺）\n\n"
        "### 该留意什么\n"
        "- 只写会挡**产品方向或发布**的事；空闲正常就写「当前没有挡事的异常」\n"
        "- 编排卫生/未推送备份最多各一句人话，勿升格成主风险\n\n"
        "### 建议往哪走\n"
        "- 直接给**最佳 1 条产品方向**（对齐已拍板/下一产品目标）+ 一句为何现在做\n"
        "- 可选一句次优带过；**禁止** A/B 菜单逼选；**禁止**把「清卫生」当最佳主业\n\n"
        "### 若要落成意图卡\n"
        "- 给 1 个**白话标题**（≤20 字）说明下一张意图卡该写什么；"
        "或写「先聊清楚：…」——此时不出 ccc-transfer\n"
        "- 未谈妥验收前不要甩 pytest/路径\n\n"
        "请现在输出完整可见答复；禁止只回 No response requested 或空内容；"
        "禁止先输出一长段工具旁白再给报告。\n\n"
        f"程序快照（仅供你内化，禁止逐字段念给用户）：\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False)}\n```\n"
        f"摘要：{baseline.get('summary', '')}\n"
        + (f"\nCLAUDE/AGENTS 摘录：\n{claude}\n" if claude else "")
        + (f"\nprofile 摘录：\n{profile}\n" if profile else "")
        + (f"\nstate 摘录：\n{state}\n" if state else "")
    )
