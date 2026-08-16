"""server/board/plans.py — 方案/计划读写模块

方案文件路径：docs/projects/<prefix>/plans/<NNN>-<slug>.md
模板：docs/projects/_template/plan-template.md
校验：scripts/validate-plans.sh

提供：
- 列表：按项目/状态/关键词筛选
- 详情：读取单个方案文件
- 创建：生成编号、写盘、校验
- 更新：改状态/内容
- 转卡：调 new-card.sh 生成任务卡
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.board.plans")

# 有效状态（2026-08-16 033 F1+M4：补「已确定」= Plan 调研态；「待验收」= 卡全关待老板拍板）
# 2026-08-17 老板定：状态字更清晰——「已确认」→「待排期」（= 老板确认过、排队待转卡）；
# 已确定旁不再标「待确认」备注（避免歧义）。
VALID_STATES = frozenset({"已确定", "待排期", "部分执行", "待验收", "已完成", "作废", "已覆盖"})

# 状态流转白名单（from → allowed to）
# 033 基线：草案(池)→已确定(Plan 调研)→待排期(老板排队)→转卡→部分执行→待验收→已完成
_TRANSITIONS: dict[str, frozenset[str]] = {
    "已确定": frozenset({"待排期", "作废", "已覆盖"}),  # 033 F1：已确定 → 老板确认 → 待排期
    "待排期": frozenset({"部分执行", "作废", "已覆盖"}),
    "部分执行": frozenset({"待验收", "作废"}),  # 033 M4：卡全关→待验收，不再直接已完成
    "待验收": frozenset({"已完成", "作废"}),  # 033 M4：老板/验收席拍板→已完成
    "作废": frozenset({"已覆盖"}),
    # 已完成 / 已覆盖 = 终态，不可再改
}

# 方案文件路径模式
_PLAN_PATH_RE = re.compile(r"^docs/projects/([a-z]{2,4})/plans/([0-9]{3})-([a-z0-9][-a-z0-9]*)\.md$")

# 方案头部字段提取（匹配 "键：值" 格式）
_FIELD_RE = re.compile(r"([^：]+)：(.+)")


def _extract_header_fields(content: str) -> dict[str, str]:
    """从方案文件头部提取字段。只扫描标题后的连续 > 行块。

    2026-08-16 033 M5 修复：按「 · 」切段，段以「键：值」开头才开新字段，
    否则并入前一字段值——值内含「 · 」不再被截断（如里程碑标题「M2 · 稳控与可恢复」
    此前被截成「M2」，导致换里程碑时旧关联残留）。
    """
    fields: dict[str, str] = {}
    lines = content.split("\n")
    in_header = False
    for line in lines[:30]:
        if line.startswith(">"):
            in_header = True
            text = line.lstrip("> ").strip()
            for segment in text.split(" · "):
                segment = segment.strip()
                m = _FIELD_RE.match(segment)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    # 只取第一次出现的字段（后面的旧状态不覆盖）
                    if key not in fields:
                        fields[key] = val
                elif fields:
                    # 值续段（前字段值含「 · 」）：并入上一个字段
                    last_key = next(reversed(fields))
                    fields[last_key] += " · " + segment
        elif in_header and not line.startswith(">"):
            # 头部块结束（非 > 行）
            break
    return fields


def _extract_title(content: str) -> str:
    """从方案文件提取标题（# 方案 · ...）。"""
    for line in content.split("\n")[:5]:
        if line.startswith("# 方案"):
            return line.lstrip("# ").strip()
    return ""


def _extract_acceptance(content: str) -> dict[str, int]:
    """提取验收标准完成情况（只统计 checkbox 行，说明文字不计）。"""
    total = 0
    done = 0
    in_section = False
    for line in content.split("\n"):
        if line.strip().startswith("## 验收标准"):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            m = re.match(r"^\s*[-*]\s+\[([ xX])\]", line)
            if not m:
                continue
            total += 1
            if m.group(1) in ("x", "X"):
                done += 1
    return {"total": total, "done": done}


def _extract_func_cards(content: str) -> list[dict[str, str]]:
    """解析方案正文「## 功能卡」段（ccc-plan-027 功能卡清单 + 2026-08-16 开发卡三要素）。

    格式：
        ## 功能卡
        ### <功能卡标题>
        目标：<2-3 句人话，一眼看懂这一步做什么>
        实现：<详细实现，可选>
        验收：<验收点，可选>
        颗粒度：<范围说明>（2026-08-16 三要素之一）
        依赖：<依赖的功能卡标题/卡 ID，逗号分隔，无则「无」>（2026-08-16 三要素之一）
        架构位置：<在系统架构图中的位置>（2026-08-16 三要素之一）

    Returns:
        [{title, goal, impl, acceptance, granularity, deps, arch_position}]
    """
    cards: list[dict[str, str]] = []
    in_section = False
    current: dict[str, str] | None = None
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("## "):
            if s.startswith("## 功能卡"):
                in_section = True
                continue
            if in_section:
                break
        if not in_section:
            continue
        if s.startswith("### "):
            if current is not None:
                cards.append(current)
            current = {
                "title": s[4:].strip(),
                "goal": "",
                "impl": "",
                "acceptance": "",
                "granularity": "",
                "deps": "",
                "arch_position": "",
            }
        elif current is not None:
            if s.startswith("目标："):
                current["goal"] = s[3:].strip()
            elif s.startswith("实现："):
                current["impl"] = s[3:].strip()
            elif s.startswith("验收："):
                current["acceptance"] = s[3:].strip()
            elif s.startswith("颗粒度："):
                current["granularity"] = s[4:].strip()
            elif s.startswith("依赖："):
                current["deps"] = s[3:].strip()
            elif s.startswith("架构位置："):
                current["arch_position"] = s[5:].strip()
    if current is not None:
        cards.append(current)
    return cards


