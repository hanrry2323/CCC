"""dsh_reader.py 测试（Task-008：提升覆盖率至60%）。

覆盖以下模块：
1. 数据根目录：dsh_data_root
2. 注册表读取：_workspace_registry
3. 解压函数：_decompress
4. 会话目录：_session_dir
5. 事件解析：_events
6. 文本提取：_text_blocks
7. 系统噪音检测：_is_sys_noise
8. 历史提取：_extract_history
9. 元数据提取：_session_meta
10. 会话加载：load_session_messages
11. Workspace加载：_load_workspaces_raw, load_workspaces
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# 1. 数据根目录测试
# ═══════════════════════════════════════════════════════════════════

class TestDshDataRoot:
    """DSH数据根目录测试。"""

    def test_dsh_data_root_default(self):
        """测试默认数据根目录。"""
        from server.web.dsh_reader import dsh_data_root

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DSH_DATA_DIR", None)
            result = dsh_data_root()
            assert isinstance(result, Path)
            assert result.name == ".dsh"

    def test_dsh_data_root_env(self):
        """测试环境变量配置的数据根目录。"""
        from server.web.dsh_reader import dsh_data_root

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"DSH_DATA_DIR": tmpdir}):
                result = dsh_data_root()
                assert result == Path(tmpdir).resolve()

    def test_dsh_data_root_expanded(self):
        """测试路径展开。"""
        from server.web.dsh_reader import dsh_data_root

        with patch.dict(os.environ, {"DSH_DATA_DIR": "~/test-dsh"}):
            result = dsh_data_root()
            assert "~" not in str(result)
            assert result.is_absolute()


# ═══════════════════════════════════════════════════════════════════
# 2. 注册表读取测试
# ═══════════════════════════════════════════════════════════════════

class TestWorkspaceRegistry:
    """注册表读取测试。"""

    def test_workspace_registry_not_found(self):
        """测试注册表不存在。"""
        from server.web.dsh_reader import _workspace_registry

        with patch("server.web.dsh_reader.dsh_data_root") as mock_root:
            mock_root.return_value = Path("/nonexistent/path")
            result = _workspace_registry()
            assert result is None

    def test_workspace_registry_invalid_json(self):
        """测试无效JSON。"""
        from server.web.dsh_reader import _workspace_registry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            storage_dir = root / "storages"
            storage_dir.mkdir()
            (storage_dir / "workspace.json").write_text("invalid json")

            with patch("server.web.dsh_reader.dsh_data_root", return_value=root):
                result = _workspace_registry()
                assert result is None

    def test_workspace_registry_valid(self):
        """测试有效注册表。"""
        from server.web.dsh_reader import _workspace_registry

        registry_data = {
            "global": {"workspaceIds": ["ws1"], "archivedSessionIds": []},
            "tables": {"workspaces": {}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            storage_dir = root / "storages"
            storage_dir.mkdir()
            (storage_dir / "workspace.json").write_text(json.dumps(registry_data))

            with patch("server.web.dsh_reader.dsh_data_root", return_value=root):
                result = _workspace_registry()
                assert result is not None
                assert "global" in result


# ═══════════════════════════════════════════════════════════════════
# 3. 解压函数测试
# ═══════════════════════════════════════════════════════════════════

class TestDecompress:
    """解压函数测试。"""

    def test_decompress_file_not_found(self):
        """测试文件不存在。"""
        from server.web.dsh_reader import _decompress

        result = _decompress(Path("/nonexistent/file.zstd"))
        assert result == ""

    def test_decompress_zstd_missing(self):
        """测试zstd命令不存在。"""
        from server.web.dsh_reader import _decompress

        with patch("server.web.dsh_reader._ZSTD_CANDIDATES", []):
            result = _decompress(Path("/some/file.zstd"))
            assert result == ""

    def test_decompress_success(self):
        """测试解压成功。"""
        from server.web.dsh_reader import _decompress

        # Mock subprocess.run返回成功结果
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b'{"type": "test"}\n'

        with patch("server.web.dsh_reader.subprocess.run", return_value=mock_result):
            result = _decompress(Path("/some/file.zstd"))
            assert result == '{"type": "test"}\n'

    def test_decompress_timeout(self):
        """测试解压超时。"""
        from server.web.dsh_reader import _decompress

        import subprocess as sp

        with patch("server.web.dsh_reader.subprocess.run", side_effect=sp.TimeoutExpired("zstd", 20)):
            result = _decompress(Path("/some/file.zstd"))
            assert result == ""


# ═══════════════════════════════════════════════════════════════════
# 4. 会话目录测试
# ═══════════════════════════════════════════════════════════════════

class TestSessionDir:
    """会话目录测试。"""

    def test_session_dir_not_found(self):
        """测试会话目录不存在。"""
        from server.web.dsh_reader import _session_dir

        with patch("server.web.dsh_reader.dsh_data_root") as mock_root:
            mock_root.return_value = Path("/nonexistent/path")
            result = _session_dir("session-123")
            assert result is None

    def test_session_dir_found(self):
        """测试会话目录存在。"""
        from server.web.dsh_reader import _session_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sessions_dir = root / "sessions" / "workspace1" / "session-abc-123"
            sessions_dir.mkdir(parents=True)

            with patch("server.web.dsh_reader.dsh_data_root", return_value=root):
                result = _session_dir("session-abc-123")
                assert result is not None
                assert result.name == "session-abc-123"

    def test_session_dir_with_uuid(self):
        """测试只传UUID的情况。"""
        from server.web.dsh_reader import _session_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sessions_dir = root / "sessions" / "workspace1" / "session-abc-123"
            sessions_dir.mkdir(parents=True)

            with patch("server.web.dsh_reader.dsh_data_root", return_value=root):
                result = _session_dir("abc-123")
                assert result is not None


# ═══════════════════════════════════════════════════════════════════
# 5. 事件解析测试
# ═══════════════════════════════════════════════════════════════════

class TestEvents:
    """事件解析测试。"""

    def test_events_empty(self):
        """测试空文本。"""
        from server.web.dsh_reader import _events

        result = _events("")
        assert result == []

    def test_events_valid_jsonl(self):
        """测试有效JSONL。"""
        from server.web.dsh_reader import _events

        text = '{"type": "user/message"}\n{"type": "assistant/message"}\n'
        result = _events(text)
        assert len(result) == 2
        assert result[0]["type"] == "user/message"
        assert result[1]["type"] == "assistant/message"

    def test_events_invalid_lines(self):
        """测试包含无效行。"""
        from server.web.dsh_reader import _events

        text = '{"type": "valid"}\ninvalid json\n{"type": "also_valid"}\n'
        result = _events(text)
        assert len(result) == 2

    def test_events_empty_lines(self):
        """测试包含空行。"""
        from server.web.dsh_reader import _events

        text = '{"type": "a"}\n\n\n{"type": "b"}\n'
        result = _events(text)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════
# 6. 文本提取测试
# ═══════════════════════════════════════════════════════════════════

class TestTextBlocks:
    """文本提取测试。"""

    def test_text_blocks_not_list(self):
        """测试非列表输入。"""
        from server.web.dsh_reader import _text_blocks

        assert _text_blocks(None) == ""
        assert _text_blocks("string") == ""
        assert _text_blocks(123) == ""

    def test_text_blocks_empty_list(self):
        """测试空列表。"""
        from server.web.dsh_reader import _text_blocks

        assert _text_blocks([]) == ""

    def test_text_blocks_with_text(self):
        """测试包含text块。"""
        from server.web.dsh_reader import _text_blocks

        content = [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "World"},
        ]
        assert _text_blocks(content) == "Hello World"

    def test_text_blocks_filters_tool_calls(self):
        """测试过滤tool-call。"""
        from server.web.dsh_reader import _text_blocks

        content = [
            {"type": "text", "text": "Before "},
            {"type": "tool-call", "name": "test"},
            {"type": "text", "text": "After"},
        ]
        assert _text_blocks(content) == "Before After"

    def test_text_blocks_non_dict(self):
        """测试非字典元素。"""
        from server.web.dsh_reader import _text_blocks

        content = ["string", 123, None, {"type": "text", "text": "valid"}]
        assert _text_blocks(content) == "valid"


# ═══════════════════════════════════════════════════════════════════
# 7. 系统噪音检测测试
# ═══════════════════════════════════════════════════════════════════

class TestSysNoise:
    """系统噪音检测测试。"""

    def test_is_sys_noise_system_reminder(self):
        """测试system-reminder。"""
        from server.web.dsh_reader import _is_sys_noise

        assert _is_sys_noise("<system-reminder>test</system-reminder>") is True

    def test_is_sys_noise_environment(self):
        """测试environment。"""
        from server.web.dsh_reader import _is_sys_noise

        assert _is_sys_noise("<environment>test</environment>") is True

    def test_is_sys_noise_normal_text(self):
        """测试正常文本。"""
        from server.web.dsh_reader import _is_sys_noise

        assert _is_sys_noise("Hello, how can I help you?") is False

    def test_is_sys_noise_stripped(self):
        """测试带空格的文本。"""
        from server.web.dsh_reader import _is_sys_noise

        assert _is_sys_noise("  <system-reminder>test</system-reminder>  ") is True


# ═══════════════════════════════════════════════════════════════════
# 8. 历史提取测试
# ═══════════════════════════════════════════════════════════════════

class TestExtractHistory:
    """历史提取测试。"""

    def test_extract_history_empty(self):
        """测试空事件列表。"""
        from server.web.dsh_reader import _extract_history

        result = _extract_history([])
        assert result == []

    def test_extract_history_user_message(self):
        """测试用户消息。"""
        from server.web.dsh_reader import _extract_history

        events = [
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "Hello"}]}}
        ]
        result = _extract_history(events)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["message"] == "Hello"

    def test_extract_history_assistant_message(self):
        """测试助手消息。"""
        from server.web.dsh_reader import _extract_history

        events = [
            {
                "type": "assistant/message",
                "data": {"message": {"content": [{"type": "text", "text": "Hi there"}]}},
            }
        ]
        result = _extract_history(events)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["message"] == "Hi there"

    def test_extract_history_filters_sys_noise(self):
        """测试过滤系统噪音。"""
        from server.web.dsh_reader import _extract_history

        events = [
            {
                "type": "user/message",
                "data": {"content": [{"type": "text", "text": "<system-reminder>test</system-reminder>"}]},
            },
            {
                "type": "user/message",
                "data": {"content": [{"type": "text", "text": "Real message"}]},
            },
        ]
        result = _extract_history(events)
        assert len(result) == 1
        assert result[0]["message"] == "Real message"

    def test_extract_history_mixed(self):
        """测试混合消息类型。"""
        from server.web.dsh_reader import _extract_history

        events = [
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "Q1"}]}},
            {"type": "assistant/chunk", "data": {"text": "chunk"}},
            {"type": "assistant/message", "data": {"message": {"content": [{"type": "text", "text": "A1"}]}}},
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "Q2"}]}},
        ]
        result = _extract_history(events)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"


# ═══════════════════════════════════════════════════════════════════
# 9. 元数据提取测试
# ═══════════════════════════════════════════════════════════════════

class TestSessionMeta:
    """元数据提取测试。"""

    def test_session_meta_empty(self):
        """测试空事件。"""
        from server.web.dsh_reader import _session_meta

        title, count = _session_meta([])
        assert title == ""
        assert count == 0

    def test_session_meta_with_messages(self):
        """测试带消息的元数据。"""
        from server.web.dsh_reader import _session_meta

        events = [
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "First message"}]}},
            {"type": "assistant/message", "data": {"message": {"content": [{"type": "text", "text": "Response"}]}}},
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "Second message"}]}},
        ]
        title, count = _session_meta(events)
        assert title == "First message"
        assert count == 3

    def test_session_meta_title_truncated(self):
        """测试标题截断。"""
        from server.web.dsh_reader import _session_meta

        long_text = "A" * 100
        events = [
            {"type": "user/message", "data": {"content": [{"type": "text", "text": long_text}]}},
        ]
        title, count = _session_meta(events)
        assert len(title) == 40
        assert title == "A" * 40

    def test_session_meta_filters_noise(self):
        """测试过滤系统噪音。"""
        from server.web.dsh_reader import _session_meta

        events = [
            {
                "type": "user/message",
                "data": {"content": [{"type": "text", "text": "<system-reminder>noise</system-reminder>"}]},
            },
            {"type": "user/message", "data": {"content": [{"type": "text", "text": "Real title"}]}},
        ]
        title, count = _session_meta(events)
        assert title == "Real title"
        assert count == 1


# ═══════════════════════════════════════════════════════════════════
# 10. 会话加载测试
# ═══════════════════════════════════════════════════════════════════

class TestLoadSessionMessages:
    """会话加载测试。"""

    def test_load_session_messages_not_found(self):
        """测试会话不存在。"""
        from server.web.dsh_reader import load_session_messages

        with patch("server.web.dsh_reader._session_dir", return_value=None):
            result = load_session_messages("nonexistent")
            assert result == []

    def test_load_session_messages_success(self):
        """测试加载成功。"""
        from server.web.dsh_reader import load_session_messages

        session_data = '{"type": "user/message", "data": {"content": [{"type": "text", "text": "Hello"}]}}\n'

        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            zstd_file = session_dir / "session.jsonl.zstd"
            zstd_file.write_text(session_data)

            with patch("server.web.dsh_reader._session_dir", return_value=session_dir):
                with patch("server.web.dsh_reader._decompress", return_value=session_data):
                    result = load_session_messages("test-session")
                    assert len(result) == 1
                    assert result[0]["role"] == "user"


# ═══════════════════════════════════════════════════════════════════
# 11. Workspace加载测试
# ═══════════════════════════════════════════════════════════════════

class TestLoadWorkspaces:
    """Workspace加载测试。"""

    def test_load_workspaces_raw_no_registry(self):
        """测试无注册表。"""
        from server.web.dsh_reader import _load_workspaces_raw

        with patch("server.web.dsh_reader._workspace_registry", return_value=None):
            result = _load_workspaces_raw()
            assert result == []

    def test_load_workspaces_raw_empty(self):
        """测试空注册表。"""
        from server.web.dsh_reader import _load_workspaces_raw

        registry = {
            "global": {"workspaceIds": [], "archivedSessionIds": []},
            "tables": {"workspaces": {}},
        }

        with patch("server.web.dsh_reader._workspace_registry", return_value=registry):
            result = _load_workspaces_raw()
            assert result == []

    def test_load_workspaces_raw_with_workspace(self):
        """测试包含workspace。"""
        from server.web.dsh_reader import _load_workspaces_raw

        registry = {
            "global": {"workspaceIds": ["ws1"], "archivedSessionIds": []},
            "tables": {
                "workspaces": {
                    "ws1": {
                        "path": "/path/to/workspace",
                        "title": "Test Workspace",
                        "sessionIds": [],
                    }
                }
            },
        }

        with patch("server.web.dsh_reader._workspace_registry", return_value=registry):
            result = _load_workspaces_raw()
            assert len(result) == 1
            assert result[0]["title"] == "Test Workspace"

    def test_load_workspaces_cached(self):
        """测试缓存机制。"""
        from server.web.dsh_reader import _workspaces_cache, load_workspaces

        # 设置缓存
        _workspaces_cache["ts"] = 9999999999.0  # 未来时间
        _workspaces_cache["data"] = [{"id": "cached"}]

        result = load_workspaces()
        assert result == [{"id": "cached"}]

        # 重置缓存
        _workspaces_cache["ts"] = 0.0
        _workspaces_cache["data"] = None
