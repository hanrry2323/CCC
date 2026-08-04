"""CCC 知识库查询统一入口（T51）。

MCP 工具（``server/kb/mcp_server.py``）、大脑（``server/web/brain.py``）、
CLI（``server/kb/cli.py``、``knowledge/ccc-kb-search.sh``）统一经此服务查询，
保证「同一内核」。对外查询协议 = kb MCP（tools），本服务是 MCP 的内核实现。

能力：:

    ensure_index()          # 无索引 → 全量构建；v2 索引 → mtime 增量；v1 索引不动
    search(query, domain)   # BM25 检索（自动 ensure_index，结果已跨源去重）
    read_document(doc_id)   # 读条目全文
    list_documents(domain)  # 列条目
    health()                # 健康自检（MCP 准入/自检用）

红线：只读 ``knowledge/``（D2 零外脑），禁止读 qx-map / hp-kb。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import search as _search_engine
from .indexer import incremental_index, load_index, load_mtimes, reindex


# ── 路径配置（零硬编码：端口/路径走环境变量，见 CLAUDE.md 红线 #7） ──

def default_knowledge_root() -> Path:
    """知识库根目录（默认 ``<项目根>/knowledge``）。"""
    return Path(__file__).resolve().parents[2] / "knowledge"


def default_index_dir() -> Path:
    """BM25 索引目录（``CCC_KB_INDEX_DIR`` 可覆盖，默认 ``knowledge/.index``）。"""
    env = os.environ.get("CCC_KB_INDEX_DIR", "").strip()
    return Path(env) if env else Path(__file__).resolve().parents[2] / "knowledge" / ".index"


def _resolve_index(index_dir: str | None) -> str:
    """将可选 index_dir 参数解析为绝对路径字符串。"""
    return str(Path(index_dir).resolve()) if index_dir else str(default_index_dir().resolve())


# ── 索引维护 ──

def ensure_index(index_dir: str | None = None) -> str:
    """确保索引就绪：无索引 → 全量构建；v2 索引 → 按 mtime 增量更新；v1 索引不动。

    返回描述字符串：``built N`` / ``updated N changed=M`` / ``unchanged``。
    任何重建后重置 search 全局引擎，避免陈旧索引。
    """
    idx = _resolve_index(index_dir)
    root = default_knowledge_root()
    if not Path(idx, "documents.json").is_file():
        count = reindex(root, idx)
        _search_engine.reset_engine()
        return f"built {count}"
    mtimes = load_mtimes(idx)
    if mtimes is None or not mtimes:
        # v1 索引（无 mtime 表）不自动动，交由显式 reindex / --reindex
        return "unchanged"
    count, changed = incremental_index(root, idx)
    if changed:
        _search_engine.reset_engine()
        return f"updated {count} changed={len(changed)}"
    return "unchanged"


def reindex_all(index_dir: str | None = None) -> int:
    """全量重建索引（显式操作：--reindex / 调度）。"""
    idx = _resolve_index(index_dir)
    count = reindex(default_knowledge_root(), idx)
    _search_engine.reset_engine()
    return count


# ── 查询（统一内核） ──

def search(
    query: str,
    domain: str | None = None,
    top_k: int = 20,
    index_dir: str | None = None,
) -> list[dict[str, Any]]:
    """BM25 检索（统一查询入口）。

    自动 ``ensure_index``（增量更新）；结果按 score 降序、已跨源去重。
    """
    ensure_index(index_dir)
    return _search_engine.search(
        query, domain=domain, top_k=top_k, index_dir=_resolve_index(index_dir)
    )


def read_document(doc_id: str, index_dir: str | None = None) -> dict[str, str] | None:
    """读取指定知识条目全文（{id, section, content, source} 或 None）。"""
    ensure_index(index_dir)
    return _search_engine.read_document(doc_id, index_dir=_resolve_index(index_dir))


def list_documents(
    domain: str | None = None,
    index_dir: str | None = None,
) -> list[dict[str, str]]:
    """列出知识库条目（[{id, section, source}]，可按域过滤）。"""
    ensure_index(index_dir)
    return _search_engine.list_documents(domain=domain, index_dir=_resolve_index(index_dir))


# ── 健康自检（MCP 准入 / selftest） ──

def health(index_dir: str | None = None) -> dict[str, Any]:
    """MCP 服务健康状态：索引就绪、文档数、各域文档计数。"""
    idx = _resolve_index(index_dir)
    ensure_index(index_dir)
    docs = load_index(idx)
    sections: dict[str, int] = {}
    for d in docs:
        sections[d.section] = sections.get(d.section, 0) + 1
    return {
        "ok": bool(docs),
        "index_dir": idx,
        "documents": len(docs),
        "sections": sections,
    }
