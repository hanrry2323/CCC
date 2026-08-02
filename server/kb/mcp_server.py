"""CCC 知识库 MCP stdio server。

暴露三个工具：
  - kb_search(query, domain?) → 检索结果 [{id, section, snippet, score}]
  - kb_read(path) → 读取指定知识条目全文 {id, section, content, source}
  - kb_list(domain?) → 列出域内条目 [{id, section, source}]

用法：
    $PYTHON_BIN -m server.kb.mcp_server                # 启动 MCP stdio server
    $PYTHON_BIN -m server.kb.mcp_server --selftest      # 自测（启动→调用三工具→退出）
    $PYTHON_BIN -m server.kb.mcp_server --list-tools    # 列出工具清单
    $PYTHON_BIN -m server.kb.mcp_server --reindex       # 重建索引
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


# ── 路径配置 ──

def _project_root() -> Path:
    """返回项目根目录（server/..）。"""
    return Path(__file__).resolve().parents[2]


def _default_knowledge_root() -> str:
    return str(_project_root() / "knowledge")


def _default_index_dir() -> str:
    return os.environ.get(
        "CCC_KB_INDEX_DIR",
        str(_project_root() / "knowledge" / ".index"),
    )


# ── 工具实现 ──

def _ensure_index() -> None:
    """确保索引已构建，否则自动构建。"""
    index_dir = _default_index_dir()
    if not Path(index_dir, "documents.json").is_file():
        from .indexer import reindex as _reindex
        count = _reindex(_default_knowledge_root(), index_dir)
        # 重置 search 引擎
        from .search import reset_engine
        reset_engine()


def _tool_kb_search(args: dict[str, Any]) -> list[dict[str, Any]]:
    """kb_search 工具实现。"""
    query = args.get("query", "")
    if not query:
        return []
    domain = args.get("domain")
    _ensure_index()
    from .search import search
    return search(query, domain=domain, index_dir=_default_index_dir())


def _tool_kb_read(args: dict[str, Any]) -> dict[str, Any] | None:
    """kb_read 工具实现。"""
    path = args.get("path", "")
    if not path:
        return None
    _ensure_index()
    from .search import read_document
    return read_document(path, index_dir=_default_index_dir())


def _tool_kb_list(args: dict[str, Any]) -> list[dict[str, str]]:
    """kb_list 工具实现。"""
    domain = args.get("domain")
    _ensure_index()
    from .search import list_documents
    return list_documents(domain=domain, index_dir=_default_index_dir())


# ── 工具注册表 ──

TOOLS: list[dict[str, Any]] = [
    {
        "name": "kb_search",
        "description": "检索 CCC 知识库，返回匹配的文档片段",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，支持中文和英文",
                },
                "domain": {
                    "type": "string",
                    "description": "域过滤：nodes-paths / projects / decisions / lessons，不传则检索全部域",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "kb_read",
        "description": "读取指定知识条目的全文内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "知识条目 ID（来自 kb_search 或 kb_list 返回的 id 字段）",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "kb_list",
        "description": "列出知识库中指定域的所有条目",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "域过滤：nodes-paths / projects / decisions / lessons，不传则列出全部",
                },
            },
            "required": [],
        },
    },
]

TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "kb_search": _tool_kb_search,
    "kb_read": _tool_kb_read,
    "kb_list": _tool_kb_list,
}


# ── MCP 协议（JSON-RPC 2.0 over stdio） ──

def _respond(msg: dict[str, Any]) -> None:
    """向 stdout 写入 JSON-RPC 响应。"""
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle_request(request: dict[str, Any]) -> None:
    """处理单条 JSON-RPC 请求。"""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {}) or {}

    if method == "initialize":
        _respond({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "ccc-kb-mcp",
                    "version": "1.0.0",
                },
            },
        })
    elif method == "notifications/initialized":
        # 客户端初始化完成通知，无需响应
        pass
    elif method == "tools/list":
        _respond({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS,
            },
        })
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {}) or {}
        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}",
                },
            })
            return
        try:
            result = handler(tool_args)
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    ],
                },
            })
        except Exception as e:
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}",
                },
            })
    else:
        _respond({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        })


def _handle_notification(notification: dict[str, Any]) -> None:
    """处理 JSON-RPC 通知（无需响应）。"""
    method = notification.get("method", "")
    if method == "notifications/initialized":
        pass


def run_server() -> None:
    """运行 MCP stdio server。"""
    buf = ""
    while True:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in msg and msg.get("id") is not None:
            _handle_request(msg)
        else:
            _handle_notification(msg)


# ── 自测 ──

def _selftest() -> int:
    """自测：启动→索引重建→调用三工具→退出。

    Returns:
        0 成功，非零失败
    """
    # 1. 重建索引
    from .indexer import reindex
    count = reindex(_default_knowledge_root(), _default_index_dir())
    print(f"[selftest] 索引重建完成：{count} 文档", file=sys.stderr)

    # 2. 测 kb_search
    search_result = _tool_kb_search({"query": "CCC", "domain": None})
    if not isinstance(search_result, list):
        print(f"[selftest] FAIL kb_search 返回类型错误: {type(search_result)}", file=sys.stderr)
        return 1
    print(f"[selftest] kb_search('CCC') → {len(search_result)} 结果", file=sys.stderr)

    # 3. 测 kb_list
    list_result = _tool_kb_list({"domain": "nodes-paths"})
    if not isinstance(list_result, list):
        print(f"[selftest] FAIL kb_list 返回类型错误: {type(list_result)}", file=sys.stderr)
        return 1
    print(f"[selftest] kb_list('nodes-paths') → {len(list_result)} 条目", file=sys.stderr)

    # 4. 测 kb_read（取第一个条目）
    if list_result:
        first_id = list_result[0]["id"]
        read_result = _tool_kb_read({"path": first_id})
        if read_result is None:
            print(f"[selftest] FAIL kb_read('{first_id}') 返回 None", file=sys.stderr)
            return 1
        print(f"[selftest] kb_read('{first_id}') → {len(read_result.get('content', ''))} 字符", file=sys.stderr)

    # 5. 测空结果
    empty_result = _tool_kb_search({"query": "ZZZZNOTEXIST999"})
    if len(empty_result) != 0:
        print(f"[selftest] FAIL kb_search 空查询应返回 0 结果，实际 {len(empty_result)}", file=sys.stderr)
        return 1
    print("[selftest] kb_search 空结果正确", file=sys.stderr)

    print("[selftest] ALL PASSED", file=sys.stderr)
    return 0


# ── CLI 入口 ──

def main() -> None:
    """CLI 入口。"""
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    elif "--list-tools" in sys.argv:
        print(json.dumps(TOOLS, ensure_ascii=False, indent=2))
    elif "--reindex" in sys.argv:
        from .indexer import reindex
        count = reindex(_default_knowledge_root(), _default_index_dir())
        print(f"索引重建完成：{count} 文档")
    else:
        run_server()


if __name__ == "__main__":
    main()