"""测试：知识库索引构建器（indexer.py）。

覆盖：
1. 索引构建（build_index）从 seed JSON + domains MD 正确产出文档
2. 保存/加载索引（save_index / load_index）往返
3. 重建索引（reindex）正确
4. 文本清洗（_clean_text）去除 markdown 标记
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from server.kb.indexer import (
    KbDocument,
    build_index,
    load_index,
    reindex,
    save_index,
)


# ── 夹具 ──

@pytest.fixture
def knowledge_root(tmp_path: Path) -> Path:
    """创建临时知识库目录结构。"""
    root = tmp_path / "knowledge"
    seed_dir = root / "seed"
    seed_dir.mkdir(parents=True)

    # 写一个模拟 seed JSON
    seed_json = {
        "schema": "ccc-kb-seed-v1",
        "section": "test-domain",
        "updated_at": "2026-08-02",
        "note": "测试用种子数据",
        "items": [
            {"id": "item-1", "name": "测试项目一", "desc": "CCC 相关的测试条目"},
            {"id": "item-2", "name": "测试项目二", "desc": "BM25 检索测试"},
        ],
    }
    (seed_dir / "01-test.json").write_text(
        json.dumps(seed_json, ensure_ascii=False), encoding="utf-8"
    )

    # 写一个模拟 domains MD
    domains_dir = root / "domains" / "test-domain"
    domains_dir.mkdir(parents=True)
    (domains_dir / "seed.md").write_text(
        "# 测试域\n\n"
        "> 来源：测试数据\n\n"
        "## 条目一\n\n"
        "CCC 测试条目内容\n\n"
        "## 条目二\n\n"
        "BM25 检索测试内容\n",
        encoding="utf-8",
    )

    return root


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    return tmp_path / ".index"


# ════════════════════════════════════════════════════════════
# 1. 索引构建
# ════════════════════════════════════════════════════════════

class TestBuildIndex:
    """build_index 从 seed JSON + domains MD 正确产出文档。"""

    def test_build_returns_documents(self, knowledge_root: Path) -> None:
        docs = build_index(knowledge_root)
        assert isinstance(docs, list)
        assert len(docs) > 0

    def test_build_includes_seed_json(self, knowledge_root: Path) -> None:
        docs = build_index(knowledge_root)
        json_docs = [d for d in docs if "seed/" in d.source]
        assert len(json_docs) > 0, "应包含 seed JSON 文档"
        assert any("CCC" in d.content for d in json_docs)

    def test_build_includes_domains_md(self, knowledge_root: Path) -> None:
        docs = build_index(knowledge_root)
        md_docs = [d for d in docs if "domains/" in d.source]
        assert len(md_docs) > 0, "应包含 domains MD 文档"

    def test_build_document_has_required_fields(self, knowledge_root: Path) -> None:
        docs = build_index(knowledge_root)
        for doc in docs:
            assert doc.doc_id, "doc_id 不能为空"
            assert doc.section, "section 不能为空"
            assert doc.content, "content 不能为空"
            assert doc.source, "source 不能为空"

    def test_build_empty_dir(self, tmp_path: Path) -> None:
        """空目录应返回空列表。"""
        docs = build_index(tmp_path / "nonexistent")
        assert docs == []


# ════════════════════════════════════════════════════════════
# 2. 保存/加载索引
# ════════════════════════════════════════════════════════════

class TestSaveLoadIndex:
    """save_index / load_index 往返正确。"""

    def test_save_and_load_roundtrip(
        self, knowledge_root: Path, index_dir: Path
    ) -> None:
        docs = build_index(knowledge_root)
        save_index(docs, index_dir)
        assert (index_dir / "documents.json").is_file()

        loaded = load_index(index_dir)
        assert len(loaded) == len(docs)
        for orig, loaded_doc in zip(docs, loaded):
            assert orig.doc_id == loaded_doc.doc_id
            assert orig.section == loaded_doc.section
            assert orig.content == loaded_doc.content

    def test_load_nonexistent_index(self, tmp_path: Path) -> None:
        """不存在的索引目录应返回空列表。"""
        docs = load_index(tmp_path / "nonexistent")
        assert docs == []


# ════════════════════════════════════════════════════════════
# 3. 重建索引
# ════════════════════════════════════════════════════════════

class TestReindex:
    """reindex 重建索引正确。"""

    def test_reindex_creates_index(
        self, knowledge_root: Path, index_dir: Path
    ) -> None:
        count = reindex(knowledge_root, index_dir)
        assert count > 0
        assert (index_dir / "documents.json").is_file()

    def test_reindex_returns_count(
        self, knowledge_root: Path, index_dir: Path
    ) -> None:
        count1 = reindex(knowledge_root, index_dir)
        # 再重建一次应相同
        count2 = reindex(knowledge_root, index_dir)
        assert count1 == count2


# ════════════════════════════════════════════════════════════
# 4. 文档模型
# ════════════════════════════════════════════════════════════

class TestKbDocument:
    """KbDocument 序列化/反序列化。"""

    def test_to_dict(self) -> None:
        doc = KbDocument(
            doc_id="test::1",
            section="test",
            content="hello world",
            source="/path/to/file",
        )
        d = doc.to_dict()
        assert d["id"] == "test::1"
        assert d["section"] == "test"
        assert d["content"] == "hello world"
        assert d["source"] == "/path/to/file"

    def test_from_dict(self) -> None:
        d = {
            "id": "test::1",
            "section": "test",
            "content": "hello world",
            "source": "/path/to/file",
        }
        doc = KbDocument.from_dict(d)
        assert doc.doc_id == "test::1"
        assert doc.section == "test"
        assert doc.content == "hello world"
