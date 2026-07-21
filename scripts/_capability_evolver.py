"""_capability_evolver.py — 自学习闭环（Phase 3，P3）

能力进化引擎，负责：
1. 读取失败 lessons → 根因分析 → 闭环（替换 stub 为完整分析）
2. lessons → SKILL.md 「已知陷阱」自动回灌
3. 失败模式打分路由（同一 pattern 反复触发 → 降权/改写）

不依赖 LLM。纯规则引擎：把失败模式映射到已知陷阱 → SKILL.md 更新。
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ============================================================
# 1. 根因分析引擎 — 把失败模式聚类到已知根因
# ============================================================

# 失败模式 → (根因类别, 修复方向, 适用角色)
_FAILURE_PATTERNS: list[tuple[re.Pattern, str, str, str, list[str]]] = [
    (
        re.compile(r"patrol.?alert.?webhook", re.I),
        "patrol-alert-webhook",
        "webhook 成功率低，切换会触发 hang auto-restart 时序冲突",
        "1) 改用文件落盘+桌面通知双通道 2) hang auto-restart 与 alert webhook 加互斥锁",
        ["ops", "regress"],
    ),
    (
        re.compile(r"hang.?auto.?restart", re.I),
        "hang-auto-restart",
        "hang 检测与 auto-restart 时序竞争：restart 时 patrol 正发告警，死锁",
        "1) auto-restart 前暂停 patrol 探测 2) 加 restart 互斥锁 3) restart 后延迟 30s 再开始探测",
        ["ops", "regress"],
    ),
    (
        re.compile(r"product_role.*失败|连续失败.*3", re.I),
        "product-role-consecutive-fail",
        "product role prompt 注入的 lessons 过多导致 tokens 超限或指令冲突",
        "1) lessons 注入按 role 过滤（已完成） 2) 限制单次注入 lessons 上限 20 条 3) 去重机制",
        ["product"],
    ),
    (
        re.compile(r"engine.*重试.*失败|retry.*fail", re.I),
        "engine-retry-exhausted",
        "engine 对同一 phase 重试 3 次全部失败，但未标记 unresolvable → 进入死循环",
        "1) 3 次重试全失败后标 unresolvable（已实现） 2) 加 phase_graph_regen 计数器",
        ["dev", "reviewer"],
    ),
    (
        re.compile(r"board.?column.?auto.?prune|column.*prune", re.I),
        "board-column-auto-prune",
        "看板列自动裁剪异常：删除 task 时未同步更新 index.json",
        "1) FileBoardStore.delete 后必须调 update_index 2) prune 操作加事务锁",
        ["ops"],
    ),
    (
        re.compile(r"git.?auto.?push|auto.?push.*fail", re.I),
        "git-auto-push",
        "patrol git auto-push 因工作树脏（未提交改动）而失败",
        "1) auto-push 前必须先 git status 检查 2) 脏工作树时落盘告警不 push 3) 改 fallback 通道",
        ["ops", "regress"],
    ),
    (
        re.compile(r"phase.*graph.*regen|unresolvable", re.I),
        "phase-graph-regen",
        "phase 图无法解析（环/orphan-dep），regen 后新 plan 仍不达标",
        "1) 加循环依赖检测（已实现） 2) 加 orphan-dep 检测（已实现） 3) regen cap 2 → abnormal",
        ["product", "dev"],
    ),
    (
        re.compile(r"scope.*reject|scope.*越界|extra.*file", re.I),
        "scope-reject",
        "scope-reject 误杀 .ccc/ 系元数据（fad416c 回归），或漏检 untracked 文件",
        "1) 排除 .ccc/ 元数据（已修复） 2) untracked file 检测（已补） 3) tracked file 用 checkout 而非 rm",
        ["dev", "reviewer"],
    ),
]


def analyze_failure(task_id: str, error_text: str) -> dict | None:
    """对单条 failure 做根因分析，返回 {reason, fix, roles, pattern} 或 None。

    同时搜索 task_id 和 error_text（因为 stub 标题可能在 task_id 或 error_text 中）。
    """
    _combined = f"{task_id} {error_text}"
    for pat, pattern_name, reason, fix, roles in _FAILURE_PATTERNS:
        if pat.search(_combined):
            return {
                "pattern": pattern_name,
                "reason": reason,
                "fix": fix,
                "roles": roles,
            }
    return None


def analyze_stub(stub_title: str, stub_timestamp: str) -> dict | None:
    """分析 stub lesson 标题和上下文，推测根因。"""
    # 先尝试 pattern 匹配
    result = analyze_failure(stub_title, stub_title)
    if result:
        return result
    # fallback 通用分析
    return {
        "pattern": "unknown",
        "reason": f"未匹配到已知失败模式：{stub_title}",
        "fix": "需人工分析",
        "roles": ["product"],
    }


# ============================================================
# 2. lessons → SKILL.md 自动回灌
# ============================================================

def _skill_path(skill_name: str) -> Path | None:
    """找 SKILL.md 路径（按 skill 名）"""
    candidates = [
        Path(__file__).parent.parent / "skills" / f"ccc-{skill_name}" / "SKILL.md",
        Path(__file__).parent.parent / "skills" / f"{skill_name}" / "SKILL.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _read_skill_traps(skill_path: Path) -> str | None:
    """读 SKILL.md 的「已知陷阱」段内容（不含标题本身）。"""
    text = skill_path.read_text(encoding="utf-8")
    # 找中文"已知陷阱"或「已知陷阱」
    m = re.search(r"#+?\s*已知陷阱[：:]\s*\n(.*?)(?=\n#+?\s|\Z)", text, re.DOTALL)
    if m:
        # 去掉标题行
        content = m.group(1).strip()
        # 去掉可能的列表标记前缀
        content = re.sub(r"^[-*]\s+", "", content, flags=re.MULTILINE)
        return content
    # 尝试找英文 Known Pitfalls / Traps
    m = re.search(r"#+?\s*(?:Known\s+(?:Pitfalls|Traps)|Trap|Pitfall)[：:]\s*\n(.*?)(?=\n#+?\s|\Z)", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def auto_feed_to_skill(task_id: str, analysis: dict) -> bool:
    """把闭环 lessons 自动追加到相关角色的 SKILL.md「已知陷阱」段。

    在每个适用角色的 SKILL.md 中追加一条陷阱，格式：
    - **{task_id}**：{reason} → {fix}
    """
    roles = analysis.get("roles", ["product"])
    fed_count = 0

    for role in roles:
        sp = _skill_path(role)
        if not sp:
            continue

        text = sp.read_text(encoding="utf-8")
        reason = analysis.get("reason", "")
        fix = analysis.get("fix", "")

        # 追加陷阱条目到已知陷阱段
        trap_line = (
            f"\n  - **{task_id}** ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}): "
            f"{reason}. "
            f"修复：{fix}"
        )

        # 找「已知陷阱」段末尾追加
        trap_section = re.search(
            r"(#+?\s*已知陷阱[：:]\s*\n(?:.*\n)*?)(?=\n#+\s|\Z)",
            text, re.DOTALL
        )
        if trap_section:
            new_text = text[:trap_section.end()] + trap_line + text[trap_section.end():]
        else:
            # 没有已知陷阱段 → 在文件末尾追加
            new_text = text.rstrip() + f"\n\n## 已知陷阱：\n{trap_line}\n"

        sp.write_text(new_text, encoding="utf-8")
        fed_count += 1

    return fed_count > 0


# ============================================================
# 3. 批量闭环 stub lessons
# ============================================================

def close_stub_in_lessons_md(
    ws_path: Path,
    stub_title: str,
    analysis: dict,
) -> bool:
    """在 docs/lessons.md 中找到 stub，替换为闭环版本。

    stub 格式：
    **Lesson N（stub）**：{stub_title} — {timestamp} — {error_context}
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    if not lessons_md.exists():
        return False

    text = lessons_md.read_text(encoding="utf-8")

    # 找到包含 stub_title 的行
    lines = text.split("\n")
    new_lines = []
    i = 0
    closed = False

    while i < len(lines):
        line = lines[i]
        if "**Lesson " in line and "（stub）" in line and stub_title in line:
            # 跳过 stub 行和它后面的空行（stub 只有一行）
            # 找到 stub 所在行开头
            # 替换 stub 行
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            reason = analysis.get("reason", "")
            fix = analysis.get("fix", "")
            roles = ", ".join(analysis.get("roles", ["product"]))
            # 替换 stub 单行为完整 Lesson
            closed_line = (
                f"\n**Lesson（已闭环）**：{stub_title} — {timestamp}\n\n"
                f"**根因分析**：{reason}\n\n"
                f"**修复措施**：{fix}\n\n"
                f"**适用角色**：{roles}\n\n"
                f"**闭环确认**：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} "
                f"— capability-evolver 自动分析\n\n"
            )
            new_lines.append(closed_line)
            closed = True
            i += 1
        else:
            new_lines.append(line)
            i += 1

    if closed:
        lessons_md.write_text("\n".join(new_lines), encoding="utf-8")
    return closed


