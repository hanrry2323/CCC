"""CCC 知识库本地检索引擎（BM25）。

纯 Python 实现 BM25 检索，零外部依赖。
支持按域过滤（domain），返回 {id, section, snippet, score}。

T51 BM25 质量调优：
- 分词含数字（IP/端口可检索）；
- k1/b 走环境变量 ``CCC_KB_BM25_K1`` / ``CCC_KB_BM25_B``（默认 1.2/0.75）；
- 域别名归一（兼容旧索引中的数字前缀 section）；
- 跨源结果去重（seed JSON 与 domains MD 同实体折叠，保留分数高者）。
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from typing import Any

from .indexer import KbDocument, load_index


# ── 域别名 / 分词 ──

# 与 indexer.normalize_section 同源；索引新构建后 section 已归一，
# 此别名仅兼容历史索引（数字前缀 section），保证 domain 过滤一致。
_SECTION_ALIASES = {
    "01-nodes-paths": "nodes-paths",
    "02-project-metadata": "projects",
    "03-key-decisions": "decisions",
    "04-lessons": "lessons",
    "plans": "plans",
    "roadmap": "plans",
}


def _canonical_section(section: str) -> str:
    """域别名归一（兼容历史索引）。"""
    return _SECTION_ALIASES.get(section, section)


def _env_float(name: str, default: float) -> float:
    """读取浮点环境变量，非法值回退默认。"""
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# ── BM25 实现 ──

class Bm25Index:
    """BM25 检索索引（内存态）。"""

    def __init__(self, k1: float | None = None, b: float | None = None) -> None:
        # k1/b 支持环境变量覆盖（CCC_KB_BM25_K1 / CCC_KB_BM25_B），默认 1.2/0.75
        self.k1 = k1 if k1 is not None else _env_float("CCC_KB_BM25_K1", 1.2)
        self.b = b if b is not None else _env_float("CCC_KB_BM25_B", 0.75)
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
        """分词：中文按单字，英文按单词，数字串独立成 token，全小写。

        T51 加数字：IP（192.168.3.116）、端口（7788/6100）、版本号等可直接检索。
        """
        text = text.lower()
        tokens: list[str] = []
        # 匹配中文字符、英文单词或数字串
        for match in re.finditer(r"[\u4e00-\u9fff]|[a-z]+|\d+", text):
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
        canon_domain = _canonical_section(domain) if domain else None
        for term in set(query_tokens):
            if term not in self.postings:
                continue
            idf = math.log(
                (self._total_docs - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1.0
            )
            for doc_idx, tf in self.postings[term].items():
                if canon_domain and _canonical_section(self.documents[doc_idx].section) != canon_domain:
                    continue
                doc_len = self.doc_lengths[doc_idx]
                tf_norm = (
                    tf * (self.k1 + 1)
                    / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))
                )
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * tf_norm

        if not scores:
            return []

        # 排序取 top_k（先取超量再去重，保证去重后仍有足够结果）
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: max(top_k * 2, top_k + 10)]

        results: list[dict[str, Any]] = []
        for doc_idx, score in sorted_docs:
            doc = self.documents[doc_idx]
            snippet = self._make_snippet(doc.content, query_tokens)
            results.append({
                "id": doc.doc_id,
                "section": _canonical_section(doc.section),
                "snippet": snippet,
                "score": round(score, 4),
            })

        # T51 跨源结果去重（seed JSON ↔ domains MD 同实体折叠）
        return dedup_results(results)[:top_k]

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


# ── 跨源结果去重（T51） ──

def _doc_id_tail(doc_id: str) -> str:
    """取 doc_id 末段标识（最后一个 ``::`` 之后），用于去重比对。

    JSON 形如 ``02-project-metadata::qb`` → ``qb``；MD 形如 ``domains::projects::qb_...``
    → ``qb_...``，故用 rsplit 取末段。
    """
    return doc_id.rsplit("::", 1)[1] if "::" in doc_id else doc_id


def _source_kind(doc_id: str) -> str:
    """文档来源：seed JSON 的 doc_id 前缀以数字开头；domains MD 以 ``domains`` 开头。"""
    prefix = doc_id.split("::", 1)[0]
    return "json" if prefix and prefix[0].isdigit() else "md"


def _is_prefix_collapse(a: str, b: str) -> bool:
    """跨源同实体判定：较短 tail 是较长 tail 的段前缀。

    段界为 ``_`` / ``-`` / 空格，避免 ``ccc`` 误折叠 ``ccc-relay-runtime``（段界非词首）。
    两源同尾（如 ``qb`` ↔ ``qb``）视为同实体。
    """
    a, b = a.lower(), b.lower()
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return False
    if not b.startswith(a):
        return False
    if len(a) == len(b):
        return True
    return b[len(a)] in "_- "


def dedup_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """跨源结果去重：同 section 内，seed JSON 与 domains MD 的 doc_id 尾段前缀一致的，
    视为同一知识实体，保留分数高者（结果按分数降序，故保留先出现者）。

    - 仅折叠跨源（JSON ↔ MD）对，同源条目（如两个项目 JSON 文档）不折叠；
    - 不同 section 不折叠。
    """
    accepted: list[dict[str, Any]] = []
    for r in results:
        dup = False
        tail = _doc_id_tail(r["id"])
        kind = _source_kind(r["id"])
        for a in accepted:
            if a["section"] != r["section"]:
                continue
            if kind == _source_kind(a["id"]):
                continue  # 同源不折叠
            if _is_prefix_collapse(tail, _doc_id_tail(a["id"])):
                dup = True
                break
        if not dup:
            accepted.append(r)
    return accepted


# ── 全局引擎 ──

_engine: Bm25Index | None = None


def get_engine(index_dir: str) -> Bm25Index:
    """获取（或初始化）全局 BM25 引擎。

    k1/b 从环境变量 ``CCC_KB_BM25_K1`` / ``CCC_KB_BM25_B`` 读取（默认 1.2/0.75），
    经 ``reset_engine`` 后生效，支持调参对比。
    """
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
