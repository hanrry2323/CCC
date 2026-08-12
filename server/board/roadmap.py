"""线路图数据模型 — 路线图解析、草案池、里程碑管理。

独立于 plans.py 方案流程：roadmap 是「线路图」层（管未来方向），
plans 是「计划」层（管当前方案），dispatch 是「看板」层（管正在进行时）。

格式约定（docs/projects/<prefix>/roadmap.md）：
    # <项目名> 线路图
    > 项目：<prefix> · 更新：<YYYY-MM-DD>

    ## 草案池
    - <草案条目>（每行一条）

    ## 里程碑
    ### <里程碑标题>
    - 状态：<草案|进行中|已完成>
    - 关联方案：<plan-id>, ...
    - 描述：<描述文本>
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    """解析仓库根目录（绝对路径），避免相对路径 `Path("docs")` 在非 CWD 场景失效。"""
    return Path(__file__).resolve().parents[2]


@dataclass
class Draft:
    """草案条目（尚未转方案、尚未确认）"""

    title: str  # 草案标题（一行）
    project: str = ""  # 所属项目前缀
    created: str = ""  # 创建日期


@dataclass
class Step:
    """里程碑下的执行步骤"""

    title: str  # 步骤标题
    description: str = ""  # 步骤描述
    status: str = "待开始"  # 待开始 | 进行中 | 已完成


@dataclass
class Milestone:
    """里程碑（关联一组方案，有进度）"""

    title: str  # 里程碑标题
    project: str = ""  # 所属项目前缀
    status: str = "草案"  # 草案 | 进行中 | 已完成
    linked_plans: list[str] = field(default_factory=list)  # 关联方案 ID
    description: str = ""  # 描述
    steps: list[Step] = field(default_factory=list)  # 执行步骤


# ── 解析 ──


def parse_roadmap(text: str, project: str = "") -> dict[str, Any]:
    """解析 roadmap.md 文本，返回 {drafts, milestones, updated}。"""
    result: dict[str, Any] = {"drafts": [], "milestones": [], "updated": ""}

    # 提取更新日期
    m = re.search(r"更新：(\d{4}-\d{2}-\d{2})", text)
    if m:
        result["updated"] = m.group(1)

    # 分段
    drafts_section = ""
    milestones_section = ""
    in_drafts = False
    in_milestones = False
    current_ms: dict[str, Any] | None = None

    for line in text.split("\n"):
        if line.strip().startswith("## 草案池"):
            in_drafts = True
            in_milestones = False
            continue
        if line.strip().startswith("## 里程碑"):
            in_drafts = False
            in_milestones = True
            continue
        if in_drafts and line.strip():
            stripped = line.strip()
            if stripped.startswith("- "):
                drafts_section += stripped[2:].strip() + "\n"
        if in_milestones:
            if line.strip().startswith("### "):
                if current_ms is not None:
                    result["milestones"].append(Milestone(**current_ms))
                current_ms = {
                    "title": line.strip()[4:].strip(),
                    "project": project,
                    "status": "草案",
                    "linked_plans": [],
                    "description": "",
                }
            elif current_ms is not None:
                stripped = line.strip()
                if stripped.startswith("- [") and "]" in stripped:
                    # Step 解析：- [状态] 标题（缩进风格，必须在描述续行之前检查）
                    step_match = re.match(r"^-\s*\[([^\]]+)\]\s*(.*)", stripped)
                    if step_match:
                        step_status = step_match.group(1).strip()
                        step_title = step_match.group(2).strip()
                        steps = current_ms.setdefault("steps", [])
                        steps.append(Step(title=step_title, description="", status=step_status))
                elif stripped.startswith("- 状态："):
                    current_ms["status"] = stripped[4:].strip().lstrip("：").strip()
                elif stripped.startswith("- 关联方案："):
                    plans = stripped[6:].strip().lstrip("：").strip()
                    current_ms["linked_plans"] = [p.strip() for p in plans.split(",") if p.strip()]
                elif stripped.startswith("- 描述："):
                    current_ms["description"] = stripped[4:].strip().lstrip("：").strip()
                elif line.startswith("  ") and current_ms["description"] and stripped.strip():
                    # 多行描述续行：以 >=2 空格缩进且非空行 → 追加
                    current_ms["description"] += " " + stripped

    if current_ms is not None:
        result["milestones"].append(Milestone(**current_ms))

    for draft_line in drafts_section.strip().split("\n"):
        if draft_line.strip():
            result["drafts"].append(Draft(title=draft_line.strip(), project=project))

    return result


# ── 查询 ──


def _roadmap_path(project: str) -> Path:
    return _repo_root() / "docs" / "projects" / project / "roadmap.md"


def list_roadmaps() -> list[str]:
    """列出所有有 roadmap.md 的项目前缀。"""
    projects_dir = _repo_root() / "docs" / "projects"
    result = []
    for d in sorted(projects_dir.iterdir()):
        if d.is_dir() and (d / "roadmap.md").is_file():
            result.append(d.name)
    return result


def list_drafts(project: str) -> list[Draft]:
    """列出某项目的草案池。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return []
    data = parse_roadmap(path.read_text(encoding="utf-8"), project=project)
    return data["drafts"]


