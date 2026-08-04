"""CCC 知识库索引构建器。

从 knowledge/（seed JSON + domains 目录）解析文档，构建 BM25 可检索索引。
索引产物输出到 knowledge/.index/（已 gitignore）。

T51 增量重建：索引文件（documents.json, version 2）携带源文件 mtime 表，
``incremental_index`` 只重扫 mtime 变化的源文件，替换全量重建；无变化时零扫。

用法::

    reindex(knowledge_root, index_dir)      # 全量重建（首次 / --reindex）
    incremental_index(root, index_dir)      # 增量重建（只扫变化文档）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ── 域命名归一 ──

# seed JSON 的 section 带数字前缀（01-nodes-paths），与域过滤名（nodes-paths）不一致；
# 统一归一为四域名，保证 domain 过滤与用例集断言一致。
_SECTION_ALIASES = {
    "01-nodes-paths": "nodes-paths",
    "02-project-metadata": "projects",
    "03-key-decisions": "decisions",
    "04-lessons": "lessons",
}


def normalize_section(section: str) -> str:
    """将 seed JSON 的数字前缀 section 归一为域过滤名。"""
    return _SECTION_ALIASES.get(section, section)


# ── 文档模型 ──

class KbDocument:
    """知识库中的一个文档条目。"""

    __slots__ = ("doc_id", "section", "content", "source")

    def __init__(self, doc_id: str, section: str, content: str, source: str) -> None:
        self.doc_id = doc_id
        self.section = section
        self.content = content
        self.source = source

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.doc_id,
            "section": self.section,
            "content": self.content,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> KbDocument:
        return cls(
            doc_id=d["id"],
            section=d["section"],
            content=d["content"],
            source=d["source"],
        )


# ── 文本清洗 ──

def _clean_text(text: str) -> str:
    """去除 markdown 标记、多余空白，返回纯文本。"""
    # 去除代码块
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # 去除行内代码
    text = re.sub(r"`[^`]+`", "", text)
    # 去除 markdown 链接，保留显示文本
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 去除表格装饰线
    text = re.sub(r"\|[\s\-:]+\|", " ", text)
    # 去除 markdown 标题标记
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 合并空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── 解析器 ──

def _parse_seed_json(filepath: Path) -> list[KbDocument]:
    """解析 seed JSON 文件（ccc-kb-seed-v1 schema），产出文档列表。"""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    section = normalize_section(data.get("section", filepath.stem))
    docs: list[KbDocument] = []
    base_id = filepath.stem  # e.g. "01-nodes-paths"

    # 通用 JSON 遍历：展平所有文本内容
    def _collect(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            # 跳过 schema 元字段
            skip_keys = {"schema", "section", "updated_at", "source", "note"}
            for k, v in obj.items():
                if k in skip_keys:
                    continue
                child_path = f"{path}.{k}" if path else k
                if isinstance(v, (str, int, float, bool)):
                    pass  # 叶子值在上一层处理
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            # 提取 id/title/name 作为文档标识
                            ident = (
                                item.get("id")
                                or item.get("title")
                                or item.get("name")
                                or f"{k}_{i}"
                            )
                            # 展平为文本
                            parts = []
                            for vk, vv in item.items():
                                if vk in skip_keys:
                                    continue
                                if isinstance(vv, (str, int, float, bool)):
                                    parts.append(f"{vk}: {vv}")
                                elif isinstance(vv, list):
                                    parts.append(f"{vk}: {'; '.join(str(x) for x in vv)}")
                                elif isinstance(vv, dict):
                                    parts.append(f"{vk}: {json.dumps(vv, ensure_ascii=False)}")
                            content = _clean_text(" | ".join(parts))
                            if content:
                                docs.append(KbDocument(
                                    doc_id=f"{base_id}::{ident}",
                                    section=section,
                                    content=content,
                                    source=str(filepath),
                                ))
                        else:
                            _collect(item, child_path)
                elif isinstance(v, dict):
                    _collect(v, child_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _collect(item, f"{path}[{i}]")

    _collect(data)

    # 顶层 note 也编入
    note = data.get("note", "")
    if note:
        docs.append(KbDocument(
            doc_id=f"{base_id}::note",
            section=section,
            content=_clean_text(note),
            source=str(filepath),
        ))

    return docs


def _parse_domain_markdown(filepath: Path) -> list[KbDocument]:
    """解析 domains 目录下的 markdown seed 文件，按 ## 标题分段。"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    section = normalize_section(filepath.parent.name)  # e.g. "nodes-paths"
    base_id = f"domains::{section}"

    # 按 ## 二级标题分段
    parts = re.split(r"\n(?=##\s)", text)
    docs: list[KbDocument] = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        # 提取标题
        title_match = re.match(r"##\s+(.+)", part)
        title = title_match.group(1).strip() if title_match else f"section_{i}"
        content = _clean_text(part)
        if content:
            safe_title = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "_", title)
            docs.append(KbDocument(
                doc_id=f"{base_id}::{safe_title}",
                section=section,
                content=content,
                source=str(filepath),
            ))

    return docs


# ── 源文件扫描 ──