def _split_deps(raw: str) -> list[str]:
    """拆分功能卡依赖字符串（逗号/顿号/空格分隔）。

    2026-08-16 机审修复：依赖以「无」开头（含「无（注解…）」形态）= 无依赖，直接返回空。
    否则「依赖：无（2026-08-16 三要素：…）」会被按空格切碎成伪依赖 → 转卡预检误拒绝。
    """
    if not raw:
        return []
    stripped = raw.strip()
    if stripped.startswith("无"):
        return []
    deps = [d.strip() for d in re.split(r"[,，、\s]+", stripped) if d.strip()]
    # 防御：仍以「无」开头的孤立条目（注解混入）过滤
    return [d for d in deps if not d.startswith("无") and d not in ("none", "N/A")]


def _patch_card_depends(card_path: Path, dep_ids: list[str]) -> None:
    """把解析后的依赖卡 ID 写入卡头「> 依赖：」行（new-card.sh 已支持 --depends 字段）。

    优先替换已有「> 依赖：」；无则插到「> 关联：」行后；再无则插到标题行后（兜底）。
    """
    if not dep_ids:
        return
    try:
        text = card_path.read_text(encoding="utf-8")
    except OSError:
        return
    dep_line = "> 依赖：" + ", ".join(dep_ids)
    if "> 依赖：" in text:
        text = re.sub(r"(> 依赖：)[^\n]*", dep_line, text, count=1)
    elif re.search(r"^> 关联：[^\n]*$", text, re.M):
        text = re.sub(r"(^> 关联：[^\n]*$)", f"\\1\n{dep_line}", text, count=1, flags=re.M)
    else:
        text = re.sub(r"(^# [^\n]*$)", f"\\1\n{dep_line}", text, count=1, flags=re.M)
    card_path.write_text(text, encoding="utf-8")


def _inject_func_card(path: Path, card: dict[str, str]) -> None:
    """把功能卡的目标/实现/验收注入已生成卡文件对应段（两级卡：人话 + 实现）。

    目标 → 替换 ## 目标 占位；实现 → 插入 ## 实现 段；验收 → 替换 ## 验收标准 占位。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    if card.get("goal"):
        text = text.replace("（一句话，可验收。）", card["goal"], 1)
    if card.get("impl"):
        if "## 实现" not in text:
            text = re.sub(
                r"(## 目标\n\n[^\n]+\n\n)(## )",
                lambda m: f"{m.group(1)}## 实现\n\n{card['impl']}\n\n{m.group(2)}",
                text,
                count=1,
            )
        else:
            text = re.sub(r"(## 实现\n\n)([^\n]+)", f"\\g<1>{card['impl']}", text, count=1)
    if card.get("acceptance"):
        text = text.replace("1. （可执行的验收点，附命令/可观察结果）", card["acceptance"], 1)
    path.write_text(text, encoding="utf-8")


def _get_valid_prefixes(repo_root: Path) -> set[str]:
    """从 registry.yaml 提取有效前缀。"""
    registry = repo_root / "docs" / "projects" / "registry.yaml"
    if not registry.exists():
        return set()
    prefixes: set[str] = set()
    for line in registry.read_text().split("\n"):
        m = re.match(r"\s+- prefix:\s+(\S+)", line)
        if m:
            p = m.group(1)
            if p != "null":
                prefixes.add(p)
    return prefixes


def list_plans(
    repo_root: Path,
    *,
    project: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """列出所有方案，支持筛选。

    Returns:
        [{id, project, num, slug, title, status, author, tool, created, updated,
          cards, path, acceptance}]
    """
    plans_dir = repo_root / "docs" / "projects"
    results: list[dict[str, Any]] = []

    if not plans_dir.exists():
        return results

    for plan_file in plans_dir.glob("*/plans/[0-9][0-9][0-9]-*.md"):
        rel = str(plan_file.relative_to(repo_root))
        m = _PLAN_PATH_RE.match(rel)
        if not m:
            continue

        prefix = m.group(1)
        num = m.group(2)
        slug = m.group(3)

        if project and prefix != project:
            continue

        # 跳过 platform 类项目（ccc 平台自研）
        if not project:
            from server.board.registry import platform_prefixes

            reg_path = str(repo_root / "docs" / "projects" / "registry.yaml")
            if prefix in platform_prefixes(reg_path):
                continue

        try:
            content = plan_file.read_text()
        except OSError:
            continue

        fields = _extract_header_fields(content)
        plan_status = fields.get("状态", "").split("·")[0].strip()

        if status and plan_status != status:
            continue

        title = _extract_title(content)
        if q and q.lower() not in title.lower() and q.lower() not in content[:500].lower():
            continue

        acceptance = _extract_acceptance(content)

        results.append(
            {
                "id": f"{prefix}-plan-{num}",
                "project": prefix,
                "num": num,
                "slug": slug,
                "title": title,
                "status": plan_status,
                "author": fields.get("作者", ""),
                "tool": fields.get("工具", ""),
                "created": fields.get("创建", ""),
                "updated": fields.get("更新", ""),
                "cards": fields.get("关联卡", ""),
                "milestone": fields.get("里程碑", ""),
                "subproject": fields.get("子项目", ""),
                "env_prep": fields.get("环境准备", ""),
                "progress": fields.get("进度", ""),
                "path": rel,
                "acceptance": acceptance,
                "approval": fields.get("批准", ""),
            }
        )

    results.sort(key=lambda r: (r["project"], r["num"]))
    return results


def get_plan(repo_root: Path, rel_path: str) -> dict[str, Any] | None:
    """读取单个方案详情。"""
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return None

    m = _PLAN_PATH_RE.match(rel_path)
    if not m:
        return None

    try:
        content = plan_file.read_text()
    except OSError:
        return None

    fields = _extract_header_fields(content)
    return {
        "id": f"{m.group(1)}-plan-{m.group(2)}",
        "project": m.group(1),
        "num": m.group(2),
        "slug": m.group(3),
        "title": _extract_title(content),
        "status": fields.get("状态", "").split("·")[0].strip(),
        "author": fields.get("作者", ""),
        "tool": fields.get("工具", ""),
        "created": fields.get("创建", ""),
        "updated": fields.get("更新", ""),
        "cards": fields.get("关联卡", ""),
        "related": fields.get("关联方案", ""),
        "milestone": fields.get("里程碑", ""),
        "subproject": fields.get("子项目", ""),
        "env_prep": fields.get("环境准备", ""),
        "progress": fields.get("进度", ""),
        "path": rel_path,
        "content": content,
        "acceptance": _extract_acceptance(content),
        "approval": fields.get("批准", ""),
    }


def _next_num(repo_root: Path, prefix: str) -> str:
    """获取下一个可用编号。"""
    plans_dir = repo_root / "docs" / "projects" / prefix / "plans"
    if not plans_dir.exists():
        return "001"
    max_n = 0
    for f in plans_dir.glob("[0-9][0-9][0-9]-*.md"):
        try:
            n = int(f.name[:3])
            if n > max_n:
                max_n = n
        except ValueError:
            continue
    return f"{max_n + 1:03d}"


def _git_commit_push(repo_root: Path, rel_paths: list[str], message: str) -> tuple[bool, str]:
    """对指定文件批量 commit + push；与 convert_plan 同规则（P0/P1 加固：方案文件落 git）。

    Returns:
        (ok, err) — push 失败返回 (False, err) 保留本地 commit，不吞错误、不循环重试。
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", *rel_paths],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", message],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "push"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()[:500]
        return False, f"commit/push 失败，文件已落盘需手动处理: {detail}"
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"git 操作异常: {exc}"
    logger.info("方案文件已 commit+push: %s", ", ".join(rel_paths))
    return True, ""


