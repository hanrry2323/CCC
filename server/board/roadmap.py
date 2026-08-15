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
    source: str = ""  # 来源（老板意图/Loop巡查/外部反馈；2026-08-14 补齐 rebuild-design 字段）


@dataclass
class Subproject:
    """子项目（里程碑的分解单元，1:1 对应一个方案）。

    CCC 流程架构改造（2026-08-16 决策）：覆盖 ccc-plan-027「无独立中间层」定义——
    里程碑下结构化解耦为子项目，激活时 1:1 生成方案，实现「里程碑→子项目→计划逐步投入→开发卡」。
    未激活子项目只停留在 roadmap.md，不占开发资源。
    """

    id: str = ""  # 子项目编号（如 2.1）
    title: str = ""  # 子项目标题
    status: str = "未启动"  # 未启动 | 计划中 | 已完成
    plan_id: str = ""  # 关联方案 ID（激活后写入），无则空


@dataclass
class Milestone:
    """里程碑（关联一组方案，有进度）。

    ccc-plan-027：Step 概念并入方案内「功能卡」段，里程碑下不再有 steps。
    2026-08-16 流程架构改造：新增 subprojects 子项目层（结构化分解单元），兼容旧格式（无子项目时退回 linked_plans 聚合）。
    """

    title: str  # 里程碑标题
    project: str = ""  # 所属项目前缀
    status: str = "待启动"  # 待启动 | 进行中 | 已完成（草案→待启动，2026-08-14 对齐 rebuild-design）
    linked_plans: list[str] = field(default_factory=list)  # 关联方案 ID
    description: str = ""  # 描述
    target_date: str = ""  # 目标日期（可选，YYYY-MM-DD；2026-08-14 补齐 rebuild-design 字段）
    timeline: str = ""  # 时间线标注（如日期区间 2026-08-07~08-09；2026-08-14 里程碑模型增强）
    version: str = ""  # 版本号（如 v0.9.0；2026-08-14 里程碑模型增强）
    subprojects: list[Subproject] = field(default_factory=list)  # 子项目列表（2026-08-16 新增）


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
    in_subprojects = False  # 子项目段收集状态（2026-08-16）
    current_ms: dict[str, Any] | None = None

    for line in text.split("\n"):
        if line.strip().startswith("## 草案池"):
            in_drafts = True
            in_milestones = False
            in_subprojects = False
            continue
        if line.strip().startswith("## 里程碑"):
            in_drafts = False
            in_milestones = True
            in_subprojects = False
            continue
        if in_drafts and line.strip():
            stripped = line.strip()
            if stripped.startswith("- "):
                drafts_section += stripped[2:].strip() + "\n"
        if in_milestones:
            if line.strip().startswith("### "):
                if current_ms is not None:
                    current_ms["subprojects"] = [
                        sp if isinstance(sp, Subproject) else Subproject(**sp)
                        for sp in current_ms.get("subprojects", [])
                    ]
                    result["milestones"].append(Milestone(**current_ms))
                current_ms = {
                    "title": line.strip()[4:].strip(),
                    "project": project,
                    "status": "待启动",
                    "linked_plans": [],
                    "description": "",
                    "target_date": "",
                    "timeline": "",
                    "version": "",
                    "subprojects": [],
                }
                in_subprojects = False
            elif current_ms is not None:
                stripped = line.strip()
                # 子项目段收集：缩进的 "- " 子项目行（- <id> <title> · 状态：<s> · 方案：<p>）
                if in_subprojects:
                    if line.startswith("  ") and stripped.startswith("- "):
                        current_ms["subprojects"].append(_parse_subproject_line(stripped[2:].strip()))
                        continue
                    in_subprojects = False  # 非缩进子项目行 → 子项目段结束，落到字段解析
                if stripped.startswith("- 子项目："):
                    in_subprojects = True
                    continue
                if stripped.startswith("- 状态："):
                    current_ms["status"] = stripped[4:].strip().lstrip("：").strip()
                elif stripped.startswith("- 关联方案："):
                    plans = stripped[6:].strip().lstrip("：").strip()
                    current_ms["linked_plans"] = [p.strip() for p in plans.split(",") if p.strip()]
                elif stripped.startswith("- 描述："):
                    current_ms["description"] = stripped[4:].strip().lstrip("：").strip()
                elif stripped.startswith("- 目标日期："):
                    current_ms["target_date"] = stripped[7:].strip().lstrip("：").strip()
                elif stripped.startswith("- 时间线："):
                    current_ms["timeline"] = stripped[6:].strip().lstrip("：").strip()
                elif stripped.startswith("- 版本："):
                    current_ms["version"] = stripped[5:].strip().lstrip("：").strip()
                elif line.startswith("  ") and current_ms["description"] and stripped.strip():
                    # 多行描述续行：以 >=2 空格缩进且非空行 → 追加
                    current_ms["description"] += " " + stripped

    if current_ms is not None:
        current_ms["subprojects"] = [
            sp if isinstance(sp, Subproject) else Subproject(**sp)
            for sp in current_ms.get("subprojects", [])
        ]
        result["milestones"].append(Milestone(**current_ms))

    for draft_line in drafts_section.strip().split("\n"):
        raw = draft_line.strip()
        if not raw:
            continue
        # 增强格式软解析：`[来源] 标题 · 日期：YYYY-MM-DD`（2026-08-14 补来源标记）
        source = ""
        created = ""
        _line = raw
        _m = re.match(r"^\[([^\]]+)\]\s*(.+)$", _line)
        if _m:
            source = _m.group(1).strip()
            _line = _m.group(2).strip()
        _m_date = re.search(r"·\s*日期[:：]\s*(\d{4}-\d{2}-\d{2})", _line)
        if _m_date:
            created = _m_date.group(1)
            _line = _line[: _m_date.start()].rstrip(" ·").strip()
        if not _line:
            _line = raw
        result["drafts"].append(
            Draft(title=_line.strip(), project=project, created=created, source=source)
        )

    return result


