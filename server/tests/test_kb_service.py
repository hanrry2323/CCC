"""测试：知识库统一查询服务（service.py，T51）。

覆盖：
1. ensure_index：无索引全量构建 / 无变化零扫 / v1 索引不动
2. search 经统一内核（自动 ensure_index + 数字检索 + 跨源去重）
3. read_document / list_documents
4. health 健康自检
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from server.kb import service
from server.kb.indexer import KbDocument, build_index, save_index


# ── 夹具 ──

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清理 CCC_KB_INDEX_DIR，避免污染真实索引。"""
    monkeypatch.delenv("CCC_KB_INDEX_DIR", raising=False)
    yield


@pytest.fixture
def kb_root(tmp_path: Path) -> Path:
    """构造临时知识库（含 seed JSON + domains MD）。"""
    root = tmp_path / "knowledge"
    (root / "seed").mkdir(parents=True)
    (root / "seed" / "01-nodes-paths.json").write_text(
        json.dumps({
            "schema": "ccc-kb-seed-v1",
            "section": "01-nodes-paths",
            "machines": [
                {"hostname": "m1", "ip": "192.168.3.140", "role": "开发机"},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "domains" / "projects").mkdir(parents=True)
    (root / "domains" / "projects" / "seed.md").write_text(
        "# 项目域\n\n## CCC 主仓\n\nCCC 项目 主仓 自动化平台底座\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    return tmp_path / ".index"


# ════════════════════════════════════════════════════════════
# 1. ensure_index
# ════════════════════════════════════════════════════════════

class TestEnsureIndex:
    """ensure_index 按需构建/增量。"""

    def test_first_build(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        status = service.ensure_index()
        assert status.startswith("built")
        assert (index_dir / "documents.json").is_file()

    def test_unchanged_no_scan(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        service.ensure_index()
        status = service.ensure_index()
        assert status == "unchanged"

    def test_incremental_update(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        service.ensure_index()
        target = kb_root / "seed" / "01-nodes-paths.json"
        os.utime(target)
        status = service.ensure_index()
        assert "updated" in status

    def test_v1_index_untouched(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        """v1 索引（无 mtime 表）不自动重建。"""
        index_dir.mkdir(parents=True, exist_ok=True)
        docs = [
            KbDocument("01-nodes-paths::m1", "nodes-paths", "M1 开发机", "x"),
        ]
        save_index(docs, index_dir)  # save_index 写 v2（带 mtimes）
        # 手动降级为 v1：去掉 mtimes
        data = json.loads((index_dir / "documents.json").read_text(encoding="utf-8"))
        data.pop("mtimes", None)
        (index_dir / "documents.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        status = service.ensure_index()
        assert status == "unchanged"


# ════════════════════════════════════════════════════════════
# 2. search 经统一内核
# ════════════════════════════════════════════════════════════

class TestServiceSearch:
    """search 自动 ensure_index，数字可检索，跨源去重。"""

    def test_search_auto_build(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        results = service.search("192.168.3.140", index_dir=str(index_dir))
        assert results
        assert results[0]["section"] == "nodes-paths"

    def test_search_domain_filter(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        results = service.search("CCC", domain="projects", index_dir=str(index_dir))
        assert results
        assert all(r["section"] == "projects" for r in results)

    def test_search_empty(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        assert service.search("", index_dir=str(index_dir)) == []
        assert service.search("ZZZZNOTEXIST", index_dir=str(index_dir)) == []


# ════════════════════════════════════════════════════════════
# 3. read / list
# ════════════════════════════════════════════════════════════

class TestServiceReadList:
    """read_document / list_documents。"""

    def test_list_documents(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        entries = service.list_documents(index_dir=str(index_dir))
        assert len(entries) >= 2
        sections = {e["section"] for e in entries}
        assert "nodes-paths" in sections
        assert "projects" in sections

    def test_read_document(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        entries = service.list_documents(index_dir=str(index_dir))
        doc = service.read_document(entries[0]["id"], index_dir=str(index_dir))
        assert doc is not None
        assert doc["id"] == entries[0]["id"]
        assert doc["content"]

    def test_read_missing(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        assert service.read_document("nonexistent", index_dir=str(index_dir)) is None


# ════════════════════════════════════════════════════════════
# 4. health
# ════════════════════════════════════════════════════════════

class TestHealth:
    """health 自检。"""

    def test_health_ok(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        h = service.health(index_dir=str(index_dir))
        assert h["ok"] is True
        assert h["documents"] >= 2
        assert h["sections"]["nodes-paths"] >= 1
        assert h["sections"]["projects"] >= 1

    def test_health_index_dir(self, kb_root: Path, index_dir: Path, monkeypatch) -> None:
        monkeypatch.setattr(service, "default_knowledge_root", lambda: kb_root)
        monkeypatch.setattr(service, "default_index_dir", lambda: index_dir)
        h = service.health(index_dir=str(index_dir))
        assert str(index_dir) in h["index_dir"]