def list_milestones(project: str) -> list[Milestone]:
    """列出某项目的里程碑。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return []
    data = parse_roadmap(path.read_text(encoding="utf-8"), project=project)
    return data["milestones"]


# ── 写入 ──


def _write_roadmap(project: str, drafts: list[Draft], milestones: list[Milestone]) -> None:
    """序列化写入 roadmap.md（带 fcntl 文件锁，防并发写覆盖）。"""
    from datetime import date

    path = _roadmap_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)

    lock_f = _acquire_roadmap_lock(project)
    try:

        lines = [
            f"# {_project_display_name(project)} 线路图",
            "",
            f"> 项目：{project} · 更新：{date.today().isoformat()}",
            "",
            "## 草案池",
            "",
        ]
        if drafts:
            for d in drafts:
                lines.append(f"- {d.title}")
        else:
            lines.append("无。")
        lines.append("")
        lines.append("## 里程碑")
        lines.append("")
        if milestones:
            for ms in milestones:
                lines.append(f"### {ms.title}")
                lines.append(f"- 状态：{ms.status}")
                if ms.linked_plans:
                    lines.append(f"- 关联方案：{', '.join(ms.linked_plans)}")
                if ms.description:
                    lines.append(f"- 描述：{ms.description}")
                if ms.steps:
                    for step in ms.steps:
                        lines.append(f"  - [{step.status}] {step.title}")
                lines.append("")
        else:
            lines.append("无。")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
    finally:
        _release_roadmap_lock(lock_f, project)


def _project_display_name(project: str) -> str:
    """取项目显示名。"""
    names = {
        "ccc": "CCC",
        "qb": "qb",
        "mx": "medio-0",
        "xy": "xianyu",
        "hp": "HP 知识库",
        "clw": "clwarp",
    }
    return names.get(project, project)


# ── 文件锁（防并发写覆盖）──


def _acquire_roadmap_lock(project: str):
    """获取 roadmap.md 写锁（fcntl 文件锁；无 fcntl 退化为无锁）。"""
    lock_dir = _repo_root() / "docs" / "projects" / project
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / ".roadmap.lock"
    try:
        import fcntl

        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        return f
    except (ImportError, OSError):
        return None


def _release_roadmap_lock(lock_f, project: str) -> None:
    if lock_f is None:
        return
    try:
        import fcntl

        fcntl.flock(lock_f, fcntl.LOCK_UN)
    finally:
        lock_f.close()


# ── 里程碑 CRUD ──


def create_milestone(
    project: str,
    title: str,
    *,
    status: str = "草案",
    linked_plans: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """创建里程碑。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    # 检查重复标题
    for ms in data["milestones"]:
        if ms.title == title:
            return {"error": f"里程碑 {title} 已存在"}

    ms = Milestone(
        title=title,
        project=project,
        status=status,
        linked_plans=linked_plans or [],
        description=description,
    )
    data["milestones"].append(ms)
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "milestone": title}


def update_milestone(
    project: str,
    title: str,
    *,
    status: str | None = None,
    linked_plans: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """更新里程碑字段。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    found = None
    for ms in data["milestones"]:
        if ms.title == title:
            found = ms
            break

    if found is None:
        return {"error": f"里程碑 {title} 不存在"}

    if status is not None:
        found.status = status
    if linked_plans is not None:
        found.linked_plans = linked_plans
    if description is not None:
        found.description = description

    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "milestone": title}


# ── 草案 CRUD ──


def create_draft(project: str, title: str) -> dict[str, Any]:
    """添加草案到草案池。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    # 检查重复
    for d in data["drafts"]:
        if d.title == title:
            return {"error": f"草案 {title} 已存在"}

    data["drafts"].append(Draft(title=title, project=project))
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "draft": title}


def promote_draft(project: str, title: str) -> dict[str, Any]:
    return {"error": f"promote_draft 已弃用，请使用 promote_draft_to_plan 将草案升级为方案"}