def _parse_subproject_line(raw: str) -> dict[str, Any]:
    """解析子项目行：`<id> <title> · 状态：<s> · 方案：<p>`（2026-08-16）。

    例：`2.1 pipeline 源码回灌 SSOT · 状态：计划中 · 方案：hp-plan-008`
    状态/方案段可选；缺省状态=未启动，缺省方案=空。用「替换删除已匹配段」避免截断后续段。
    """
    status = "未启动"
    plan_id = ""
    body = raw
    _m_status = re.search(r"·\s*状态[：:]\s*([^·]+)", body)
    if _m_status:
        status = _m_status.group(1).strip()
        body = body.replace(_m_status.group(0), "", 1)
    _m_plan = re.search(r"·\s*方案[：:]\s*([^·]+)", body)
    if _m_plan:
        plan_id = _m_plan.group(1).strip()
        body = body.replace(_m_plan.group(0), "", 1)
    parts = body.strip(" ·").split(" ", 1)
    return {
        "id": parts[0].strip(),
        "title": parts[1].strip() if len(parts) > 1 else "",
        "status": status,
        "plan_id": plan_id,
    }


# ── 查询 ──


def active_linked_plans(project: str, plan_ids: list[str]) -> list[str]:
    """过滤里程碑关联方案里的作废/已覆盖方案（展示用；roadmap.md 保留关联历史）。

    人审调整动作统一化（2026-08-14）：作废方案从总数剔除，列表展示同步过滤。
    """
    if not plan_ids:
        return []
    plans_dir = _repo_root() / "docs" / "projects" / project / "plans"
    active: list[str] = []
    for pid in plan_ids:
        m = re.match(rf"{re.escape(project)}-plan-(\d+)", pid)
        if not m:
            active.append(pid)
            continue
        candidates = sorted(plans_dir.glob(f"{m.group(1)}-*.md"))
        if not candidates:
            active.append(pid)
            continue
        try:
            text = candidates[0].read_text(encoding="utf-8", errors="replace")
        except OSError:
            active.append(pid)
            continue
        sm = re.search(r"状态：([^\s·]+)", text)
        st = sm.group(1) if sm else ""
        if st not in ("作废", "已覆盖"):
            active.append(pid)
    return active


