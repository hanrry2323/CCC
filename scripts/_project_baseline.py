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
        # 飞轮：空闲时把下一产品意图落到 L1 planned（右栏）；不进 backlog
        if pipeline_idle and (git_clean or dirty_ccc_only):
            try:
                _am.ensure_flywheel_planned_intent(
                    ws,
                    project_id=str(result.get("project_id") or ws.name),
                    pipeline_idle=True,
                )
                decided = _am.load_decided(ws)
            except Exception as _fe:
                _log.debug("flywheel planned materialize: %s", _fe)
        nxt = _am.next_product_goal(decided)
        result["next_product_goal"] = nxt
        if pipeline_idle and (git_clean or dirty_ccc_only) and nxt:
            tip = (
                f"空闲优先产品目标：{nxt.get('text', '')[:80]}"
                + (
                    f"（exit: {str(nxt.get('exit_condition') or '')[:60]}）"
                    if nxt.get("exit_condition")
                    else " · 点「转意图卡」补探针并进代办"
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


def _boss_product_brief(baseline: dict[str, Any]) -> str:
    """给 Agent 内化的**产品白话摘要**——禁止塞原始 JSON / 字段名清单（会教模型用运维腔）。"""
    git = baseline.get("git") or {}
    ver = (baseline.get("version") or {}).get("VERSION") or "未知版本"
    pid = baseline.get("project_id") or "本项目"
    idle = bool(baseline.get("pipeline_idle"))
    inflight = int(baseline.get("inflight_active") or 0)
    if idle and inflight == 0:
        pipe = "当前没有在飞开发，适合谈下一产品意图"
    elif inflight > 0:
        pipe = "还有开发在飞，先等这波做完再开新产品意图"
    else:
        pipe = "管道未完全空闲，谈下一步时先确认是否撞车"

    kind = (git.get("dirty_kind") or baseline.get("dirty_kind") or "").strip()
    ccc_only = git.get("dirty_ccc_only")
    if ccc_only is None:
        ccc_only = baseline.get("dirty_ccc_only")
    if not git.get("dirty"):
        dirt = "仓况干净"
    elif kind == "ccc_hygiene" or ccc_only:
        dirt = "只有编排痕迹未提交，不挡谈产品"
    elif kind == "mixed":
        dirt = "有少量未收好的业务改动，谈意图时留意别撞车；编排痕迹可忽略"
    elif kind == "business":
        dirt = "权威仓有未收好的业务改动，谈意图时留意别撞车"
    else:
        dirt = "仓里有未收尾改动，谈意图时留意"

    ab = git.get("ahead_behind") or {}
    ahead = int(ab.get("ahead") or 0)
    backup = (
        f"本地比远端多 {ahead} 次提交，记得备份推送（不挡谈下一步）"
        if ahead > 0
        else ""
    )

    nxt = baseline.get("next_product_goal") or {}
    nxt_text = (nxt.get("text") or "").strip()
    nxt_exit = (nxt.get("exit_condition") or "").strip()
    nxt_status = (nxt.get("status") or "").strip()
    if nxt_text:
        goal_block = (
            f"已拍板下一产品意图（status={nxt_status or 'unknown'}）：\n"
            f"· 用人话转述给老板（要什么结果），**禁止**把配置路径/测试文件名念出来\n"
            f"· 系统内化原文：{nxt_text[:500]}\n"
        )
        if nxt_exit:
            goal_block += f"· 系统验收口径（勿对老板念命令）：{nxt_exit[:240]}\n"
    else:
        goal_block = "暂无已拍板的下一产品意图；结合项目定位与规划文给人最佳方向。\n"

    lines = [
        f"项目 {pid} · 版本 {ver}",
        f"管道：{pipe}",
        f"仓况：{dirt}",
    ]
    if backup:
        lines.append(backup)
    lines.append(goal_block.rstrip())
    return "\n".join(lines)


def baseline_prompt_for_claude(baseline: dict[str, Any]) -> str:
    """发给 Desktop Agent 的对齐提示：架构师出系列开发计划；禁止单功能闲聊。

    硬教训：raw JSON / 禁词清单会教运维腔；「最佳 1 条」会缩成补单测式单点讨论。
    """
    profile = (baseline.get("profile_excerpt") or "")[:500]
    claude = (baseline.get("claude_excerpt") or "")[:500]
    brief = _boss_product_brief(baseline)
    return (
        "【角色】你是老板的**架构师**（产品架构 + 交付路线）。"
        "主交付物 = **一系列有序开发计划**（阶段路线图），不是围着某一个功能聊天。"
        "老板要的是：从现在走到收口，中间要推哪几步、先后依赖、每步做成什么样子。"
        "老板不是技术员——正文禁止检修报告、路径、测试名、命令。\n\n"
        "【本轮任务】对齐项目基线后，直接给出可拍板的**系列开发计划**。"
        "先结论；**禁止**工具旁白 / 英文过程句。"
        "后台核实静默；板堵最多一句「板面我已理顺」。\n\n"
        "【硬禁】\n"
        "- 禁止把回复缩成「下一个小功能 / 补两条单测 / 改某个配置」的单点讨论\n"
        "- 禁止 A/B 菜单逼选；禁止清卫生当主业\n"
        "- 正文禁止路径、测试名、配置文件、命令、看板数字、提交哈希\n"
        "- 本轮**禁止**输出 ```ccc-transfer```；末段只列整条链的白话标题；"
        "老板要点「转意图卡」才开工\n"
        "- 禁止建议降控制面/关机；闲置不是故障\n\n"
        "【qb 等收口项目 · 内化】北星对齐实盘人确认 + 回测可视化；"
        "计划须从现状排到收口，已拍板意图只是路线上的一站，不是整条计划。\n\n"
        "### 项目与进度\n"
        "- 这是什么产品（一句定位 + 版本人话）\n"
        "- 现在走到哪（产品阶段，人话）\n"
        "- 能否开系列计划（可以排 / 先等在飞做完 / 板面我已理顺）\n\n"
        "### 该留意什么\n"
        "- 只写会挡整条路线或发布的事；没有就写「当前没有挡事的异常」\n"
        "- 编排痕迹 / 未推送备份最多各一句\n\n"
        "### 开发计划（系列 · 本轮主菜）\n"
        "- 给出 **3～7 步有序阶段**（编号 1…N）；每步一句：**产品结果** + 为何此刻\n"
        "- 标明**当前首刀**是哪一步；后续步骤写清依赖（人话）\n"
        "- 已拍板的下一意图必须落进其中一站，但不得独占整份答复\n"
        "- 每步必须是可独立验收的产品意图，不是实现 checklist\n\n"
        "### 若要落成意图卡链\n"
        "- 按上表顺序列出 1/N… 白话标题（每条 ≤20 字，产品结果口吻）\n"
        "- 或写「先聊清楚：…」——此时不出标题列表\n\n"
        "请现在直接输出完整可见答复。\n\n"
        "【内化材料 · 禁止复述字段/原文堆砌】\n"
        f"{brief}\n"
        + (f"\n产品定位摘录：\n{claude}\n" if claude else "")
        + (f"\n档案摘录：\n{profile}\n" if profile else "")
    )