def promote_draft_to_plan(project: str, index: int = 0, author: str = "system", tool: str = "ccc") -> dict[str, Any]:
    """从 roadmap.md 草案池取一条草案，创建方案，并从草案池移除该条目。

    Args:
        project: 项目前缀
        index: 草案池中的索引（0=第一条），用于指定取哪条草案
        author: 方案作者
        tool: 方案工具

    Returns:
        {ok, plan: {path, id}, draft_title: ...} or {error}
    """
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    if not data["drafts"]:
        return {"error": "草案池为空"}

    if index < 0 or index >= len(data["drafts"]):
        return {"error": f"草案索引 {index} 越界（共 {len(data['drafts'])} 条）"}

    draft = data["drafts"][index]
    draft_title = draft.title

    # 从草案池移除
    data["drafts"].pop(index)
    _write_roadmap(project, data["drafts"], data["milestones"])

    # 调用 plans.py create_plan 创建方案
    from server.board.plans import create_plan as _create_plan

    repo_root = _repo_root()
    result = _create_plan(
        repo_root,
        project=project,
        title=draft_title,
        content=f"## 目标\n\n从草案「{draft_title}」升级而来。\n\n## 验收标准\n\n- [ ] 待定义\n",
        author=author,
        tool=tool,
    )

    if "error" in result:
        # 回滚：把草案放回池中
        data["drafts"].insert(index, draft)
        _write_roadmap(project, data["drafts"], data["milestones"])
        return {"error": f"方案创建失败: {result['error']}"}

    return {"ok": True, "plan": {"path": result.get("path"), "id": result.get("id")}, "draft_title": draft_title}


# ── 进度计算 ──


def sync_milestone_progress(project: str, plan_rel_path: str) -> dict[str, Any]:
    """当方案进度变更时，自动更新关联里程碑的进度。

    读取里程碑关联的方案，汇总方案进度，更新 roadmap.md 中里程碑的进度行。
    在 plan 状态变更时由 plans.py 的 update_plan / convert_plan 触发。

    Returns:
        {ok, updated_milestones: [title, ...]}  or  {error}
    """
    path = _roadmap_path(project)
    if not path.is_file():
        return {"ok": True, "updated_milestones": []}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    # 提取 plan ID: docs/projects/<prefix>/plans/<NNN>-<slug>.md → <prefix>-plan-<NNN>
    m = re.match(r"docs/projects/([a-z]{2,4})/plans/([0-9]{3})-", plan_rel_path)
    if not m:
        return {"ok": True, "updated_milestones": []}
    plan_id = f"{m.group(1)}-plan-{m.group(2)}"

    updated: list[str] = []
    for ms in data["milestones"]:
        if plan_id not in ms.linked_plans:
            continue
        progress = compute_milestone_progress(project, ms.title)
        if "error" in progress:
            continue
        # 更新里程碑状态
        old_status = ms.status
        ms.status = progress["status"]
        if old_status != ms.status:
            updated.append(ms.title)

    if updated:
        _write_roadmap(project, data["drafts"], data["milestones"])

    return {"ok": True, "updated_milestones": updated}


def compute_milestone_progress(project: str, title: str) -> dict[str, Any]:
    """计算里程碑进度 = 关联方案完成率。

    返回: {total, completed, progress_pct (0-100), status}
    """
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    ms = None
    for m in data["milestones"]:
        if m.title == title:
            ms = m
            break

    if ms is None:
        return {"error": f"里程碑 {title} 不存在"}

    total = len(ms.linked_plans)
    if total == 0:
        return {"total": 0, "completed": 0, "progress_pct": 0, "status": ms.status}

    completed = 0
    plans_dir = _repo_root() / "docs" / "projects" / project / "plans"
    for plan_id in ms.linked_plans:
        # 查找匹配的方案文件
        match = re.match(rf"{project}-plan-(\d+)", plan_id)
        if match:
            num = match.group(1)
            candidates = sorted(plans_dir.glob(f"{num}-*.md"))
            if candidates:
                try:
                    plan_text = candidates[0].read_text(encoding="utf-8")
                    if "状态：已完成" in plan_text:
                        completed += 1
                except OSError:
                    pass

    progress_pct = int(completed / total * 100) if total > 0 else 0

    # 纯计算，不写文件（不写副作用：调用方需要更新时显式调用 update_milestone）
    # 自动推导状态：全部完成=已完成，部分完成=进行中，零完成=草案
    derived_status = ms.status
    if progress_pct == 100:
        derived_status = "已完成"
    elif completed > 0:
        derived_status = "进行中"

    return {
        "total": total,
        "completed": completed,
        "progress_pct": progress_pct,
        "status": derived_status,
    }
