"""CCC lessons pipeline — 记录失败教训供 product 角色参考 (v0.31)"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _lessons_dir(ws_path: Path) -> Path:
    d = ws_path / ".ccc" / "lessons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_failure(
    ws_path: Path, task_id: str, phase: str | int, error: str, analysis: str = ""
) -> dict:
    """记录一次任务失败到 .ccc/lessons/{task_id}.json"""
    record = {
        "task_id": task_id,
        "phase": phase,
        "error": error,
        "analysis": analysis,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "fixed": False,
    }
    out = _lessons_dir(ws_path) / f"{task_id}.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


_STUB_ANALYSIS_MARKERS = (
    "未匹配到已知失败模式",
)


def _is_stub_lesson(item: dict) -> bool:
    """v0.42: analysis 空或 stub 文案 → 不注入 product prompt。"""
    analysis = (item.get("analysis") or "").strip()
    if not analysis:
        return True
    return any(m in analysis for m in _STUB_ANALYSIS_MARKERS)


def get_recent_lessons(ws_path: Path, count: int = 50) -> list[dict]:
    """读取 .ccc/lessons/ 下所有 json，按 timestamp 排序，返回最近 count 条。

    v0.42: 过滤 stub（空 analysis / 「未匹配到已知失败模式」）。
    """
    lessons_dir = ws_path / ".ccc" / "lessons"
    if not lessons_dir.is_dir():
        return []
    items: list[dict] = []
    for fp in lessons_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text())
            if isinstance(data, dict) and not _is_stub_lesson(data):
                items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[:count]


def mark_fixed(ws_path: Path, task_id: str) -> bool:
    """标记某条教训已修复（fixed: true）。"""
    fp = ws_path / ".ccc" / "lessons" / f"{task_id}.json"
    if not fp.exists():
        return False
    try:
        data = json.loads(fp.read_text())
        data["fixed"] = True
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return True
    except (json.JSONDecodeError, OSError):
        return False


# v0.32: 扫描 docs/lessons.md 中所有 `## Lesson N` 标题，仅行首匹配（避免正文误命中）。
_LESSON_HEADING_RE = re.compile(r"^## Lesson (\d+)")


def _next_lesson_number(ws_path: Path) -> int:
    """扫描 docs/lessons.md 找到最新 Lesson 编号，返回下一个。

    没有匹配到任何 Lesson 时返回 1。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    if not lessons_md.exists():
        return 1
    max_n = 0
    for line in lessons_md.read_text().split("\n"):
        m = _LESSON_HEADING_RE.match(line.strip())
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return max_n + 1