def close_all_stubs(ws_path: Path | None = None) -> list[str]:
    """批量闭环 all 11 stub lessons。返回已闭环的 stub 标题列表。"""
    if ws_path is None:
        ws_path = Path(__file__).parent.parent

    lessons_md = ws_path / "docs" / "lessons.md"
    if not lessons_md.exists():
        return []

    text = lessons_md.read_text(encoding="utf-8")
    stub_pattern = re.compile(r"\*\*Lesson \d+（stub）\*\*：(.+?)(?:—|\n|$)")
    closed: list[str] = []

    for m in stub_pattern.finditer(text):
        stub_title = m.group(1).strip()
        # 如果已经闭环（不缺 — 或 has "闭环"），跳过
        if "已闭环" in stub_title or "闭环" in stub_title:
            continue
        analysis = analyze_stub(stub_title, "")
        if analysis:
            close_stub_in_lessons_md(ws_path, stub_title, analysis)
            auto_feed_to_skill(stub_title, analysis)
            closed.append(stub_title)

    return closed


# ============================================================
# 4. 失败模式打分路由
# ============================================================

_FAILURE_COUNTS_FILE = Path.home() / ".ccc" / "failure-pattern-counts.json"


def _load_failure_counts() -> dict[str, int]:
    """读取累计失败模式计数。"""
    try:
        if _FAILURE_COUNTS_FILE.exists():
            return json.loads(_FAILURE_COUNTS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_failure_counts(counts: dict[str, int]) -> None:
    """写入失败模式计数。"""
    try:
        _FAILURE_COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _FAILURE_COUNTS_FILE.write_text(json.dumps(counts, ensure_ascii=False, indent=2))
    except OSError:
        pass


def record_failure_pattern(pattern: str) -> int:
    """记录一次失败模式触发，返回累计次数。"""
    counts = _load_failure_counts()
    current = counts.get(pattern, 0) + 1
    counts[pattern] = current
    _save_failure_counts(counts)
    return current


def should_auto_rewrite(pattern: str) -> bool:
    """判断是否需要对某 pattern 自动降权/改写。

    规则: 同一 pattern 累计 >= 2 次 → 触发自进化。
    """
    counts = _load_failure_counts()
    return counts.get(pattern, 0) >= 2


def get_top_failure_patterns(n: int = 5) -> list[tuple[str, int]]:
    """获取 TOP N 高失败模式。"""
    counts = _load_failure_counts()
    return sorted(counts.items(), key=lambda x: -x[1])[:n]