def scan_source_files(knowledge_root: str | Path) -> list[Path]:
    """扫描知识库源文件（seed JSON + domains/*.md），返回有序绝对路径列表。"""
    root = Path(knowledge_root).resolve()
    files: list[Path] = []

    seed_dir = root / "seed"
    if seed_dir.is_dir():
        files.extend(sorted(seed_dir.glob("*.json")))

    domains_dir = root / "domains"
    if domains_dir.is_dir():
        for domain_dir in sorted(domains_dir.iterdir()):
            if domain_dir.is_dir():
                files.extend(sorted(domain_dir.glob("*.md")))

    return files


def _parse_source_file(filepath: Path) -> list[KbDocument]:
    """按扩展名解析单个源文件为文档列表。"""
    if filepath.suffix == ".json":
        return _parse_seed_json(filepath)
    return _parse_domain_markdown(filepath)


def _source_mtimes(files: list[Path]) -> dict[str, float]:
    """{源文件绝对路径: mtime}。"""
    return {str(f): f.stat().st_mtime for f in files}


# ── 索引构建 ──

def build_index(knowledge_root: str | Path) -> list[KbDocument]:
    """从 knowledge/ 构建文档列表（全量）。

    扫描 seed JSON 与 domains 目录下的 markdown 文件，返回扁平文档列表。
    """
    docs: list[KbDocument] = []
    for f in scan_source_files(knowledge_root):
        docs.extend(_parse_source_file(f))
    return docs


def save_index(docs: list[KbDocument], index_dir: str | Path, mtimes: dict[str, float] | None = None) -> None:
    """将文档列表保存为索引 JSON 文件（version 2，携带源文件 mtime 表）。

    Args:
        docs: 文档列表
        index_dir: 索引输出目录
        mtimes: {源文件绝对路径: mtime}；增量重建的判定依据
    """
    out = Path(index_dir)
    out.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "2",
        "mtimes": mtimes or {},
        "documents": [d.to_dict() for d in docs],
    }
    (out / "documents.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_index(index_dir: str | Path) -> list[KbDocument]:
    """从索引目录加载文档列表（兼容 version 1/2）。"""
    index_file = Path(index_dir) / "documents.json"
    if not index_file.is_file():
        return []
    data = json.loads(index_file.read_text(encoding="utf-8"))
    return [KbDocument.from_dict(d) for d in data.get("documents", [])]


def load_mtimes(index_dir: str | Path) -> dict[str, float] | None:
    """加载索引文件的源文件 mtime 表。

    Returns:
        {源文件绝对路径: mtime}；version 1（无 mtime 表）返回 None
    """
    index_file = Path(index_dir) / "documents.json"
    if not index_file.is_file():
        return None
    data = json.loads(index_file.read_text(encoding="utf-8"))
    mtimes = data.get("mtimes")
    return dict(mtimes) if isinstance(mtimes, dict) else None


def reindex(knowledge_root: str | Path, index_dir: str | Path) -> int:
    """全量重建索引（首次 / --reindex）。

    Args:
        knowledge_root: knowledge/ 目录路径
        index_dir: 索引输出目录

    Returns:
        索引文档数量
    """
    files = scan_source_files(knowledge_root)
    docs = build_index(knowledge_root)
    save_index(docs, index_dir, _source_mtimes(files))
    return len(docs)


def incremental_index(knowledge_root: str | Path, index_dir: str | Path) -> tuple[int, list[str]]:
    """增量重建索引：只重扫 mtime 变化的源文件，替换全量重建。

    - 无变化 → 直接复用现有索引（返回 ``(现有文档数, [])``，零文件读取）。
    - 有变化 → 保留未变源文件的既有文档，只重解析变化文件；删除源移除其文档。
    - 无既有索引 / 既有索引为 version 1（无 mtime 表）→ 退化为全量重建。

    Args:
        knowledge_root: knowledge/ 目录路径
        index_dir: 索引输出目录

    Returns:
        ``(索引文档数, 实际重扫的源文件路径列表)``
    """
    files = scan_source_files(knowledge_root)
    current_m = _source_mtimes(files)
    existing_m = load_mtimes(index_dir)
    existing_docs = load_index(index_dir)

    # 无既有索引（或 v1 无 mtime 表）→ 全量重建
    if not existing_docs or not existing_m:
        docs = build_index(knowledge_root)
        save_index(docs, index_dir, current_m)
        return len(docs), [str(f) for f in files]

    # 判定变化源
    changed = [f for f in files if existing_m.get(str(f)) != current_m.get(str(f))]
    deleted = [src for src in existing_m if src not in current_m]

    if not changed and not deleted:
        return len(existing_docs), []

    # 保留未变源文件的既有文档（按 source 分组）
    by_source: dict[str, list[KbDocument]] = {}
    for d in existing_docs:
        by_source.setdefault(d.source, []).append(d)

    new_docs: list[KbDocument] = []
    for src, docs in by_source.items():
        if src not in deleted and existing_m.get(src) == current_m.get(src):
            new_docs.extend(docs)

    # 只重解析变化源文件
    for f in changed:
        new_docs.extend(_parse_source_file(f))

    save_index(new_docs, index_dir, current_m)
    return len(new_docs), [str(f) for f in changed]
