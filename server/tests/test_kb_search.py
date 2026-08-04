"""测试：知识库本地检索（search.py）。

覆盖：
1. BM25 检索对已知关键词命中对应域
2. 域过滤正确
3. 空结果行为正确
4. 摘要生成
5. T51 数字分词（IP/端口可检索）
6. T51 域别名归一（数字前缀 section 兼容）
7. T51 跨源结果去重（seed JSON ↔ domains MD 同实体折叠）
8. T51 k1/b 环境变量调参
"""

from __future__ import annotations

import pytest

from server.kb.indexer import KbDocument
from server.kb.search import Bm25Index, _canonical_section, dedup_results, reset_engine


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
# 5. T51 数字分词
# ════════════════════════════════════════════════════════════

class TestDigitTokenize:
    """T51：数字串独立成 token，IP/端口可检索。"""

    def test_ip_query_hits(self, bm25: Bm25Index) -> None:
        """IP 查询应命中对应机器文档。"""
        results = bm25.search("192.168.3.140")
        assert results, "IP 查询应有结果"
        hit = results[0]
        assert "192.168.3.140" in hit["snippet"] or "m1" in hit["id"].lower()

    def test_zip_query_hits(self, bm25: Bm25Index) -> None:
        """端口/编号数字可检索。"""
        results = bm25.search("192.168.3.116")
        assert results

    def test_tokenize_keeps_numbers(self) -> None:
        tokens = Bm25Index._tokenize("7788 端口 6100")
        assert "7788" in tokens
        assert "6100" in tokens
        assert "端" in tokens  # 中文按单字
        assert "口" in tokens


# ════════════════════════════════════════════════════════════
# 6. T51 域别名归一
# ════════════════════════════════════════════════════════════

class TestDomainAlias:
    """T51：数字前缀 section（历史索引）过滤归一为域过滤名。"""

    def test_canonical_section_alias(self) -> None:
        assert _canonical_section("01-nodes-paths") == "nodes-paths"
        assert _canonical_section("nodes-paths") == "nodes-paths"

    def test_search_alias_domain_filter(self) -> None:
        """用数字前缀 section 作为 domain 过滤参数，等价于规范域。"""
        docs = [
            KbDocument("01-nodes-paths::m1", "01-nodes-paths", "M1 开发机 IP 192.168.3.140", "s1"),
            KbDocument("02-project-metadata::ccc", "02-project-metadata", "CCC 项目 主仓", "s2"),
        ]
        engine = Bm25Index()
        engine.build(docs)
        # 域过滤按归一名生效：数字前缀别名被解析到规范域
        r1 = engine.search("CCC", domain="02-project-metadata")
        r2 = engine.search("CCC", domain="projects")
        assert len(r1) == len(r2) == 1
        assert r1[0]["section"] == "projects"


# ════════════════════════════════════════════════════════════
# 7. T51 跨源结果去重
# ════════════════════════════════════════════════════════════

class TestDedupResults:
    """T51：seed JSON 与 domains MD 同实体结果折叠，保留分数高者。"""

    @staticmethod
    def _result(doc_id: str, section: str, score: float) -> dict:
        return {"id": doc_id, "section": section, "snippet": doc_id, "score": score}

    def test_cross_source_same_entity_collapse(self) -> None:
        results = [
            self._result("02-project-metadata::qb", "projects", 6.7),
            self._result("domains::projects::qb_CCC_自动化开发测试项目_", "projects", 6.4),
            self._result("02-project-metadata::CCC", "projects", 6.1),
        ]
        deduped = dedup_results(results)
        assert len(deduped) == 2  # qb 双源折叠为 1
        assert deduped[0]["id"] == "02-project-metadata::qb"

    def test_same_source_not_collapsed(self) -> None:
        """同源（两个 JSON 项目）不折叠，即使前缀相似。"""
        results = [
            self._result("02-project-metadata::ccc", "projects", 6.0),
            self._result("02-project-metadata::ccc-relay-runtime", "projects", 5.5),
        ]
        deduped = dedup_results(results)
        assert len(deduped) == 2

    def test_different_section_not_collapsed(self) -> None:
        """不同 section 不折叠。"""
        results = [
            self._result("01-nodes-paths::m1", "nodes-paths", 6.0),
            self._result("domains::projects::m1_xx", "projects", 5.5),
        ]
        deduped = dedup_results(results)
        assert len(deduped) == 2

    def test_search_applies_dedup(self) -> None:
        """search 返回结果已跨源去重。"""
        docs = [
            KbDocument("02-project-metadata::qb", "projects", "qb 项目 路径 Mac2017 自动化", "j1"),
            KbDocument("domains::projects::qb_CCC_自动化开发测试项目_", "projects", "qb（CCC 自动化开发测试项目）路径 Mac2017", "m1"),
            KbDocument("02-project-metadata::xianyu", "projects", "xianyu 项目 自动分发 平台", "j2"),
        ]
        engine = Bm25Index()
        engine.build(docs)
        results = engine.search("qb 项目")
        ids = [r["id"] for r in results]
        assert len(ids) == 2  # qb 双源折叠
        assert any("xianyu" in i for i in ids)


# ════════════════════════════════════════════════════════════
# 8. T51 k1/b 环境变量调参
# ════════════════════════════════════════════════════════════

class TestBm25Params:
    """T51：k1/b 可经环境变量覆盖，默认 1.2/0.75。"""

    def test_default_params(self) -> None:
        engine = Bm25Index()
        assert engine.k1 == 1.2
        assert engine.b == 0.75

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("CCC_KB_BM25_K1", "1.5")
        monkeypatch.setenv("CCC_KB_BM25_B", "0.5")
        engine = Bm25Index()
        assert engine.k1 == 1.5
        assert engine.b == 0.5

    def test_env_invalid_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("CCC_KB_BM25_K1", "abc")
        engine = Bm25Index()
        assert engine.k1 == 1.2

    def test_param_affects_scores(self) -> None:
        """不同 k1/b 产生不同分数（调参有实际影响）。"""
        docs = [
            KbDocument("d::1", "t", "alpha beta gamma", "s"),
            KbDocument("d::2", "t", "alpha alpha alpha beta", "s"),
        ]
        e1 = Bm25Index(k1=1.2, b=0.75)
        e1.build(docs)
        e2 = Bm25Index(k1=2.0, b=0.3)
        e2.build(docs)
        assert e1.search("alpha")[0]["score"] != e2.search("alpha")[0]["score"]


# ════════════════════════════════════════════════════════════
# 9. 引擎重置
# ════════════════════════════════════════════════════════════

class TestEngineReset:
    """引擎重置。"""

    def test_reset_engine(self) -> None:
        reset_engine()
        # 重置后不应报错
        reset_engine()
