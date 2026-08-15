"""中枢 Prompt 注入器 — 制卡阶段生成 LLM 专用提示段。

出卡时由 new-card.sh 调用，从 registry.yaml + 项目 README + KB 检索
生成「执行提示」（给开发大模型）和「机审提示」（给验收大模型），
注入到任务卡文件中。

用法:
    # 生成并注入到卡文件
    python3 -m server.board.prompt_inject <card_path> --project <prefix> --title "..."

    # 仅生成提示文本（dry-run），不写卡文件
    python3 -m server.board.prompt_inject <card_path> --project <prefix> --title "..." --dry-run

    # 从 stdin 读取卡文件内容
    cat card.md | python3 -m server.board.prompt_inject - --project mx --title "..."

设计原则:
    - 零硬编码: 项目路径/技术栈/模块名全部从 registry + README 提取
    - 容错: 项目 README 缺失或 KB 不可用时不报错，生成基础提示
    - LLM 友好: 输出格式为结构化列表，大模型可直接解析执行
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

from server.board.card_header import parse_metadata

logger = logging.getLogger("ccc.prompt_inject")

# ── 项目根目录（相对于本文件） ──
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_registry() -> dict[str, Any]:
    """加载 registry.yaml 并返回以 prefix 为键的字典。"""
    import yaml

    registry_path = _PROJECT_ROOT / "docs" / "projects" / "registry.yaml"
    if not registry_path.is_file():
        logger.warning("registry.yaml 不存在: %s", registry_path)
        return {}

    try:
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("registry.yaml 解析失败: %s", exc)
        return {}

    projects = data.get("projects", []) if isinstance(data, dict) else []
    by_prefix: dict[str, Any] = {}
    for proj in projects:
        prefix = proj.get("prefix")
        if prefix:
            by_prefix[prefix] = proj
    return by_prefix


def _load_project_readme(prefix: str) -> dict[str, str]:
    """读取 docs/projects/<prefix>/README.md，提取关键字段。

    返回 dict 包含:
        - name: 项目名
        - role: 一句话定位
        - mac2017_path: 2017 仓库路径
        - tech_stack: 技术栈摘要（提取自「附 A：技术栈」或正文）
        - key_modules: 关键模块（提取自「附 B：目录树」或「crate 清单」等）
        - forbidden: 禁区
        - raw: 原始全文（截断到 8000 字符）
    """
    readme_path = _PROJECT_ROOT / "docs" / "projects" / prefix / "README.md"
    result: dict[str, str] = {
        "name": prefix,
        "role": "",
        "mac2017_path": "",
        "tech_stack": "",
        "key_modules": "",
        "forbidden": "",
        "raw": "",
    }

    if not readme_path.is_file():
        return result

    try:
        raw = readme_path.read_text(encoding="utf-8")
    except OSError:
        return result

    result["raw"] = raw[:8000]

    # 提取「是什么」段（第一段 ## 后的内容）
    m = re.search(r"##\s+是什么\s*\n+(.+?)(?=\n##|\Z)", raw, re.DOTALL)
    if m:
        result["role"] = m.group(1).strip()

    # 提取 2017 路径
    m = re.search(r"Mac2017.*?`([^`]+)`", raw)
    if m:
        result["mac2017_path"] = m.group(1).strip()

    # 提取技术栈（「附 A：技术栈」或「技术栈」段）
    tech_section = ""
    for pattern in [r"##\s*附\s*A[：:]\s*技术栈", r"##\s*技术栈"]:
        m = re.search(pattern + r"\s*\n(.+?)(?=\n##\s|\n---|\Z)", raw, re.DOTALL)
        if m:
            tech_section = m.group(1).strip()
            break

    if tech_section:
        # 提取表格中的技术-版本对
        tech_lines: list[str] = []
        for line in tech_section.split("\n"):
            line = line.strip()
            # 匹配表格行: | 语言 | Rust | edition 2021 |
            if line.startswith("|") and not line.startswith("|--") and not line.startswith("| :"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2:
                    # 跳过表头行（如 | 层 | 技术 | 版本 |）
                    if parts[0] in ("层", "层级", "分类", "Category", "Crate") or parts[0] == parts[1]:
                        continue
                    tech_lines.append(f"{parts[0]}={parts[1]}" + (f" ({parts[2]})" if len(parts) > 2 else ""))
        if tech_lines:
            result["tech_stack"] = ", ".join(tech_lines[:20])

    # 提取关键模块（「附 B：目录树」或「crate 清单」等）
    for pattern in [
        r"##\s*附\s*B[：:]\s*目录树",
        r"##\s*附\s*B[：:].*",
        r"###\s*.*crate\s*清单",
        r"###\s*.*目录.*树",
    ]:
        m = re.search(pattern + r"\s*\n(.+?)(?=\n##\s|\n---|\Z)", raw, re.DOTALL)
        if m:
            section = m.group(1).strip()
            # 提取代码块中的目录树
            tree_match = re.search(r"```\n(.+?)```", section, re.DOTALL)
            if tree_match:
                result["key_modules"] = tree_match.group(1).strip()[:2000]
            else:
                # 提取表格行
                mod_lines = []
                for line in section.split("\n"):
                    if line.strip().startswith("|") and not line.strip().startswith("|--"):
                        mod_lines.append(line.strip())
                if mod_lines:
                    result["key_modules"] = "\n".join(mod_lines[:20])
            break

    # 提取禁区
    m = re.search(r"##\s+禁区\s*\n(.+?)(?=\n##|\n---|\Z)", raw, re.DOTALL)
    if m:
        result["forbidden"] = m.group(1).strip()

    return result


def _search_kb(project_prefix: str, title: str, focus: str = "skill") -> str:
    """搜索知识库获取项目相关知识条目。

    Args:
        project_prefix: 项目前缀
        title: 任务卡标题
        focus: 搜索焦点 — ``"skill"``（开发技能）、``"review"``（审查清单）、``"lesson"``（历史教训）

    Returns:
        格式化的知识库参考文本，含具体命令/守则/教训。
    """
    query_map = {
        "skill": f"{project_prefix} 常用命令 cargo test pytest 模块 守则",
        "review": f"{project_prefix} 审查 清单 P0 可修 不可修",
        "lesson": f"{project_prefix} 教训 根因 修复 适用场景",
    }
    query = query_map.get(focus, f"{project_prefix} {title}")

    try:
        from server.kb import service as kb_service

        # 按项目域过滤：优先匹配 domains/projects/ 下的条目
        results = kb_service.search(query, top_k=8)
        if not results:
            return ""

        # 优先项目专属条目（domains::projects::），其次通用条目
        project_results = [r for r in results if "::projects::" in r.get("id", "")]
        general_results = [r for r in results if "::projects::" not in r.get("id", "")]
        ranked = project_results + general_results

        # 提取可执行内容：优先匹配「常用命令」「开发守则」「审查维度」「教训」等关键节
        snippets: list[str] = []
        for r in ranked[:5]:
            snippet = r.get("snippet", "")[:300]
            doc_id = r.get("id", "")
            if not snippet:
                continue

            # 项目相关性：非项目专属条目需包含项目前缀
            if "::projects::" not in doc_id and project_prefix not in snippet.lower():
                continue

            # 按焦点过滤：只保留与当前焦点相关的内容
            if focus == "skill":
                # 提取命令、守则、模块
                if any(
                    kw in snippet for kw in ("常用命令", "开发守则", "关键模块", "cargo", "pytest", "npm run", "构建")
                ):
                    snippets.append(_clean_snippet(snippet, doc_id))
            elif focus == "review":
                # 提取审查维度、可修/不可修边界
                if any(kw in snippet for kw in ("审查维度", "审查重点", "P0", "可修范围", "不可修边界", "必须打回")):
                    # 额外过滤：非项目专属条目需包含项目前缀
                    if "::projects::" in doc_id and project_prefix not in snippet.lower():
                        continue
                    snippets.append(_clean_snippet(snippet, doc_id))
            elif focus == "lesson":
                # 提取教训（必须包含项目前缀或关键词）
                if any(kw in snippet for kw in ("根因", "修复", "教训", "适用场景")):
                    # 额外过滤：非项目专属条目需包含项目前缀
                    if "::projects::" in doc_id and project_prefix not in snippet.lower():
                        continue
                    snippets.append(_clean_snippet(snippet, doc_id))

        if snippets:
            return "\n".join(snippets[:3])
    except Exception:
        pass

    return ""


def _clean_snippet(snippet: str, doc_id: str) -> str:
    """清理 KB 片段：截断、去噪、加来源标记。"""
    # 截断到合理长度
    text = snippet.strip()
    if len(text) > 280:
        text = text[:280] + "..."
    return f"  - [{doc_id}] {text}"


def _parse_related_field(card_content: str) -> str:
    """提取卡内容中的关联字段。"""
    meta = parse_metadata(card_content)
    return meta.get("关联", "").strip()


def _parse_plan_ref(related_text: str) -> tuple[str, str] | None:
    """解析关联字段中的方案前缀和编号。

    例如: "ccc-plan-011 卡1" -> ("ccc", "011")
    """
    match = re.search(r"\b([a-zA-Z0-9]+)-plan-(\d+)\b", related_text, re.IGNORECASE)
    if match:
        return match.group(1).lower(), match.group(2)
    return None


def _get_plan_summary(prefix: str, num: str) -> str:
    """读取并解析方案摘要。"""
    plans_dir = _PROJECT_ROOT / "docs" / "projects" / prefix / "plans"
    if not plans_dir.is_dir():
        return ""

    plan_files = list(plans_dir.glob(f"{num}-*.md"))
    if not plan_files:
        return ""

    try:
        plan_content = plan_files[0].read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("读取方案文件失败 %s: %s", plan_files[0], exc)
        return ""

    # 提取目标：支持 ## 目标 或 ## 0. 一句话目标
    m_target = re.search(r"##\s+(?:\d+\.\s+)?(?:一句话)?目标\s*\n+(.+?)(?=\n##|\n---|(?:\Z))", plan_content, re.DOTALL)
    target = m_target.group(1).strip() if m_target else ""

    # 提取验收标准
    m_criteria = re.search(r"##\s+验收标准\s*\n+(.+?)(?=\n##|\n---|(?:\Z))", plan_content, re.DOTALL)
    criteria = m_criteria.group(1).strip() if m_criteria else ""

    if not target and not criteria:
        return ""

    def clean_block(text: str) -> str:
        # 去除 markdown 复选框 - [ ] 或 - [x]
        text = re.sub(r"- \[[ xX]\]\s*", "", text)
        # 去除列表行首 - 或 *
        text = re.sub(r"^[-*]\s*", "", text, flags=re.MULTILINE)
        # 替换多个空白字符为一个空格
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    target_clean = clean_block(target).rstrip("。")
    criteria_clean = clean_block(criteria).rstrip("。")

    parts = []
    if target_clean:
        parts.append(f"目标：{target_clean}")
    if criteria_clean:
        parts.append(f"验收标准：{criteria_clean}")

    summary = "。".join(parts)
    if summary:
        summary += "。"
    if len(summary) > 400:
        summary = summary[:397] + "..."
    return summary


def _get_project_recent_lines(prefix: str) -> list[str]:
    """读取并解析项目 README 的「线路/近况」节，返回最多 3 条。"""
    readme_path = _PROJECT_ROOT / "docs" / "projects" / prefix.lower() / "README.md"
    if not readme_path.is_file():
        return []

    try:
        raw = readme_path.read_text(encoding="utf-8")
    except OSError:
        return []

    m = re.search(r"##\s*线路\s*/\s*近况\s*\n+(.+?)(?=\n##|\n---|(?:\Z))", raw, re.DOTALL)
    if not m:
        m = re.search(r"##\s*线路近况\s*\n+(.+?)(?=\n##|\n---|(?:\Z))", raw, re.DOTALL)

    if not m:
        return []

    section_content = m.group(1).strip()

    lines = []
    for line in section_content.splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("*"):
            item = re.sub(r"^[-*]\s*", "", line).strip()
            if item:
                lines.append(item)
                if len(lines) >= 3:
                    break
    return lines


def _role_skill_hint(card_content: str) -> str:
    """按任务卡「角色」字段查 role-skills.yaml，返回 Skill 注入提示。

    机制（2026-08-10 老板洞察）：通用智能体按任务卡成为专家。
    卡头「角色：<role>」→ 查映射表 → 注入「请加载 Skill：xxx」。
    """
    if not card_content:
        return ""
    import re

    m = re.search(r"角色[:：]\s*([^\s·|]+)", card_content)
    if not m:
        return ""
    role = m.group(1).strip()
    cfg = _load_role_skills()
    entry = cfg.get("roles", {}).get(role)
    if not entry or not entry.get("skill"):
        return ""
    skill = entry["skill"]
    source = entry.get("skill_source", "claude")
    return f"- 角色：{role}（本卡专用）——请加载 Skill「{skill}」（来源 {source}），按该 Skill 的方法完成本卡任务"


def _load_role_skills() -> dict:
    """加载角色→Skill 映射表（server/config/role-skills.yaml，SSOT）。"""
    import os
    import yaml as _yaml

    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "role-skills.yaml")
    try:
        with open(p, encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_executor_hint(project_prefix: str, title: str = "", card_context: str = "", card_content: str = "") -> str:
    """生成「执行提示」——给开发大模型（OpenCode）的专用指令。

    从 KB 提取项目专属的开发技能、常用命令、关键模块和守则，
    生成可执行的开发指令（而非信息罗列）。
    """
    registry = _load_registry()
    proj = registry.get(project_prefix, {})
    readme = _load_project_readme(project_prefix)

    name = readme.get("name") or proj.get("name", project_prefix)
    role = readme.get("role") or proj.get("role", "")
    mac2017_path = readme.get("mac2017_path") or ""
    paths = proj.get("paths", {})
    mac2017_path = mac2017_path or paths.get("mac2017", "")
    forbidden = readme.get("forbidden") or ""

    # KB 检索：开发技能
    kb_skill = _search_kb(project_prefix, title, focus="skill")
    # KB 检索：历史教训（避免踩坑）
    kb_lessons = _search_kb(project_prefix, title, focus="lesson")

    lines = [f"- 项目：{name}（{role}）"]
    if mac2017_path:
        # 2026-08-12 隔离升级：业务仓型项目禁止引导主目录开发，代码工作区由 Engine 派发注入
        if proj.get("taskable"):
            lines.append(
                f"- 项目仓（只读参考）：{mac2017_path}（Mac2017）——禁止在主仓目录切换卡分支或直接开发"
            )
            lines.append(
                "- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录"
            )
        else:
            lines.append(f"- 仓库路径：{mac2017_path}（Mac2017）")

    # 提取关联方案摘要
    related_field = _parse_related_field(card_content)
    if related_field:
        plan_ref = _parse_plan_ref(related_field)
        if plan_ref:
            plan_prefix, plan_num = plan_ref
            plan_summary = _get_plan_summary(plan_prefix, plan_num)
            if plan_summary:
                lines.append(f"- 关联方案摘要：{plan_summary}")

    # 提取项目线路/近况
    recent_lines = _get_project_recent_lines(project_prefix)
    if recent_lines:
        recent_str = "\n".join(f"  - {line}" for line in recent_lines)
        lines.append(f"- 项目线路/近况：\n{recent_str}")

    # KB 技能指南（优先：含具体命令和守则）
    if kb_skill:
        lines.append(f"- 开发技能与命令：\n{kb_skill}")
    else:
        # 回退：从 README 提取技术栈
        tech_stack = readme.get("tech_stack") or ""
        if tech_stack:
            lines.append(f"- 技术栈：{tech_stack}")
        key_modules = readme.get("key_modules") or ""
        if key_modules:
            lines.append(f"- 关键模块：\n{key_modules}")

    # 历史教训
    if kb_lessons:
        lines.append(f"- 历史教训（避免踩坑）：\n{kb_lessons}")

    if forbidden:
        lines.append(f"- 禁区：{forbidden}")
    role_hint = _role_skill_hint(card_content)
    if role_hint:
        lines.append(role_hint)
    if card_context:
        lines.append(f"- 补充说明：{card_context}")

    lines.append("- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支")
    lines.append("- 禁止：直推 main、写机审区/验收区、置已关闭")

    return "\n\n".join(lines)


def build_auditor_hint(project_prefix: str, title: str = "", card_context: str = "") -> str:
    """生成「机审提示」——给验收大模型（Claude Code）的专用指令。

    从 KB 提取项目专属的审查清单、历史教训和架构约束，
    生成可执行的审查指令（含具体审查重点和可修/不可修边界）。
    """
    registry = _load_registry()
    proj = registry.get(project_prefix, {})
    readme = _load_project_readme(project_prefix)

    name = readme.get("name") or proj.get("name", project_prefix)
    role = readme.get("role") or proj.get("role", "")
    forbidden = readme.get("forbidden") or ""

    # KB 检索：审查清单
    kb_review = _search_kb(project_prefix, title, focus="review")
    # KB 检索：历史教训
    kb_lessons = _search_kb(project_prefix, title, focus="lesson")

    lines = [f"- 审查项目：{name}（{role}）"]

    # KB 审查清单（优先：含具体审查维度、P0 重点、可修/不可修边界）
    if kb_review:
        lines.append(f"- 审查清单：\n{kb_review}")
    else:
        # 回退：通用审查指引
        lines.append("- 审查重点：代码实现质量、边界条件、异常处理、架构隐患")

    # 历史教训（告知审查时特别注意的坑）
    if kb_lessons:
        lines.append(f"- 历史教训（审查时重点关注）：\n{kb_lessons}")

    if forbidden:
        lines.append(f"- 架构约束/红线：{forbidden}")

    lines.append("- 处理原则：")
    lines.append("  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过")
    lines.append("  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出")
    lines.append("  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决")
    lines.append("  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因")
    lines.append("  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）")
    lines.append("- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭")
    lines.append("- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。")
    lines.append(
        "  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，"
    )
    lines.append("    打回原因注明缺失项；执行体补维护区后重试。")
    lines.append(
        "  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。"
    )

    return "\n\n".join(lines)


def inject_hints(
    card_path: str | Path,
    project_prefix: str,
    title: str = "",
    card_context: str = "",
    *,
    dry_run: bool = False,
) -> str:
    """读取卡文件，将「执行提示」和「机审提示」注入到对应段中。

    只替换空段或占位段（内容为纯占位文本的段），不覆盖已有内容。

    Args:
        card_path: 卡文件路径（或 "-" 从 stdin 读取）
        project_prefix: 项目前缀
        title: 任务卡标题
        card_context: 额外上下文
        dry_run: True 时只打印不写文件

    Returns:
        注入后的完整卡文本。
    """
    if card_path == "-" or str(card_path) == "-":
        content = sys.stdin.read()
        card_path_obj: Path | None = None
    else:
        card_path_obj = Path(card_path)
        if not card_path_obj.is_file():
            logger.warning("卡文件不存在: %s", card_path_obj)
            return ""
        content = card_path_obj.read_text(encoding="utf-8")

    executor_hint = build_executor_hint(project_prefix, title, card_context, card_content=content)
    auditor_hint = build_auditor_hint(project_prefix, title, card_context)

    # 替换「## 执行提示」段：只替换空段或纯占位段
    executor_placeholder = re.compile(r"(^##\s*执行提示.*?\n)(.*?)(?=\n^##\s|\Z)", re.DOTALL | re.MULTILINE)
    exec_match = executor_placeholder.search(content)
    if exec_match:
        existing = exec_match.group(2).strip()
        # 只替换空段或纯占位段（不含实际内容）
        if not existing or existing.startswith("（中枢在出卡时注入"):
            content = executor_placeholder.sub(
                lambda m: m.group(1) + "\n" + executor_hint + "\n",
                content,
                count=1,
            )

    # 替换「## 机审提示」段
    auditor_placeholder = re.compile(r"(^##\s*机审提示.*?\n)(.*?)(?=\n^##\s|\Z)", re.DOTALL | re.MULTILINE)
    audit_match = auditor_placeholder.search(content)
    if audit_match:
        existing = audit_match.group(2).strip()
        if not existing or existing.startswith("（中枢在出卡时注入"):
            content = auditor_placeholder.sub(
                lambda m: m.group(1) + "\n" + auditor_hint + "\n",
                content,
                count=1,
            )

    if dry_run:
        print(content)
        return content

    if card_path_obj is not None:
        card_path_obj.write_text(content, encoding="utf-8")
        logger.info("提示段已注入: %s", card_path_obj)

    return content


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="CCC 中枢 Prompt 注入器 — 生成 LLM 专用提示段并注入到任务卡",
    )
    parser.add_argument(
        "card_path",
        nargs="?",
        default="-",
        help="任务卡文件路径（或 '-' 从 stdin 读取；--executor-only/--auditor-only 模式可省略）",
    )
    parser.add_argument(
        "--project",
        "-p",
        required=True,
        help="项目前缀（如 mx、ccc、hp）",
    )
    parser.add_argument(
        "--title",
        "-t",
        default="",
        help="任务卡标题（用于 KB 检索）",
    )
    parser.add_argument(
        "--context",
        "-c",
        default="",
        help="额外上下文",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="只打印注入后的卡内容，不写文件",
    )
    parser.add_argument(
        "--executor-only",
        action="store_true",
        help="只生成执行提示",
    )
    parser.add_argument(
        "--auditor-only",
        action="store_true",
        help="只生成机审提示",
    )

    args = parser.parse_args()

    card_content = ""
    if args.card_path and args.card_path != "-":
        card_path_obj = Path(args.card_path)
        if card_path_obj.is_file():
            try:
                card_content = card_path_obj.read_text(encoding="utf-8")
            except Exception:
                pass

    if args.executor_only:
        print(build_executor_hint(args.project, args.title, args.context, card_content=card_content))
        return

    if args.auditor_only:
        print(build_auditor_hint(args.project, args.title, args.context))
        return

    result = inject_hints(
        args.card_path,
        args.project,
        args.title,
        args.context,
        dry_run=args.dry_run,
    )

    if not result:
        sys.exit(1)


if __name__ == "__main__":
    main()