def create_plan(
    repo_root: Path,
    *,
    project: str,
    title: str,
    content: str,
    author: str,
    tool: str,
    milestone: str | None = None,
    approved: bool = False,
    initial_status: str = "待排期",
) -> dict[str, Any]:
    """创建新方案文件。

    initial_status：创建初始态（默认「待排期」；033 F1 promote 产出「已确定」，老板确认后转「待排期」）。

    Returns:
        {ok, path, id} or {error}
    """
    valid_prefixes = _get_valid_prefixes(repo_root)
    if project not in valid_prefixes:
        return {"error": f"无效项目前缀: {project}"}

    # 拒绝 platform 类项目创建方案（ccc 平台自研不走业务方案流程）
    from server.board.registry import platform_prefixes

    reg_path = str(repo_root / "docs" / "projects" / "registry.yaml")
    if project in platform_prefixes(reg_path):
        return {"error": f"项目 {project} 为平台自研（category=platform），不走业务方案流程"}

    if not author or not author.strip():
        return {"error": "作者不能为空"}

    # 并发锁（Fix #9）：编号分配 + 写盘串行化，防两请求同取 next num 互相覆盖。
    lock_f = _acquire_convert_lock(repo_root, project)
    if lock_f is None:
        return {"error": f"{project} 有方案创建/转卡进行中，请稍后重试"}
    try:
        num = _next_num(repo_root, project)
        slug = _title_to_slug(title)
        plans_dir = repo_root / "docs" / "projects" / project / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        plan_id = f"{project}-plan-{num}"

        # 构建完整方案文件
        # 批准标签仅在 approved=True（草案→方案，节点① 老板确认）时写入；
        # 手动建方案（/plans/create）不自动打「老板确认」标签（2026-08-14 修复误标）。
        _approval_line = f"> 批准：老板确认方案 · {today}\n" if approved else ""
        plan_content = f"""# 方案 · {title}

> 项目：{project} · 编号：{plan_id} · 状态：{initial_status} · 作者：{author} · 工具：{tool}
{_approval_line}> 创建：{today} · 更新：{today}
> 关联卡：无
> 关联方案：无
> 里程碑：{milestone or "无"}

{content}
"""
        file_path = plans_dir / f"{num}-{slug}.md"
        file_path.write_text(plan_content)

        # 033 阶段 2 M6：方案确认写批准真值账本（confirm_plan）——「老板确认方案」不再是文件里一行字
        if approved:
            from server.board.audit_ledger import record_action

            record_action("confirm_plan", plan_id, source=tool or "ccc-api", detail=title)

        # 027 缝隙1：方案↔里程碑双向关联（同步 roadmap.md linked_plans）
        if milestone and milestone.strip():
            from server.board.roadmap import link_plan_to_milestone

            link_plan_to_milestone(project, plan_id, milestone.strip())

        rel = str(file_path.relative_to(repo_root))

        # 校验
        validate_script = repo_root / "scripts" / "validate-plans.sh"
        if validate_script.exists():
            result = subprocess.run(
                ["bash", str(validate_script), str(file_path)],
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
            if result.returncode != 0:
                # 校验失败，删除文件
                file_path.unlink(missing_ok=True)
                return {"error": f"方案校验失败:\n{result.stderr or result.stdout}"}

        # Fix #8：commit+push 与 convert_plan 同规则
        ok, err = _git_commit_push(repo_root, [rel], f"plans: create {plan_id} — {slug}")
        if not ok:
            return {"ok": True, "path": rel, "id": plan_id, "partial": True, "warning": err}

        return {"ok": True, "path": rel, "id": plan_id}
    finally:
        _release_convert_lock(lock_f, repo_root, project)


def _title_to_slug(title: str) -> str:
    """标题转 slug（简单英文提取，中文 fallback 为 task）。"""
    # 提取英文单词
    english = re.findall(r"[a-zA-Z0-9]+", title)
    if english:
        return "-".join(w.lower() for w in english[:6])
    return "task"


def update_plan(
    repo_root: Path,
    *,
    rel_path: str,
    status: str | None = None,
    content: str | None = None,
    cards: str | None = None,
    milestone: str | None = None,
) -> dict[str, Any]:
    """更新方案状态或内容。

    Returns:
        {ok} or {error}
    """
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}

    if not _PLAN_PATH_RE.match(rel_path):
        return {"error": "无效的方案路径格式"}

    if status and status not in VALID_STATES:
        return {"error": f"无效状态: {status}（须为: {'/'.join(sorted(VALID_STATES))}）"}

    try:
        current = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}

    # 状态流转白名单校验
    if status:
        current_fields = _extract_header_fields(current)
        current_status = current_fields.get("状态", "").split("·")[0].strip()
        if current_status not in VALID_STATES:
            # P0 全链路修复：非法现状值（如「提案（待老板测试…）」）禁止截断式替换，
            # 否则正则 [^ ·]+ 会吃掉空格前的片段、残留尾巴永久卡死。
            return {
                "error": f"当前状态值非法（{current_status}），禁止程序化修改——请先修复数据（合法值: {'/'.join(sorted(VALID_STATES))}）"
            }
        if current_status in _TRANSITIONS:
            allowed = _TRANSITIONS[current_status]
            if status not in allowed:
                return {"error": f"状态流转非法: {current_status} → {status}（允许: {', '.join(sorted(allowed))}）"}
        elif current_status in ("已完成", "作废"):
            return {"error": f"终态不可修改: {current_status}"}

    today = date.today().isoformat()

    if status:
        # 替换状态字段
        current = re.sub(
            r"(状态：)([^ ·]+)",
            f"\\g<1>{status}",
            current,
            count=1,
        )

    # 更新日期
    current = re.sub(
        r"(更新：)([0-9-]+)",
        f"\\g<1>{today}",
        current,
        count=1,
    )

    if cards is not None:
        # 替换关联卡字段
        if "关联卡：" in current:
            current = re.sub(
                r"(关联卡：)([^\n]*)",
                f"\\g<1>{cards}",
                current,
                count=1,
            )
        else:
            # 如果字段不存在，在头部插入
            lines = current.split("\n")
            # 在关联方案行后插入
            for i, line in enumerate(lines):
                if "关联方案：" in line:
                    lines.insert(i + 1, f"> 关联卡：{cards}")
                    break
            current = "\n".join(lines)

    if content is not None:
        # 替换正文内容（保留头部）
        parts = current.split("\n\n", 2)
        header = "\n\n".join(parts[:2]) if len(parts) >= 2 else current
        current = f"{header}\n\n{content}\n"

    # 027 缝隙1：里程碑字段更新（主入口）+ roadmap.md linked_plans 双向同步
    _ms_new = None
    _ms_prev = ""
    if milestone is not None:
        _ms_prev = _extract_header_fields(current).get("里程碑", "").strip()
        _ms_new = milestone if milestone.strip() else "无"
        if "里程碑：" in current:
            current = re.sub(r"(里程碑：)([^\n]*)", f"\\g<1>{_ms_new}", current, count=1)
        else:
            lines = current.split("\n")
            inserted = False
            for i, line in enumerate(lines):
                if "关联方案：" in line:
                    lines.insert(i + 1, f"> 里程碑：{_ms_new}")
                    inserted = True
                    break
            if not inserted:
                lines.insert(2, f"> 里程碑：{_ms_new}")
            current = "\n".join(lines)

    plan_file.write_text(current)

    # 人审调整动作统一化：方案作废/已覆盖 → 级联作废关联卡（防孤儿卡）
    # 已覆盖（被更晚方案取代）= 旧方案不再执行，其未关闭关联卡一并作废（老板 2026-08-14 定）。
    cascaded: list[str] = []
    cascaded_paths: list[str] = []
    if status in ("作废", "已覆盖"):
        m_cards = re.search(r"关联卡：([^\n]*)", current)
        cards_raw = m_cards.group(1).strip() if m_cards else ""
        if cards_raw and cards_raw != "无":
            card_ids = re.findall(r"([a-zA-Z]+[0-9]+(?:\-[a-zA-Z])?)", cards_raw)
            cascaded = _void_cascade_cards(repo_root, card_ids, "方案作废级联")
            if cascaded:
                from server.board.loader import load_index_file

                _idx = load_index_file(repo_root / "docs" / "dispatch")
                for _cid in cascaded:
                    _e = _idx.get(_cid) or _idx.get(_cid.lower())
                    _rp = (_e or {}).get("path") or ""
                    if _rp and _rp not in cascaded_paths:
                        cascaded_paths.append(_rp)

    # 双向同步：把方案挂到新里程碑、从旧里程碑移除
    if milestone is not None:
        m_sync = _PLAN_PATH_RE.match(rel_path)
        if m_sync:
            from server.board.roadmap import link_plan_to_milestone

            link_plan_to_milestone(
                m_sync.group(1),
                f"{m_sync.group(1)}-plan-{m_sync.group(2)}",
                _ms_new if _ms_new != "无" else None,
                _ms_prev if _ms_prev and _ms_prev != "无" else None,
            )

    # 级联回写：方案进度（看板卡状态变更时自动更新）
    sync_plan_progress(repo_root, rel_path)

    # 级联回写：里程碑进度（方案进度变更时自动更新关联里程碑）
    from server.board.roadmap import sync_milestone_progress

    m = _PLAN_PATH_RE.match(rel_path)
    if m:
        sync_milestone_progress(m.group(1), rel_path)

    # Fix #8：commit+push 与 convert_plan 同规则（作废级联卡一并提交）
    commit_paths = [rel_path] + cascaded_paths
    ok, err = _git_commit_push(repo_root, commit_paths, f"plans: update {rel_path}")
    if not ok:
        return {
            "ok": True,
            "updated": True,
            "partial": True,
            "warning": err,
            "cascaded": cascaded,
        }

    return {"ok": True, "updated": True, "cascaded": cascaded}


