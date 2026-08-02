"""CCC 知识库 · MCP 服务 + 本地语义检索。

提供 BM25 级本地检索（纯 Python，零外部依赖）和 MCP stdio server，
供 2017 大脑 Agent 通过 MCP 协议查询 CCC 自建知识库（knowledge/）。

使用入口：
    python3 -m server.kb.mcp_server --selftest   # 自测
    python3 -m server.kb.mcp_server --list-tools  # 列出工具
"""

from __future__ import annotations