def auto_append_lesson_md(
    ws_path: Path,
    task_id: str,
    phase: int | str | None,
    error: str,
) -> None:
    """自动追加一条 Lesson 记录到 docs/lessons.md。

    格式对标已有 Lesson 结构（标题 + 元信息 + 自检提示），
    内容完全由调用方提供（不分析根因或修复方案）。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    n = _next_lesson_number(ws_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    phase_str = str(phase) if phase is not None else "N/A"
    entry = (
        "\n---\n"
        f"\n## Lesson {n}：{task_id} 进入异常状态\n"
        f"\n**项目**：`{ws_path}` | **Phase**：{phase_str} | **时间**：{timestamp}\n"
        f"\n**失败原因**：{error}\n"
        f"\n**待分析**：由 product_role 后续补充根因和修复方案\n"
    )
    with open(lessons_md, "a", encoding="utf-8") as f:
        f.write(entry)


# ── F4-2: success lessons by topic ───────────────────────────────────

# 长词优先；title 含左侧关键词 → 右侧 topic slug（不做 NLP）
_TOPIC_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
    ("断线恢复", "disconnect-recovery"),
    ("投递三态", "delivery-tri-state"),
    ("断线", "disconnect"),
    ("投递", "delivery"),
    ("扇出", "fanout"),
    ("门禁", "gate"),
    ("验收", "acceptance"),
    ("回测", "regress"),
    ("归档", "archive"),
    ("上下文", "context"),
    ("流畅", "fluency"),
    ("disconnect", "disconnect"),
    ("delivery", "delivery"),
    ("fanout", "fanout"),
)

_SUCCESS_SECTION_RE = re.compile(
    r"^## success · (?P<ts>\S+)\s*\n(?P<body>.*?)(?=^## success · |\Z)",
    re.MULTILINE | re.DOTALL,
)
_FIELD_RE = re.compile(
    r"^\s*[-*]\s*\*\*(?P<k>task_id|topic|summary)\*\*\s*:\s*(?P<v>.*?)\s*$",
    re.MULTILINE,
)


def sanitize_topic(raw: str) -> str:
    """文件名安全 topic：小写、空白→-、保留字母数字与 unicode 词字符。"""
    s = (raw or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w\-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    return (s[:64] or "general")


def extract_topic(title: str, tag: str | None = None) -> str:
    """从 title 关键词或 tag 提取 topic slug。"""
    if tag and str(tag).strip():
        tag_s = str(tag).strip()
        for kw, slug in _TOPIC_KEYWORD_MAP:
            if kw.lower() in tag_s.lower() or kw in tag_s:
                return sanitize_topic(slug)
        return sanitize_topic(tag_s)
    text = title or ""
    lower = text.lower()
    for kw, slug in _TOPIC_KEYWORD_MAP:
        if kw.lower() in lower or kw in text:
            return sanitize_topic(slug)
    return sanitize_topic(text) if text.strip() else "general"


def record_success(
    ws_path: Path, task_id: str, topic: str, summary: str
) -> dict:
    """写/追加 `.ccc/lessons/<topic>.md` 成功经验段（人可读 + 机可注入）。"""
    topic_slug = sanitize_topic(topic)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    record = {
        "task_id": task_id,
        "topic": topic_slug,
        "summary": summary or "",
        "timestamp": ts,
        "kind": "success",
    }
    out = _lessons_dir(ws_path) / f"{topic_slug}.md"
    section = (
        f"## success · {ts}\n\n"
        f"- **task_id**: {task_id}\n"
        f"- **topic**: {topic_slug}\n"
        f"- **summary**: {summary or ''}\n\n"
    )
    if out.is_file():
        existing = out.read_text(encoding="utf-8", errors="replace")
        if not existing.endswith("\n"):
            existing += "\n"
        out.write_text(existing + section, encoding="utf-8")
    else:
        header = f"# Success lessons · {topic_slug}\n\n"
        out.write_text(header + section, encoding="utf-8")
    return record


def _parse_success_md(path: Path) -> list[dict]:
    """解析单个 topic markdown 中的 success 段。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    file_topic = path.stem
    items: list[dict] = []
    for m in _SUCCESS_SECTION_RE.finditer(text):
        fields = {fm.group("k"): fm.group("v").strip() for fm in _FIELD_RE.finditer(m.group("body"))}
        items.append(
            {
                "task_id": fields.get("task_id", ""),
                "topic": fields.get("topic") or file_topic,
                "summary": fields.get("summary", ""),
                "timestamp": m.group("ts"),
                "kind": "success",
                "source": path.name,
            }
        )
    return items


def get_lessons_by_topic(
    ws_path: Path, topic: str, count: int = 5
) -> list[dict]:
    """按文件名 / 段落关键词匹配成功 lessons，返回最近 count 条。"""
    lessons_dir = ws_path / ".ccc" / "lessons"
    if not lessons_dir.is_dir():
        return []
    topic_slug = sanitize_topic(topic)
    if not topic_slug:
        return []
    items: list[dict] = []
    seen_paths: set[Path] = set()

    preferred = lessons_dir / f"{topic_slug}.md"
    if preferred.is_file():
        items.extend(_parse_success_md(preferred))
        seen_paths.add(preferred.resolve())

    try:
        md_files = sorted(lessons_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        md_files = []

    for fp in md_files:
        try:
            resolved = fp.resolve()
        except OSError:
            continue
        if resolved in seen_paths:
            continue
        name_match = topic_slug in fp.stem.lower() or fp.stem.lower() in topic_slug
        body_match = False
        if not name_match:
            try:
                body = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lower = body.lower()
            body_match = topic_slug in lower or any(
                kw.lower() in lower for kw, slug in _TOPIC_KEYWORD_MAP if slug == topic_slug
            )
        if name_match or body_match:
            items.extend(_parse_success_md(fp))
            seen_paths.add(resolved)

    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items[: max(0, int(count))]