def _void_cascade_cards(repo_root: Path, card_ids: list[str], reason: str) -> list[str]:
    """方案作废时级联：把关联卡（待分派/执行中/已回写/打回）标「作废（reason）」。

    人审调整动作统一化（2026-08-14）：作废方案不能留孤儿卡，未关闭的关联卡一并作废。
    作废 = 终态，写卡文件（与「已关闭」同级权威）；已关闭/已作废 不动。

    Returns:
        被级联作废的卡 ID 列表。
    """
    if not card_ids:
        return []
    from server.board.loader import load_index_file
    from server.board.models import base_state
    from server.engine.store import _replace_state_in_metadata

    index = load_index_file(repo_root / "docs" / "dispatch")
    cascaded: list[str] = []
    cascaded_paths: list[Path] = []
    for cid in card_ids:
        entry = index.get(cid) or index.get(cid.lower())
        if not entry:
            continue
        rel_path = entry.get("path") or ""
        if not rel_path or "docs/archive" in rel_path:
            continue
        cur = base_state(str(entry.get("state") or ""))
        if cur not in ("待分派", "执行中", "已回写", "打回"):
            continue
        card_path = repo_root / rel_path
        try:
            text = card_path.read_text(encoding="utf-8")
            new_text = _replace_state_in_metadata(text, f"作废（{reason[:40]}）")
        except (OSError, ValueError):
            continue
        card_path.write_text(new_text, encoding="utf-8")
        cascaded.append(cid)
        cascaded_paths.append(rel_path)
    if cascaded:
        # 刷新索引，让 sync_plan_progress 读到新状态
        try:
            from server.board.loader import load_dispatch_cards

            load_dispatch_cards(repo_root / "docs" / "dispatch")
        except Exception:
            logger.exception("方案作废级联：刷新卡片索引失败（不阻断）")
    return cascaded


