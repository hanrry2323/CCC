"""CCC 知识库本地检索引擎（BM25）。

纯 Python 实现 BM25 检索，零外部依赖。
支持按域过滤（domain），返回 {id, section, snippet, score}。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .indexer import KbDocument, load_index


# ── BM25 实现 ──

class Bm25Index:
    """BM25 检索索引（内存态）。"""

    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.documents: list[KbDocument] = []
        self.avgdl: float = 0.0
        self.doc_lengths: list[int] = []
        # term -> {doc_index -> term_frequency}
        self.postings: dict[str, dict[int, int]] = {}
        # term -> document frequency
        self.df: dict[str, int] = {}
        self._total_docs: int = 0
        self._built = False

    def build(self, documents: list[KbDocument]) -> None:
        """从文档列表构建 BM25 索引。"""
        self.documents = documents
        self._total_docs = len(documents)

        # 计算文档长度
        self.doc_lengths = [len(self._tokenize(d.content)) for d in documents]
        self.avgdl = sum(self.doc_lengths) / max(self._total_docs, 1)

        # 构建倒排索引
        for idx, doc in enumerate(documents):
            tokens = self._tokenize(doc.content)
            tf = Counter(tokens)
            for term, count in tf.items():
                if term not in self.postings:
                    self.postings[term] = {}
                self.postings[term][idx] = count

        # 计算文档频率
        self.df = {term: len(post) for term, post in self.postings.items()}
        self._built = True

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """分词：中文按单字，英文按单词，全小写。"""
        text = text.lower()
        tokens: list[str] = []
        # 匹配中文字符或英文单词
        for match in re.finditer(r"[\u4e00-\u9fff]|[a-z]+", text):
            tokens.append(match.group())
        return tokens

    def search(
        self,
        query: str,
        domain: str | None = None,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """BM25 检索。

        Args:
            query: 查询关键词
            domain: 域过滤（nodes-paths / projects / decisions / lessons），None=全部
            top_k: 返回结果数上限

        Returns:
            [{id, section, snippet, score}] 按 score 降序
        """
        if not self._built or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 计算每个文档的 BM25 分数
        scores: dict[int, float] = {}
        for term in set(query_tokens):
            if term not in self.postings:
                continue
            idf = math.log(
                (self._total_docs - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1.0
            )
            for doc_idx, tf in self.postings[term].items():
                if domain and self.documents[doc_idx].section != domain:
                    continue
                doc_len = self.doc_lengths[doc_idx]
                tf_norm = (
                    tf * (self.k1 + 1)
                    / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))
                )
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * tf_norm

        if not scores:
            return []

        # 排序取 top_k
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results: list[dict[str, Any]] = []
        for doc_idx, score in sorted_docs:
            doc = self.documents[doc_idx]
            snippet = self._make_snippet(doc.content, query_tokens)
            results.append({
                "id": doc.doc_id,
                "section": doc.section,
                "snippet": snippet,
                "score": round(score, 4),
            })

        return results

    @staticmethod
    def _make_snippet(text: str, query_tokens: list[str], max_len: int = 150) -> str:
        """生成含关键词的摘要片段。"""
        text_lower = text.lower()
        # 找第一个匹配位置
        best_pos = -1
        for token in query_tokens:
            pos = text_lower.find(token)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_pos = pos

        if best_pos < 0:
            return text[:max_len] + ("..." if len(text) > max_len else "")

        # 以匹配位置为中心截取
        start = max(0, best_pos - max_len // 2)
        end = min(len(text), start + max_len)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet


# ── 全局引擎 ──

_engine: Bm25Index | None = None


def get_engine(index_dir: str) -> Bm25Index:
    """获取（或初始化）全局 BM25 引擎。"""
    global _engine
    if _engine is not None:
        return _engine
    _engine = Bm25Index()
    docs = load_index(index_dir)
    if docs:
        _engine.build(docs)
    return _engine


def reset_engine() -> None:
    """重置全局引擎（测试用）。"""
    global _engine
    _engine = None


def search(
    query: str,
    domain: str | None = None,
    index_dir: str | None = None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """便捷检索入口。

    默认索引路径为 ``knowledge/.index/``（相对于项目根）。
    """
    if index_dir is None:
        # 默认相对于项目根
        import os
        _root = os.environ.get(
            "CCC_KB_INDEX_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))), "knowledge", ".index"),
        )
        index_dir = _root
    engine = get_engine(index_dir)
    return engine.search(query, domain=domain, top_k=top_k)


def list_documents(
    domain: str | None = None,
    index_dir: str | None = None,
) -> list[dict[str, str]]:
    """列出知识库中的文档条目。

    Args:
        domain: 域过滤，None=全部
        index_dir: 索引目录

    Returns:
        [{id, section, source}]
    """
    if index_dir is None:
        import os
        index_dir = os.environ.get(
            "CCC_KB_INDEX_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))), "knowledge", ".index"),
        )
    docs = load_index(index_dir)
    result = []
    for d in docs:
        if domain and d.section != domain:
            continue
        result.append({"id": d.doc_id, "section": d.section, "source": d.source})
    return result


def read_document(
    doc_id: str,
    index_dir: str | None = None,
) -> dict[str, str] | None:
    """读取指定知识条目全文。

    Args:
        doc_id: 文档 ID
        index_dir: 索引目录

    Returns:
        {id, section, content, source} 或 None
    """
    if index_dir is None:
        import os
        index_dir = os.environ.get(
            "CCC_KB_INDEX_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))), "knowledge", ".index"),
        )
    docs = load_index(index_dir)
    for d in docs:
        if d.doc_id == doc_id:
            return {"id": d.doc_id, "section": d.section, "content": d.content, "source": d.source}
    return None
