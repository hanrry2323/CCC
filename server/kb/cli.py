"""CCC 知识库查询 CLI（T51）。

``knowledge/ccc-kb-search.sh`` 的后端：与 kb MCP / 大脑同一查询内核
（``server/kb/service.py``），保证 CLI 结果与 MCP 一致。

用法::

    python3 -m server.kb.cli search "<关键词>" [--domain <域>] [--top-k N]
    python3 -m server.kb.cli list [--domain <域>]
    python3 -m server.kb.cli read <doc_id>
    python3 -m server.kb.cli health
    python3 -m server.kb.cli reindex
    python3 -m server.kb.cli reindex-incremental
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from . import service


def _print_search(results: list[dict[str, Any]]) -> None:
    if not results:
        print("无匹配结果")
        return
    print(f"命中 {len(results)} 条：")
    for i, r in enumerate(results, 1):
        section = r.get("section", "?")
        doc_id = r.get("id", "?")
        score = r.get("score", 0)
        snippet = r.get("snippet", "") or ""
        print(f"{i:>2}. [{section}] {doc_id}  score={score}")
        print(f"     {snippet}")


def _cmd_search(args: argparse.Namespace) -> int:
    query = args.query
    if not query:
        print("错误：需要查询关键词")
        return 2
    results = service.search(query, domain=args.domain, top_k=args.top_k)
    _print_search(results)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    entries = service.list_documents(domain=args.domain)
    if not entries:
        print("无条目")
        return 0
    print(f"共 {len(entries)} 条：")
    for e in entries:
        print(f"  [{e['section']}] {e['id']}")
    return 0


def _cmd_read(args: argparse.Namespace) -> int:
    doc = service.read_document(args.doc_id)
    if doc is None:
        print(f"未找到条目：{args.doc_id}")
        return 1
    print(f"[{doc['section']}] {doc['id']}")
    print(f"来源：{doc['source']}")
    print("----")
    print(doc.get("content", ""))
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    h = service.health()
    print(f"状态：{'OK' if h['ok'] else 'FAIL'}")
    print(f"索引目录：{h['index_dir']}")
    print(f"文档数：{h['documents']}")
    for section, count in sorted(h.get("sections", {}).items()):
        print(f"  {section}: {count}")
    return 0 if h["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccc-kb", description="CCC 知识库查询 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="BM25 检索")
    p_search.add_argument("query", help="检索关键词")
    p_search.add_argument("--domain", default=None, help="域���滤（nodes-paths/projects/decisions/lessons/plans）")
    p_search.add_argument("--top-k", type=int, default=5, help="返回条数上限（默认 5）")
    p_search.set_defaults(func=_cmd_search)

    p_list = sub.add_parser("list", help="列条目")
    p_list.add_argument("--domain", default=None, help="域过滤（nodes-paths/projects/decisions/lessons/plans）")
    p_list.set_defaults(func=_cmd_list)

    p_read = sub.add_parser("read", help="读条目全文")
    p_read.add_argument("doc_id", help="条目 ID")
    p_read.set_defaults(func=_cmd_read)

    p_health = sub.add_parser("health", help="健康自检")
    p_health.set_defaults(func=_cmd_health)

    p_full = sub.add_parser("reindex", help="全量重建索引")
    p_full.set_defaults(func=lambda a: (print(f"索引全量重建完成：{service.reindex_all()} 文档"), 0)[1])

    p_inc = sub.add_parser("reindex-incremental", help="增量重建索引")
    p_inc.set_defaults(func=lambda a: (print(f"索引增量重建完成：{service.ensure_index()}"), 0)[1])

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