_CONVERT_LOCK = threading.Lock()


def _acquire_convert_lock(repo_root: Path, prefix: str):
    """同前缀转卡互斥锁（fcntl 文件锁；无 fcntl 环境退化为进程内锁）。"""
    lock_dir = repo_root / "docs" / "projects" / prefix / "plans"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f".convert-{prefix}.lock"
    try:
        import fcntl
    except ImportError:
        if not _CONVERT_LOCK.acquire(blocking=False):
            return None
        return ("thread", None)
    try:
        f = open(lock_path, "w")
    except OSError:
        return None
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return ("fcntl", f)


def _release_convert_lock(handle, repo_root: Path, prefix: str) -> None:
    kind, f = handle
    if kind == "thread":
        _CONVERT_LOCK.release()
        return
    try:
        import fcntl

        fcntl.flock(f, fcntl.LOCK_UN)
    finally:
        f.close()
        lock_path = repo_root / "docs" / "projects" / prefix / "plans" / f".convert-{prefix}.lock"
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _extract_created_card(stdout: str, prefix: str, repo_root: Path) -> tuple[Path, str] | None:
    """从 new-card.sh 输出提取生成的卡文件（路径 + 卡 ID）。"""
    fname_m = re.search(rf"({prefix}\d{{3}}-[a-z0-9][-a-z0-9]*\.md)", stdout)
    if not fname_m:
        return None
    fname = fname_m.group(1)
    path_m = re.search(rf"([^\s]*docs/dispatch/{prefix}/{re.escape(fname)})", stdout)
    if path_m:
        p = Path(path_m.group(1))
        path = p if p.is_absolute() else repo_root / p
    else:
        path = repo_root / "docs" / "dispatch" / prefix / fname
    return path, fname.split("-", 1)[0]


def accept_plan(
    repo_root: Path,
    *,
    rel_path: str,
) -> dict[str, Any]:
    """验收拍板（033 M4）：待验收 方案 → 老板/验收席按验收标准拍板 → 已完成 + 批准行。

    校验：方案状态为「待验收」；验收标准全部勾选（未勾选拒绝，督促先核对）。
    """
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}
    _m_accept = _PLAN_PATH_RE.match(rel_path)
    if not _m_accept:
        return {"error": "无效的方案路径格式"}
    project = _m_accept.group(1)
    try:
        current = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}
    fields = _extract_header_fields(current)
    cur_status = fields.get("状态", "").split("·")[0].strip()
    if cur_status != "待验收":
        return {"error": f"当前状态「{cur_status}」不可验收拍板，只有「待验收」方案可拍板"}

    acc = _extract_acceptance(current)
    if acc["total"] > 0 and acc["done"] < acc["total"]:
        return {"error": f"验收标准未全部勾选（{acc['done']}/{acc['total']}）——请先核对并勾选验收项"}

    # 033 阶段 2 M6：验收拍板前查「转卡」批准真值账本（convert）——存量无记录 WARN 放行
    from server.board.audit_ledger import has_action, record_action

    if not has_action("convert", f"{project}-plan-{_m_accept.group(2)}"):
        logger.warning("方案 %s 无 convert 账本记录（存量降级放行；新方案须转卡后验收）", f"{project}-plan-{_m_accept.group(2)}")

    # 033 阶段 2 M6：交付物声明校验（轻量 WARN，不全量核查——交付报告/CHANGELOG/RELEASE/tag/可复跑）
    if not re.search(r"交付|CHANGELOG|RELEASE|deliver", current, re.I):
        logger.warning(
            "方案 %s 未声明交付物（交付报告/CHANGELOG/RELEASE/Git Tag/可复跑验证），拍板前建议在备注补齐",
            rel_path,
        )

    today = date.today().isoformat()
    current = re.sub(r"(状态：)([^\s·]+)", r"\1已完成", current, count=1)
    current = re.sub(r"(更新：)([0-9-]+)", f"\\g<1>{today}", current, count=1)
    # 写「老板验收拍板」批准行（三节点验收权威源）
    if re.search(r"(^|\n)\s*> 批准：", current):
        current = re.sub(r"(\n\s*> 批准：)([^\n]*)", f"\\1老板验收拍板 · {today}", current, count=1)
    else:
        current = re.sub(r"(> 项目：[^\n]*\n)", f"\\1> 批准：老板验收拍板 · {today}\n", current, count=1)
    plan_file.write_text(current)

    # 033 阶段 2 M6：验收拍板写批准真值账本（accept）——「老板验收拍板」不再仅靠批准行
    record_action("accept", f"{project}-plan-{_m_accept.group(2)}", source="ccc-api", detail=rel_path)

    ok, err = _git_commit_push(repo_root, [rel_path], f"plans: accept {rel_path}")
    if not ok:
        return {"ok": True, "accepted": True, "partial": True, "warning": err}
    return {"ok": True, "accepted": True}


