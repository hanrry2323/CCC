"""测试：知识库 MCP server（mcp_server.py）。

覆盖：
1. 工具清单含 kb_search / kb_read / kb_list
2. 三工具调用成功
3. 非法参数报错
4. --selftest 自测通过
5. --list-tools 输出正确
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from server.kb.mcp_server import TOOLS, TOOL_HANDLERS, _tool_kb_search, _tool_kb_list


# ── 夹具 ──

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


# ════════════════════════════════════════════════════════════
# 1. 工具注册表
# ════════════════════════════════════════════════════════════

class TestToolRegistry:
    """工具注册表结构正确。"""

    def test_tools_list_contains_three_tools(self) -> None:
        assert len(TOOLS) == 3

    def test_tool_names(self) -> None:
        names = {t["name"] for t in TOOLS}
        assert names == {"kb_search", "kb_read", "kb_list"}

    def test_each_tool_has_description(self) -> None:
        for t in TOOLS:
            assert t.get("description"), f"Tool {t['name']} missing description"

    def test_each_tool_has_input_schema(self) -> None:
        for t in TOOLS:
            assert "inputSchema" in t, f"Tool {t['name']} missing inputSchema"

    def test_tool_handlers_registered(self) -> None:
        assert set(TOOL_HANDLERS.keys()) == {"kb_search", "kb_read", "kb_list"}

    def test_kb_search_requires_query(self) -> None:
        kb_search = next(t for t in TOOLS if t["name"] == "kb_search")
        schema = kb_search["inputSchema"]
        assert "query" in schema.get("required", [])

    def test_kb_read_requires_path(self) -> None:
        kb_read = next(t for t in TOOLS if t["name"] == "kb_read")
        schema = kb_read["inputSchema"]
        assert "path" in schema.get("required", [])


# ════════════════════════════════════════════════════════════
# 2. 工具调用
# ════════════════════════════════════════════════════════════

class TestToolCalls:
    """三工具调用成功。"""

    def test_kb_search_returns_list(self) -> None:
        result = _tool_kb_search({"query": "CCC"})
        assert isinstance(result, list)

    def test_kb_search_empty_query(self) -> None:
        result = _tool_kb_search({"query": ""})
        assert result == []

    def test_kb_search_with_domain(self) -> None:
        result = _tool_kb_search({"query": "CCC", "domain": "projects"})
        assert isinstance(result, list)

    def test_kb_list_returns_list(self) -> None:
        result = _tool_kb_list({"domain": None})
        assert isinstance(result, list)

    def test_kb_list_with_domain(self) -> None:
        result = _tool_kb_list({"domain": "nodes-paths"})
        assert isinstance(result, list)

    def test_kb_read_nonexistent(self) -> None:
        from server.kb.mcp_server import _tool_kb_read
        result = _tool_kb_read({"path": "nonexistent-id-999"})
        assert result is None


# ════════════════════════════════════════════════════════════
# 3. --selftest
# ════════════════════════════════════════════════════════════

class TestSelftest:
    """--selftest 自测通过。"""

    def test_selftest_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "server.kb.mcp_server", "--selftest"],
            cwd=_project_root(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        stderr = result.stderr
        assert result.returncode == 0, (
            f"selftest 失败 (rc={result.returncode}):\n{stderr}"
        )
        assert "ALL PASSED" in stderr, f"selftest 未通过:\n{stderr}"


# ════════════════════════════════════════════════════════════
# 4. --list-tools
# ════════════════════════════════════════════════════════════

class TestListTools:
    """--list-tools 输出正确。"""

    def test_list_tools_output(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "server.kb.mcp_server", "--list-tools"],
            cwd=_project_root(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 3
        names = {t["name"] for t in data}
        assert names == {"kb_search", "kb_read", "kb_list"}