def _roadmap_path(project: str) -> Path:
    return _repo_root() / "docs" / "projects" / project / "roadmap.md"


def list_roadmaps() -> list[str]:
    """列出所有有 roadmap.md 的业务项目前缀（跳过 platform 类项目）。"""
    from server.board.registry import platform_prefixes

    _platform = platform_prefixes()
    projects_dir = _repo_root() / "docs" / "projects"
    result = []
    for d in sorted(projects_dir.iterdir()):
        if d.is_dir() and (d / "roadmap.md").is_file():
            if d.name not in _platform:
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
                _line = f"- {d.title}"
                if d.source:
                    _line = f"- [{d.source}] {d.title}"
                if d.created:
                    _line += f" · 日期：{d.created}"
                lines.append(_line)
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
                if ms.target_date:
                    lines.append(f"- 目标日期：{ms.target_date}")
                if ms.timeline:
                    lines.append(f"- 时间线：{ms.timeline}")
                if ms.version:
                    lines.append(f"- 版本：{ms.version}")
                if ms.subprojects:
                    lines.append("- 子项目：")
                    for sp in ms.subprojects:
                        _line = f"  - {sp.id} {sp.title}"
                        if sp.status and sp.status != "未启动":
                            _line += f" · 状态：{sp.status}"
                        if sp.plan_id:
                            _line += f" · 方案：{sp.plan_id}"
                        lines.append(_line)
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
    status: str = "待启动",
    linked_plans: list[str] | None = None,
    description: str = "",
    target_date: str = "",
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
        target_date=target_date,
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
    target_date: str | None = None,
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
    if target_date is not None:
        found.target_date = target_date

    # P1#13：字段变更后按实际完成率重算状态（此前追加 linked_plans 后状态永久失真，
    # 直到下一次 update_plan 触发 sync 才有巡检窗口期）
    computed = compute_milestone_progress(project, title)
    if isinstance(computed, dict) and not computed.get("error") and computed.get("completed", 0) > 0:
        if computed["status"] != found.status:
            found.status = computed["status"]

    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "milestone": title}


def activate_subproject(
    project: str,
    milestone_title: str,
    subproject_id: str,
    plan_id: str,
) -> dict[str, Any]:
    """激活子项目（2026-08-16）：设置 status=计划中 + 关联方案 ID，并同步里程碑 linked_plans。

    子项目激活 = 人审节点① 细化——老板逐个指定哪个子项目转入计划，1:1 生成方案后调用。
    """
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}
    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)
    for ms in data["milestones"]:
        if ms.title == milestone_title:
            for sp in ms.subprojects:
                if sp.id == subproject_id:
                    sp.status = "计划中"
                    sp.plan_id = plan_id
                    if plan_id not in ms.linked_plans:
                        ms.linked_plans.append(plan_id)
                    _write_roadmap(project, data["drafts"], data["milestones"])
                    return {"ok": True, "subproject": subproject_id, "plan": plan_id}
            return {"error": f"子项目 {subproject_id} 不在里程碑 {milestone_title} 中"}
    return {"error": f"里程碑 {milestone_title} 不存在"}