def sync_plan_progress(repo_root: Path, rel_path: str) -> dict[str, Any]:
    """读取方案关联的卡，从 cards.index.jsonl 查每张卡的状态，计算 closed/total，
    回写方案文件头部的进度信息。

    被 convert_plan / update_plan 调用，在看板卡状态变更时自动触发级联回写。

    Returns:
        {ok, progress: {total, closed, progress_pct}} or {error}
    """
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}

    if not _PLAN_PATH_RE.match(rel_path):
        return {"error": "无效的方案路径格式"}

    try:
        current = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}

    fields = _extract_header_fields(current)
    cards_raw = fields.get("关联卡", "").strip()
    if not cards_raw or cards_raw == "无":
        return {"ok": True, "progress": {"total": 0, "closed": 0, "progress_pct": 0}}

    # 从卡片引用中提取卡 ID
    card_ids = re.findall(r"([a-zA-Z]+[0-9]+(?:\-[a-zA-Z])?)", cards_raw)

    if not card_ids:
        return {"ok": True, "progress": {"total": 0, "closed": 0, "progress_pct": 0}}

    # 从 cards.index.jsonl 读取卡片状态
    from server.board.loader import load_index_file
    from server.board.models import base_state

    index = load_index_file(repo_root / "docs" / "dispatch")
    card_id_lower_map = {k.lower(): v for k, v in index.items()}

    total = len(card_ids)
    closed = 0
    voided = 0
    for cid in card_ids:
        entry = card_id_lower_map.get(cid.lower())
        # P1#14：关闭态口径统一——支持「已关闭（…）」括号变体（base_state 语义）
        state = str(entry.get("state", "")) if entry else ""
        base = base_state(state)
        if base == "已关闭":
            closed += 1
        elif base == "作废":
            # 人审调整动作统一化：作废卡从方案总数剔除（剩余活跃卡全关 → 完成）
            voided += 1

    # 活跃卡 = 总关联卡 − 作废卡（作废=不再做，不占完成分母）
    total_active = total - voided
    progress_pct = int(closed / total_active * 100) if total_active > 0 else 0

    # 回写进度到方案文件头部
    # 格式: > 进度：3/5 (60%)（作废 2）——作废卡单列，不占完成分母
    progress_text = f"进度：{closed}/{total_active} ({progress_pct}%)"
    if voided:
        progress_text += f"（作废 {voided}）"

    if "进度：" in current:
        current = re.sub(
            r"(进度：)([^\n]*)",
            progress_text,
            current,
            count=1,
        )
    else:
        # 在关联方案行后插入进度行
        lines = current.split("\n")
        inserted = False
        for i, line in enumerate(lines):
            if "关联方案：" in line:
                lines.insert(i + 1, f"> {progress_text}")
                inserted = True
                break
        if not inserted:
            # 在头部 > 块末尾插入
            for i, line in enumerate(lines):
                if line.startswith(">"):
                    continue
                if i > 0 and lines[i - 1].startswith(">"):
                    lines.insert(i, f"> {progress_text}")
                    inserted = True
                    break
        if not inserted:
            # 在标题后插入
            lines.insert(2, f"> {progress_text}")
        current = "\n".join(lines)

    # 027 缝隙3 + 033 M4：活跃关联卡全关 → 方案置「待验收」（非已完成），老板/验收席拍板才「已完成」；
    # 作废卡剔除出 total，剩余活跃卡全关即待验收。
    # 边界：全部关联卡作废（total_active==0）→ 方案自动置「作废」（没有活卡=方案作废）。
    auto_completed = False
    status_m = re.search(r"状态：([^\s·]+)", current)
    cur_status = status_m.group(1) if status_m else ""
    if cur_status in ("待排期", "部分执行"):
        if total_active > 0 and closed == total_active:
            current = re.sub(r"(状态：)([^\s·]+)", r"\1待验收", current, count=1)
            auto_completed = True
        elif total_active == 0 and voided > 0:
            # 全作废边界：方案自动作废（级联卡已作废，方案不再有活卡）
            current = re.sub(r"(状态：)([^\s·]+)", r"\1作废", current, count=1)
            auto_completed = True

    plan_file.write_text(current)

    # total 字段 = 活跃卡数（剔除作废），与进度行展示口径一致
    return {
        "ok": True,
        "progress": {"total": total_active, "closed": closed, "progress_pct": progress_pct},
        "auto_completed": auto_completed,
    }


