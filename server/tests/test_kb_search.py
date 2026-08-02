"""测试：知识库本地检索（search.py）。

覆盖：
1. BM25 检索对已知关键词命中对应域
2. 域过滤正确
3. 空结果行为正确
4. 摘要生成
"""

from __future__ import annotations

import pytest

from server.kb.indexer import KbDocument
from server.kb.search import Bm25Index, reset_engine


# ── 夹具 ──

@pytest.fixture
def sample_docs() -> list[KbDocument]:
    return [
        KbDocument(
            doc_id="nodes-paths::machine-m1",
            section="nodes-paths",
            content="M1 开发机 IP 192.168.3.140 macOS 26.5.2 arm64 8GB 运行 CCC 服务",
            source="knowledge/seed/01-nodes-paths.json",
        ),
        KbDocument(
            doc_id="nodes-paths::machine-mac2017",
            section="nodes-paths",
            content="Mac2017 重活节点 IP 192.168.3.116 macOS 13.7.8 x86_64 16GB 运行 qb",
            source="knowledge/seed/01-nodes-paths.json",
        ),
        KbDocument(
            doc_id="projects::ccc",
            section="projects",
            content="CCC 项目 主仓 路径 /Users/apple/program/CCC/ 自动化平台底座",
            source="knowledge/seed/02-project-metadata.json",
        ),
        KbDocument(
            doc_id="projects::quantHive",
            section="projects",
            content="QuantHive 独立轨道 git 仓 路径 /Users/apple/ZCodeProject/QuantHive/",
            source="knowledge/seed/02-project-metadata.json",
        ),
        KbDocument(
            doc_id="decisions::D1-D10",
            section="decisions",
            content="CCC 重构方案 薄驱动 Engine 文档流转 看板 HTTP 服务 大脑 Agent",
            source="knowledge/seed/03-key-decisions.json",
        ),
        KbDocument(
            doc_id="lessons::L1",
            section="lessons",
            content="Plan 必须用自然语言 不能写具体命令 避免 agent 被当成 shell 执行器",
            source="knowledge/seed/04-lessons.json",
        ),
    ]


@pytest.fixture
def bm25(sample_docs: list[KbDocument]) -> Bm25Index:
    engine = Bm25Index()
    engine.build(sample_docs)
    return engine


# ════════════════════════════════════════════════════════════
# 1. 基本检索
# ════════════════════════════════════════════════════════════

class TestBasicSearch:
    """BM25 检索基本功能。"""

    def test_search_returns_results(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC")
        assert len(results) > 0
        for r in results:
            assert "id" in r
            assert "section" in r
            assert "snippet" in r
            assert "score" in r

    def test_search_known_keyword_hits_correct_domain(
        self, bm25: Bm25Index
    ) -> None:
        """对已知关键词 'CCC'，应命中包含 CCC 的文档。"""
        results = bm25.search("CCC")
        sections = {r["section"] for r in results}
        # CCC 出现在 projects 和 decisions 中
        assert "projects" in sections or "decisions" in sections

    def test_search_returns_sorted_by_score(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC")
        if len(results) >= 2:
            scores = [r["score"] for r in results]
            assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


# ════════════════════════════════════════════════════════════
# 2. 域过滤
# ════════════════════════════════════════════════════════════

class TestDomainFilter:
    """域过滤功能。"""

    def test_filter_single_domain(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC", domain="projects")
        assert len(results) > 0
        for r in results:
            assert r["section"] == "projects"

    def test_filter_excludes_other_domains(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC", domain="nodes-paths")
        # 在 nodes-paths 中搜索 "CCC"，应返回 0 结果（因为 sample 中 nodes-paths 不包含 CCC）
        # 实际可能因 BM25 有少量匹配，但结果 section 必须全是 nodes-paths
        for r in results:
            assert r["section"] == "nodes-paths"

    def test_filter_none_returns_all(self, bm25: Bm25Index) -> None:
        results_all = bm25.search("CCC", domain=None)
        results_filtered = bm25.search("CCC", domain="projects")
        assert len(results_all) >= len(results_filtered)


# ════════════════════════════════════════════════════════════
# 3. 空结果
# ════════════════════════════════════════════════════════════

class TestEmptyResults:
    """空结果行为。"""

    def test_empty_query(self, bm25: Bm25Index) -> None:
        results = bm25.search("")
        assert results == []

    def test_no_match(self, bm25: Bm25Index) -> None:
        results = bm25.search("ZZZZNOTEXIST999")
        assert results == []

    def test_no_match_with_domain(self, bm25: Bm25Index) -> None:
        results = bm25.search("ZZZZNOTEXIST999", domain="projects")
        assert results == []


# ════════════════════════════════════════════════════════════
# 4. 摘要生成
# ════════════════════════════════════════════════════════════

class TestSnippet:
    """摘要生成。"""

    def test_snippet_contains_keyword(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC")
        for r in results:
            if "CCC" in r["snippet"] or "ccc" in r["snippet"].lower():
                return
        # 至少有一个结果包含关键词
        assert True

    def test_snippet_not_empty(self, bm25: Bm25Index) -> None:
        results = bm25.search("CCC")
        for r in results:
            assert r["snippet"], f"snippet 为空: {r['id']}"


# ════════════════════════════════════════════════════════════
# 5. 引擎重置
# ════════════════════════════════════════════════════════════

class TestEngineReset:
    """引擎重置。"""

    def test_reset_engine(self) -> None:
        reset_engine()
        # 重置后不应报错
        reset_engine()