def delete_milestone(project: str, title: str) -> dict[str, Any]:
    """删除里程碑（仅当无关联方案时允许；有方案则拒绝，需先解绑）。

    人审调整动作统一化（2026-08-14）：补齐 rebuild-design 的 DELETE 端点。
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

    if ms.linked_plans:
        return {"error": f"里程碑 {title} 仍有 {len(ms.linked_plans)} 个关联方案，先解绑再删除"}

    data["milestones"] = [m for m in data["milestones"] if m.title != title]
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "removed": title}


# ── 方案↔里程碑双向关联（ccc-plan-027 缝隙1）──


def link_plan_to_milestone(
    project: str,
    plan_id: str,
    milestone_title: str | None,
    prev_milestone_title: str | None = None,
) -> dict[str, Any]:
    """维护 roadmap.md 的 linked_plans 派生索引（方案头「里程碑」字段是主入口）。

    - milestone_title 非空：把 plan_id 加入目标里程碑 linked_plans；
    - prev_milestone_title：从旧里程碑移除该方案（改里程碑场景）；
    - milestone_title 为 None/空串：从所有里程碑移除该方案（清除关联）。

    Returns:
        {ok, updated: bool}
    """
    path = _roadmap_path(project)
    if not path.is_file():
        return {"ok": True, "updated": False}
    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    changed = False
    for ms in data["milestones"]:
        linked = list(ms.linked_plans)
        if prev_milestone_title and ms.title == prev_milestone_title and plan_id in linked:
            linked.remove(plan_id)
        if not milestone_title and plan_id in linked:
            linked.remove(plan_id)
        if milestone_title and ms.title == milestone_title and plan_id not in linked:
            linked.append(plan_id)
        if linked != ms.linked_plans:
            ms.linked_plans = linked
            changed = True

    if changed:
        _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "updated": changed}


# ── 草案 CRUD ──


def create_draft(
    project: str, title: str, *, source: str = "", created: str = ""
) -> dict[str, Any]:
    """添加草案到草案池（2026-08-14 补来源标记）。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    # 检查重复
    for d in data["drafts"]:
        if d.title == title:
            return {"error": f"草案 {title} 已存在"}

    if not created:
        from datetime import date

        created = date.today().isoformat()
    data["drafts"].append(Draft(title=title, project=project, created=created, source=source))
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "draft": title}


def edit_draft(project: str, index: int, new_title: str) -> dict[str, Any]:
    """修改草案条目文字（人审调整动作统一化：节点① 改草案后再确认）。"""
    path = _roadmap_path(project)
    if not path.is_file():
        return {"error": f"项目 {project} 尚无 roadmap.md"}

    new_title = new_title.strip()
    if not new_title:
        return {"error": "草案标题不能为空"}

    text = path.read_text(encoding="utf-8")
    data = parse_roadmap(text, project=project)

    if not data["drafts"]:
        return {"error": "草案池为空"}
    if index < 0 or index >= len(data["drafts"]):
        return {"error": f"草案索引 {index} 越界（共 {len(data['drafts'])} 条）"}

    # 查重（改后与其它草案重名）
    for i, d in enumerate(data["drafts"]):
        if i != index and d.title == new_title:
            return {"error": f"草案 {new_title} 已存在"}

    data["drafts"][index].title = new_title
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "draft": new_title, "index": index}


