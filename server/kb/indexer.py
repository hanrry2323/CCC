"""CCC 知识库索引构建器。

从 knowledge/（seed JSON + domains 目录）解析文档，构建 BM25 可检索索引。
索引产物输出到 knowledge/.index/（已 gitignore），支持 reindex 重建。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


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

    section = data.get("section", filepath.stem)
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

    section = filepath.parent.name  # e.g. "nodes-paths"
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


# ── 索引构建 ──

def build_index(knowledge_root: str | Path) -> list[KbDocument]:
    """从 knowledge/ 构建文档列表。

    扫描 seed JSON 与 domains 目录下的 markdown 文件，返回扁平文档列表。
    """
    root = Path(knowledge_root).resolve()
    docs: list[KbDocument] = []

    # 1. seed JSON
    seed_dir = root / "seed"
    if seed_dir.is_dir():
        for f in sorted(seed_dir.glob("*.json")):
            docs.extend(_parse_seed_json(f))

    # 2. domains markdown
    domains_dir = root / "domains"
    if domains_dir.is_dir():
        for domain_dir in sorted(domains_dir.iterdir()):
            if domain_dir.is_dir():
                for f in sorted(domain_dir.glob("*.md")):
                    docs.extend(_parse_domain_markdown(f))

    return docs


def save_index(docs: list[KbDocument], index_dir: str | Path) -> None:
    """将文档列表保存为索引 JSON 文件。"""
    out = Path(index_dir)
    out.mkdir(parents=True, exist_ok=True)

    data = {
        "version": "1",
        "documents": [d.to_dict() for d in docs],
    }
    (out / "documents.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_index(index_dir: str | Path) -> list[KbDocument]:
    """从索引目录加载文档列表。"""
    index_file = Path(index_dir) / "documents.json"
    if not index_file.is_file():
        return []
    data = json.loads(index_file.read_text(encoding="utf-8"))
    return [KbDocument.from_dict(d) for d in data.get("documents", [])]


def reindex(knowledge_root: str | Path, index_dir: str | Path) -> int:
    """重建索引。

    Args:
        knowledge_root: knowledge/ 目录路径
        index_dir: 索引输出目录

    Returns:
        索引文档数量
    """
    docs = build_index(knowledge_root)
    save_index(docs, index_dir)
    return len(docs)