def plan_card_states(repo_root: Path, cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """方案 → 关联卡在看板六列的分布（ccc-plan-024 流程条数据源）。

    cards: 已富化卡列表（含 id / board_column / state）。
    Returns:
        {plan_rel_path: {"total": n, "cols": {"待分派": n, ...}}}
    """
    plans = list_plans(repo_root)
    cards_by_id = {str(c.get("id", "")).lower(): c for c in cards if c.get("id")}
    out: dict[str, dict[str, Any]] = {}
    # 人审统一化：作废卡从方案进度剔除，流程条补作废列（契约列集合）
    col_keys = ("待分派", "执行中", "机审", "已回写", "打回", "已关闭", "作废")
    for p in plans:
        ref = re.findall(r"([a-zA-Z]+[0-9]+)", p.get("cards") or "")
        cols = {k: 0 for k in col_keys}
        for cid in ref:
            c = cards_by_id.get(cid.lower())
            col = str((c or {}).get("board_column") or (c or {}).get("state") or "待分派")
            cols[col] = cols.get(col, 0) + 1
        out[p["path"]] = {"total": len(ref), "cols": cols}
    return out


def _rollback_created(files: list[Path]) -> None:
    """删除本轮已生成的卡文件（转卡失败时回滚，保证重试不产生重复卡）。"""
    for p in files:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def convert_plan(
    repo_root: Path,
    *,
    rel_path: str,
    slices: list[str] | None = None,
    no_push: bool = False,
) -> dict[str, Any]:
    """将方案转为任务卡。

    2026-08-17 修复：repo_root 统一为绝对路径——调用方传相对路径（如 Path('.')）
    时，commit 阶段 `p.relative_to(repo_root)` 抛「not in subpath」导致卡已生成但
    commit+push 中断（状态已推进、卡是孤儿，engine 感知不到）。

    1. 读取方案的「功能卡」/「转卡计划」段
    2. 调 new-card.sh 生成任务卡（全部成功才推进状态；失败回滚已生成卡）
    3. slices 指定时只转该子集（逐步投入——一次一个子项目的功能卡，2026-08-16）
    4. 依赖硬约束：被依赖必须在本批功能卡或已有关卡中；否则拒绝出卡
    5. 自动推进方案状态为「部分执行」+ 写入关联卡
    6. 默认 commit+push 到远端（no_push=True 供测试/无 git 环境跳过）

    Returns:
        {ok, cards: [card_id]} or {error}
    """
    # 2026-08-17：repo_root 规范化绝对路径（防相对路径下 relative_to 不匹配）
    repo_root = repo_root.resolve()
    plan_file = repo_root / rel_path
    if not plan_file.exists():
        return {"error": "方案文件不存在"}

    m = _PLAN_PATH_RE.match(rel_path)
    if not m:
        return {"error": "无效的方案路径格式"}

    prefix = m.group(1)

    # 红线（2026-08-10）：禁出卡前缀（如 ccc 平台自研）禁止转卡，方案仍可存在与查看
    try:
        from server.board.registry import forbidden_prefixes

        if prefix in forbidden_prefixes(str(repo_root / "docs" / "projects" / "registry.yaml")):
            return {"error": f"项目 {prefix} 为禁出卡前缀（平台自研红线），禁止转卡"}
    except Exception:
        pass

    # 并发锁：同前缀同时只允许一个转卡，防重复出卡
    lock_f = _acquire_convert_lock(repo_root, prefix)
    if lock_f is None:
        return {"error": f"{prefix} 有转卡进行中，请稍后重试"}
    try:
        result = _convert_plan_locked(
            repo_root, rel_path=rel_path, prefix=prefix, slices=slices, no_push=no_push
        )
        # 033 阶段 2 M6：转卡成功写批准真值账本（convert）
        if result.get("ok"):
            from server.board.audit_ledger import record_action

            record_action(
                "convert",
                f"{prefix}-plan-{m.group(2)}",
                source="ccc-api",
                detail=", ".join(result.get("cards") or []),
            )
        return result
    finally:
        _release_convert_lock(lock_f, repo_root, prefix)


def _convert_plan_locked(
    repo_root: Path,
    *,
    rel_path: str,
    prefix: str,
    slices: list[str] | None = None,
    no_push: bool,
) -> dict[str, Any]:
    m = _PLAN_PATH_RE.match(rel_path)
    plan_file = repo_root / rel_path
    try:
        content = plan_file.read_text()
    except OSError:
        return {"error": "读取方案文件失败"}

    # 状态检查：只允许待排期/部分执行转卡
    current_fields = _extract_header_fields(content)
    current_status = current_fields.get("状态", "").split("·")[0].strip()
    if current_status not in ("待排期", "部分执行"):
        return {"error": f"当前状态「{current_status}」不可转卡，只有「待排期」或「部分执行」状态可以转卡"}

    # 2026-08-16 环境准备门禁联动：子项目方案必须声明「环境准备」才能转卡
    # （承接作废 hp-plan-004 的「开发/部署隔离 + 可重建验证」为强制前置门禁）
    if "子项目：" in content and not re.search(r"环境准备：", content):
        return {
            "error": "方案缺「环境准备」声明——子项目方案转卡前必须先声明环境准备（2026-08-16 门禁）"
        }

    # 033 阶段 2 M6：转卡前查「方案确认」批准真值账本（confirm_plan）——「老板确认转卡」不再仅靠卡文件自盖章
    # 存量方案（阶段 1 前确认、无账本记录）→ WARN 放行（渐进真值化，不阻断存量）
    from server.board.audit_ledger import has_action

    _plan_key = f"{prefix}-plan-{m.group(2)}"
    if not has_action("confirm_plan", _plan_key):
        logger.warning("方案 %s 无 confirm_plan 账本记录（存量降级放行；新方案须确认后转卡）", _plan_key)

    # 027：功能卡清单优先（## 功能卡 段），回退旧「## 转卡计划」段（每行一卡）
    _func_cards = _extract_func_cards(content)
    if _func_cards:
        card_slices = [
            {
                "title": c["title"],
                "goal": c.get("goal", ""),
                "impl": c.get("impl", ""),
                "acceptance": c.get("acceptance", ""),
                "deps": c.get("deps", ""),
                "mode": "func_cards",
            }
            for c in _func_cards
        ]
    else:
        plan_section = ""
        in_section = False
        for line in content.split("\n"):
            if line.strip().startswith("## 转卡计划"):
                in_section = True
                continue
            if in_section and line.strip().startswith("##"):
                break
            if in_section:
                plan_section += line + "\n"
        plan_lines = [
            ln
            for ln in plan_section.strip().split("\n")
            if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("```")
        ]
        card_slices = [
            {
                "title": re.sub(r"^[-*]\s*|^\d+\.\s*", "", ln).strip(),
                "goal": "",
                "impl": "",
                "acceptance": "",
                "deps": "",
                "mode": "plan_section",
            }
            for ln in plan_lines
        ]

    card_slices = [s for s in card_slices if s["title"]]
    if not card_slices:
        return {"error": "方案缺少「功能卡」或「转卡计划」段"}

    # 2026-08-16 逐步投入：slices 指定时只转该子集（一次一个子项目的功能卡）
    if slices is not None:
        _allowed = set(slices)
        _missing = [t for t in _allowed if not any(c["title"] == t for c in card_slices)]
        if _missing:
            return {"error": f"指定的功能卡不在方案中: {', '.join(_missing)}"}
        card_slices = [c for c in card_slices if c["title"] in _allowed]
        if not card_slices:
            return {"error": "指定的功能卡子集为空，无法转卡"}

    # 2026-08-16 依赖硬约束：被依赖必须在本批功能卡（标题）或已有关卡（卡 ID）中
    from server.board.loader import load_index_file

    _index = load_index_file(repo_root / "docs" / "dispatch")
    _available_titles = {c["title"] for c in card_slices}
    for c in card_slices:
        for dep in _split_deps(c.get("deps", "")):
            if dep in _available_titles:
                continue
            if dep.lower() in _index:
                continue
            return {
                "error": f"功能卡「{c['title']}」依赖「{dep}」既不在本批转卡、也不是已有关卡——拒绝出卡（依赖硬约束 2026-08-16）"
            }

    # 提取标题（方案标题去掉「方案 · 」前缀）
    title = _extract_title(content).removeprefix("方案 · ").strip()

    new_card_script = repo_root / "scripts" / "new-card.sh"
    if not new_card_script.exists():
        return {"error": "new-card.sh 不存在"}

    created_files: list[Path] = []
    cards: list[str] = []

    # 按功能卡/转卡计划逐张出卡（027：功能卡段优先；转卡计划段兼容旧格式）
    for s in card_slices:
        card_title = s["title"].strip()
        if not card_title:
            continue

        full_title = f"{title} — {card_title}"
        # 出卡时带方案关联（P0 全链路修复：否则卡关闭后 sync_plan_cards 无法定位方案 → 进度永不重算）
        plan_id = f"{prefix}-plan-{m.group(2)}"
        result = subprocess.run(
            [
                "bash", str(new_card_script),
                "--project", prefix,
                "--title", full_title,
                "--related", plan_id,
            ],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        if result.returncode != 0:
            _rollback_created(created_files)
            return {
                "error": f"出卡失败: {card_title}\n{result.stderr or result.stdout}",
                "cards": cards,
            }

        created = _extract_created_card(result.stdout, prefix, repo_root)
        if created is None:
            _rollback_created(created_files)
            return {
                "error": f"出卡成功但无法解析卡文件路径: {card_title}\n{result.stdout}",
                "cards": cards,
            }
        created_files.append(created[0])
        cards.append(created[1])
        # 027 两级卡：功能卡目标/实现/验收注入卡文件
        if s["mode"] == "func_cards" and (s["goal"] or s["impl"] or s["acceptance"]):
            _inject_func_card(created[0], s)

    # 2026-08-16 依赖透传：两段式——先出卡，再把依赖解析成卡 ID 写回卡头「> 依赖：」
    # 依赖引用 = 本批功能卡标题（同批，映射到本批卡 ID）或已有关卡 ID（跨方案，透传）
    _batch_id_by_title = {s["title"]: cards[i] for i, s in enumerate(card_slices) if s["title"]}
    for i, s in enumerate(card_slices):
        dep_ids: list[str] = []
        for dep in _split_deps(s.get("deps", "")):
            if dep in _batch_id_by_title:
                dep_ids.append(_batch_id_by_title[dep])
            elif re.match(r"^[a-z]{2,4}\d{3}$", dep):
                dep_ids.append(dep)
            # 其它已在依赖硬约束预检拦截，不会到达这里
        if dep_ids:
            _patch_card_depends(created_files[i], dep_ids)

    # 自动推进状态为「部分执行」+ 写入关联卡
    today = date.today().isoformat()
    card_list = ", ".join(cards) if cards else "无"
    current = plan_file.read_text()

    # 更新状态
    current = re.sub(r"(状态：)([^ ·]+)", r"\1部分执行", current, count=1)
    # 更新日期
    current = re.sub(r"(更新：)([0-9-]+)", f"\\g<1>{today}", current, count=1)
    # 更新关联卡
    current = re.sub(r"(关联卡：)([^\n]*)", f"\\g<1>{card_list}", current, count=1)
    # 人审节点②：方案批准行更新为「老板确认转卡」（无则插入到头部引用块）
    if re.search(r"(^|\n)\s*> 批准：", current):
        current = re.sub(r"(\n\s*> 批准：)([^\n]*)", f"\\1老板确认转卡 · {today}", current, count=1)
    else:
        current = re.sub(r"(> 项目：[^\n]*\n)", f"\\1> 批准：老板确认转卡 · {today}\n", current, count=1)

    # 人审节点②：给每张新卡追加「老板确认转卡」批准行（单行最新语义，卡头 validate 只查必填 5 key）
    for cf in created_files:
        try:
            ctext = cf.read_text(encoding="utf-8")
        except OSError:
            continue
        clines = ctext.split("\n")
        insert_at = 1
        for i, ln in enumerate(clines):
            if ln.startswith("# "):
                insert_at = i + 1
                break
        clines.insert(insert_at, f"> 批准：老板确认转卡 · {today}")
        cf.write_text("\n".join(clines))

    plan_file.write_text(current)

    if no_push:
        # 级联回写：方案进度（看板卡状态变更时自动更新）
        sync_plan_progress(repo_root, rel_path)
        # 级联回写：里程碑进度（方案进度变更时自动更新关联里程碑）
        from server.board.roadmap import sync_milestone_progress

        sync_milestone_progress(prefix, rel_path)
        return {"ok": True, "cards": cards}

    # P0 全链路修复：正常（push）分支也触发级联回写——方案进度与里程碑进度
    # 在 git add 之前执行，进度行与卡文件同批 commit（此前只在 no_push 分支调用）
    sync_plan_progress(repo_root, rel_path)
    from server.board.roadmap import sync_milestone_progress

    sync_milestone_progress(prefix, rel_path)

    # commit+push：卡文件与方案状态同批提交，Engine 才能感知新卡
    rel_paths = [str(p.relative_to(repo_root)) for p in created_files] + [rel_path]
    plan_id = f"{prefix}-plan-{m.group(2)}"
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", *rel_paths],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "commit",
                "-m",
                f"cards: convert-plan {plan_id} ({len(cards)} slices)",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "push"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "error": f"卡已生成并推进方案状态，但提交/推送失败，需手动推送: {exc.stderr or exc.stdout}",
            "cards": cards,
            "partial": True,
        }

    return {"ok": True, "cards": cards}