def remove_draft(project: str, index: int) -> dict[str, Any]:
    """取消一条草案：直接移除条目（人审调整动作统一化：节点① 取消=不再执行）。

    与 promote_draft_to_plan（pop 移除）一致；git 历史仍可追溯。
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

    removed = data["drafts"].pop(index)
    _write_roadmap(project, data["drafts"], data["milestones"])
    return {"ok": True, "removed": removed.title}


def promote_draft(project: str, title: str) -> dict[str, Any]:
    return {"error": "promote_draft 已弃用，请使用 promote_draft_to_plan 将草案升级为方案"}


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

    # 调用 plans.py create_plan 创建方案（节点① 老板确认 → approved=True 打批准标签）
    from server.board.plans import create_plan as _create_plan

    repo_root = _repo_root()
    result = _create_plan(
        repo_root,
        project=project,
        title=draft_title,
        content=f"## 目标\n\n从草案「{draft_title}」升级而来。\n\n## 验收标准\n\n- [ ] 待定义\n",
        author=author,
        tool=tool,
        approved=True,
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
        # 子项目模式的里程碑也纳入同步（方案挂子项目，可能不在 linked_plans）
        if plan_id not in ms.linked_plans and not ms.subprojects:
            continue
        # 2026-08-16 机审修复：方案状态变更 → 同步子项目状态（已完成/计划中/未启动）
        if ms.subprojects:
            _sync_subproject_statuses(project, ms)
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


def _sync_subproject_statuses(project: str, ms: Any) -> None:
    """根据关联方案状态同步子项目状态（2026-08-16 机审修复：子项目进度有完成通路）。

    已完成 → 已完成；作废/已覆盖 → 未启动（剔除）；其余 → 计划中（有方案）。
    未激活子项目（无 plan_id）→ 未启动。
    """
    plans_dir = _repo_root() / "docs" / "projects" / project / "plans"
    for sp in ms.subprojects:
        if not sp.plan_id:
            sp.status = "未启动"
            continue
        match = re.match(rf"{project}-plan-(\d+)", sp.plan_id)
        if not match:
            continue
        candidates = sorted(plans_dir.glob(f"{match.group(1)}-*.md"))
        if not candidates:
            continue
        try:
            plan_text = candidates[0].read_text(encoding="utf-8")
            status_m = re.search(r"状态：([^\s·]+)", plan_text)
            plan_status = status_m.group(1) if status_m else ""
        except OSError:
            continue
        if plan_status == "已完成":
            sp.status = "已完成"
        elif plan_status in ("作废", "已覆盖"):
            sp.status = "未启动"
        else:
            sp.status = "计划中"


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

    # 有子项目时按子项目聚合（2026-08-16 决策），否则退回关联方案聚合（兼容旧格式里程碑）
    # 2026-08-16 机审修复：子项目分支读「关联方案完成率」（文档承诺语义），
    # 而非只数 sp.status——否则没有任何代码把子项目置「已完成」，进度永久卡住。
    if ms.subprojects:
        plans_dir = _repo_root() / "docs" / "projects" / project / "plans"
        total = len(ms.subprojects)
        completed = 0
        for sp in ms.subprojects:
            if not sp.plan_id:
                continue
            match = re.match(rf"{project}-plan-(\d+)", sp.plan_id)
            if not match:
                continue
            candidates = sorted(plans_dir.glob(f"{match.group(1)}-*.md"))
            if not candidates:
                continue
            try:
                plan_text = candidates[0].read_text(encoding="utf-8")
                status_m = re.search(r"状态：([^\s·]+)", plan_text)
                plan_status = status_m.group(1) if status_m else ""
                if plan_status in ("作废", "已覆盖"):
                    total -= 1
                    continue
                if plan_status == "已完成":
                    completed += 1
            except OSError:
                pass
    else:
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
                        # P1#14：读头部状态字段（此前全文子串匹配「状态：已完成」会误计）；
                        # 方案头是多 key 一行（> 项目：… · 状态：…），取全文首个「状态：」值 = 头部
                        # 终态非完成方案（作废/已覆盖）剔除出 total
                        status_m = re.search(r"状态：([^\s·]+)", plan_text)
                        plan_status = status_m.group(1) if status_m else ""
                        if plan_status in ("作废", "已覆盖"):
                            total -= 1
                            continue
                        if plan_status == "已完成":
                            completed += 1
                    except OSError:
                        pass

    progress_pct = int(completed / total * 100) if total > 0 else 0

    # 纯计算，不写文件（不写副作用：调用方需要更新时显式调用 update_milestone）
    # 自动推导状态：全部完成=已完成，部分完成=进行中，零完成=待启动
    # 全作废边界（2026-08-14）：原有关联方案但全部作废/已覆盖（total 被剔除到 0）→ 归「待启动」
    derived_status = ms.status
    if total == 0:
        derived_status = "待启动"
    elif progress_pct == 100:
        derived_status = "已完成"
    elif completed > 0:
        derived_status = "进行中"

    return {
        "total": total,
        "completed": completed,
        "progress_pct": progress_pct,
        "status": derived_status,
    }
