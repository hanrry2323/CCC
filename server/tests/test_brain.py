"""server/web/brain.py 补充测试（Task-014：提升覆盖率至80%）。

覆盖以下模块：
1. 配置读取：_get_brain_max_concurrency, _get_brain_model_tiers, _brain_cfg, _get_brain_timeout
2. 知识库检索：_retrieve_kb_context
3. Claude CLI调用：_run_claude
4. 流式事件归一化：_normalize_stream_event
5. 子进程终止：_terminate_proc
6. 流式调用：_stream_claude, _stream_relay_direct
"""

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# 1. 配置读取测试
# ═══════════════════════════════════════════════════════════════════

class TestConfigReading:
    """配置读取相关函数测试。"""

    def test_get_brain_max_concurrency_default(self):
        """测试默认最大并发数。"""
        from server.web.brain import _get_brain_max_concurrency

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CCC_BRAIN_MAX_CONCURRENCY", None)
            result = _get_brain_max_concurrency()
            assert result == 2

    def test_get_brain_max_concurrency_custom(self):
        """测试自定义最大并发数。"""
        from server.web.brain import _get_brain_max_concurrency

        with patch.dict(os.environ, {"CCC_BRAIN_MAX_CONCURRENCY": "4"}):
            result = _get_brain_max_concurrency()
            assert result == 4

    def test_get_brain_max_concurrency_invalid(self):
        """测试无效的最大并发数。"""
        from server.web.brain import _get_brain_max_concurrency

        with patch.dict(os.environ, {"CCC_BRAIN_MAX_CONCURRENCY": "invalid"}):
            result = _get_brain_max_concurrency()
            assert result == 2

    def test_get_brain_max_concurrency_zero(self):
        """测试零值最大并发数。"""
        from server.web.brain import _get_brain_max_concurrency

        with patch.dict(os.environ, {"CCC_BRAIN_MAX_CONCURRENCY": "0"}):
            result = _get_brain_max_concurrency()
            assert result == 1  # max(1, 0) = 1

    def test_get_brain_model_tiers_default(self):
        """测试默认模型档位。"""
        from server.web.brain import _get_brain_model_tiers

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CCC_MODEL_TIERS", None)
            result = _get_brain_model_tiers()
            assert result == ["flash", "code"]

    def test_get_brain_model_tiers_custom(self):
        """测试自定义模型档位。"""
        from server.web.brain import _get_brain_model_tiers

        with patch.dict(os.environ, {"CCC_MODEL_TIERS": "flash,pro,code"}):
            result = _get_brain_model_tiers()
            assert result == ["flash", "pro", "code"]

    def test_get_brain_model_tiers_empty(self):
        """测试空模型档位。"""
        from server.web.brain import _get_brain_model_tiers

        with patch.dict(os.environ, {"CCC_MODEL_TIERS": ""}):
            result = _get_brain_model_tiers()
            assert result == []

    def test_brain_cfg_from_env(self):
        """测试从环境变量读取配置。"""
        from server.web.brain import _brain_cfg

        with patch.dict(os.environ, {"TEST_CONFIG_KEY": "test_value"}):
            result = _brain_cfg("TEST_CONFIG_KEY")
            assert result == "test_value"

    def test_brain_cfg_from_config_env(self):
        """测试从config.env文件读取配置。"""
        from server.web.brain import _brain_cfg

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("MY_CONFIG=value_from_file\n")
            f.write("# comment line\n")
            f.write("OTHER=value\n")
            config_path = f.name

        try:
            with patch.dict(os.environ, {"CCC_CONFIG_ENV": config_path}):
                result = _brain_cfg("MY_CONFIG")
                assert result == "value_from_file"
        finally:
            os.unlink(config_path)

    def test_brain_cfg_env_priority_over_file(self):
        """测试环境变量优先于config.env文件。"""
        from server.web.brain import _brain_cfg

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("MY_CONFIG=value_from_file\n")
            config_path = f.name

        try:
            with patch.dict(os.environ, {"CCC_CONFIG_ENV": config_path, "MY_CONFIG": "value_from_env"}):
                result = _brain_cfg("MY_CONFIG")
                assert result == "value_from_env"
        finally:
            os.unlink(config_path)

    def test_brain_cfg_default_value(self):
        """测试默认值。"""
        from server.web.brain import _brain_cfg

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NONEXISTENT_KEY", None)
            os.environ.pop("CCC_CONFIG_ENV", None)
            result = _brain_cfg("NONEXISTENT_KEY", "default")
            assert result == "default"

    def test_brain_cfg_invalid_file(self):
        """测试无效的config.env文件路径。"""
        from server.web.brain import _brain_cfg

        with patch.dict(os.environ, {"CCC_CONFIG_ENV": "/nonexistent/path.env"}):
            result = _brain_cfg("KEY", "default")
            assert result == "default"

    def test_get_brain_timeout_default(self):
        """测试默认超时时间。"""
        from server.web.brain import _get_brain_timeout

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CCC_BRAIN_TIMEOUT", None)
            os.environ.pop("CCC_CONFIG_ENV", None)
            result = _get_brain_timeout()
            assert result == 300

    def test_get_brain_timeout_custom(self):
        """测试自定义超时时间。"""
        from server.web.brain import _get_brain_timeout

        with patch.dict(os.environ, {"CCC_BRAIN_TIMEOUT": "120"}):
            result = _get_brain_timeout()
            assert result == 120

    def test_get_brain_timeout_invalid(self):
        """测试无效的超时时间。"""
        from server.web.brain import _get_brain_timeout

        with patch.dict(os.environ, {"CCC_BRAIN_TIMEOUT": "invalid"}):
            result = _get_brain_timeout()
            assert result == 300


# ═══════════════════════════════════════════════════════════════════
# 2. 知识库检索测试
# ═══════════════════════════════════════════════════════════════════

class TestKBRetrieval:
    """知识库检索测试。"""

    def test_retrieve_kb_context_disabled(self):
        """测试知识库检索禁用。"""
        from server.web.brain import _retrieve_kb_context

        with patch.dict(os.environ, {"CCC_BRAIN_KB": "0"}):
            result = _retrieve_kb_context("test query")
            assert result == ""

    def test_retrieve_kb_context_empty_results(self):
        """测试空检索结果。"""
        from server.web.brain import _retrieve_kb_context

        with patch.dict(os.environ, {"CCC_BRAIN_KB": "1"}):
            with patch("server.web.brain._get_brain_kb_index_dir", return_value=""):
                with patch("server.kb.service.search", return_value=[]):
                    result = _retrieve_kb_context("test query")
                    assert result == ""

    def test_retrieve_kb_context_with_results(self):
        """测试有检索结果。"""
        from server.web.brain import _retrieve_kb_context

        mock_results = [
            {"section": "§1", "id": "doc1::Title1", "snippet": "snippet1"},
            {"section": "§2", "id": "doc2::Title2", "snippet": "snippet2"},
        ]

        with patch.dict(os.environ, {"CCC_BRAIN_KB": "1"}):
            with patch("server.web.brain._get_brain_kb_index_dir", return_value="/test"):
                with patch("server.kb.service.search", return_value=mock_results):
                    result = _retrieve_kb_context("test query")
                    assert "知识库参考" in result
                    assert "Title1" in result
                    assert "snippet1" in result
                    assert "Title2" in result

    def test_retrieve_kb_context_exception(self):
        """测试检索异常。"""
        from server.web.brain import _retrieve_kb_context

        with patch.dict(os.environ, {"CCC_BRAIN_KB": "1"}):
            with patch("server.web.brain._get_brain_kb_index_dir", return_value="/test"):
                with patch("server.kb.service.search", side_effect=Exception("search error")):
                    result = _retrieve_kb_context("test query")
                    assert result == ""


# ═══════════════════════════════════════════════════════════════════
# 3. Claude CLI调用测试
# ═══════════════════════════════════════════════════════════════════

class TestRunClaude:
    """Claude CLI调用测试。"""

    def test_run_claude_success(self):
        """测试成功调用Claude CLI。"""
        from server.web.brain import _run_claude

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Hello, I am Claude."
        mock_proc.stderr = ""

        with patch("server.web.brain._get_brain_claude_bin", return_value="claude"):
            with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain._get_brain_model", return_value="claude-3"):
                        with patch("server.web.brain.subprocess.run", return_value=mock_proc):
                            success, output, error_kind = _run_claude("test prompt", 300)
                            assert success is True
                            assert output == "Hello, I am Claude."
                            assert error_kind is None

    def test_run_claude_timeout(self):
        """测试Claude CLI超时。"""
        from server.web.brain import _run_claude

        with patch("server.web.brain._get_brain_claude_bin", return_value="claude"):
            with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain._get_brain_model", return_value="claude-3"):
                        with patch("server.web.brain.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)):
                            success, output, error_kind = _run_claude("test prompt", 300)
                            assert success is False
                            assert output == "brain timeout"
                            assert error_kind == "timeout"

    def test_run_claude_file_not_found(self):
        """测试Claude CLI不存在。"""
        from server.web.brain import _run_claude

        with patch("server.web.brain._get_brain_claude_bin", return_value="nonexistent"):
            with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain._get_brain_model", return_value="claude-3"):
                        with patch("server.web.brain.subprocess.run", side_effect=FileNotFoundError("not found")):
                            success, output, error_kind = _run_claude("test prompt", 300)
                            assert success is False
                            assert "brain failed" in output
                            assert error_kind == "failed"

    def test_run_claude_nonzero_exit(self):
        """测试Claude CLI非零退出码。"""
        from server.web.brain import _run_claude

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Error: something went wrong"

        with patch("server.web.brain._get_brain_claude_bin", return_value="claude"):
            with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain._get_brain_model", return_value="claude-3"):
                        with patch("server.web.brain.subprocess.run", return_value=mock_proc):
                            success, output, error_kind = _run_claude("test prompt", 300)
                            assert success is False
                            assert "brain failed" in output
                            assert error_kind == "failed"

    def test_run_claude_empty_output(self):
        """测试Claude CLI空输出。"""
        from server.web.brain import _run_claude

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        with patch("server.web.brain._get_brain_claude_bin", return_value="claude"):
            with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain._get_brain_model", return_value="claude-3"):
                        with patch("server.web.brain.subprocess.run", return_value=mock_proc):
                            success, output, error_kind = _run_claude("test prompt", 300)
                            assert success is False
                            assert "empty content" in output
                            assert error_kind == "failed"


# ═══════════════════════════════════════════════════════════════════
# 4. 流式事件归一化测试
# ═══════════════════════════════════════════════════════════════════

class TestNormalizeStreamEvent:
    """流式事件归一化测试。"""

    def test_normalize_system_init(self):
        """测试system/init事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "system",
            "subtype": "init",
            "model": "claude-3",
            "tools": ["tool1"],
            "mcp_servers": ["mcp1"],
            "skills": ["skill1"],
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "meta"
        assert result[1]["model"] == "claude-3"
        assert result[1]["tools"] == ["tool1"]

    def test_normalize_assistant_text(self):
        """测试assistant text事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello, I am Claude."}
                ]
            },
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "text"
        assert result[1]["text"] == "Hello, I am Claude."

    def test_normalize_assistant_thinking(self):
        """测试assistant thinking事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "data": "thinking content"}
                ]
            },
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "thinking"
        assert result[1]["data"] == "thinking content"

    def test_normalize_assistant_tool_use(self):
        """测试assistant tool_use事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "tool123", "name": "Read", "input": {"path": "/test"}}
                ]
            },
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "tool_use"
        assert result[1]["id"] == "tool123"
        assert result[1]["name"] == "Read"

    def test_normalize_user_tool_result(self):
        """测试user tool_result事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool123", "content": "file content"}
                ]
            },
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "tool_result"
        assert result[1]["tool_use_id"] == "tool123"
        assert result[1]["content"] == "file content"

    def test_normalize_result_done(self):
        """测试result done事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "result",
            "is_error": False,
            "result": "final text",
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "done"
        assert result[1]["text"] == "final text"
        assert result[1]["is_error"] is False

    def test_normalize_result_error(self):
        """测试result error事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "result",
            "is_error": True,
            "result": "",
            "api_error_status": "error message",
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "done"
        assert result[1]["is_error"] is True
        assert result[1]["error"] == "error message"

    def test_normalize_stream_event_text_delta(self):
        """测试stream_event text_delta事件。"""
        from server.web.brain import _normalize_stream_event

        event = {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "chunk text"},
            },
        }
        result = _normalize_stream_event(event)
        assert result is not None
        assert result[0] == "text"
        assert result[1]["text"] == "chunk text"

    def test_normalize_unknown_type(self):
        """测试未知事件类型。"""
        from server.web.brain import _normalize_stream_event

        event = {"type": "unknown_type"}
        result = _normalize_stream_event(event)
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# 5. 子进程终止测试
# ═══════════════════════════════════════════════════════════════════

class TestTerminateProc:
    """子进程终止测试。"""

    def test_terminate_proc_already_exited(self):
        """测试子进程已退出。"""
        from server.web.brain import _terminate_proc

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 已退出
        mock_proc.pid = 1234

        _terminate_proc(mock_proc)
        mock_proc.kill.assert_not_called()

    def test_terminate_proc_running(self):
        """测试终止运行中的子进程。"""
        from server.web.brain import _terminate_proc
        import signal

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 运行中
        mock_proc.pid = 1234

        with patch("server.web.brain.os.getpgid", return_value=5678):
            with patch("server.web.brain.os.getpgrp", return_value=9999):
                with patch("server.web.brain.os.killpg") as mock_killpg:
                    _terminate_proc(mock_proc)
                    mock_killpg.assert_called_once_with(5678, signal.SIGKILL)

    def test_terminate_proc_same_group(self):
        """测试子进程在同一进程组。"""
        from server.web.brain import _terminate_proc

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 1234

        with patch("server.web.brain.os.getpgid", return_value=9999):
            with patch("server.web.brain.os.getpgrp", return_value=9999):
                _terminate_proc(mock_proc)
                mock_proc.kill.assert_called_once()

    def test_terminate_proc_no_pid(self):
        """测试子进程无PID。"""
        from server.web.brain import _terminate_proc

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = None

        _terminate_proc(mock_proc)
        mock_proc.kill.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 6. 流式调用测试
# ═══════════════════════════════════════════════════════════════════

class TestStreamClaude:
    """流式调用测试。"""

    def test_stream_claude_direct_mode(self):
        """测试直连模式。"""
        from server.web.brain import _stream_claude

        with patch("server.web.brain._get_brain_direct", return_value=True):
            with patch("server.web.brain._stream_relay_direct") as mock_relay:
                mock_relay.return_value = iter([("meta", {"model": "test"})])
                result = list(_stream_claude("test prompt"))
                mock_relay.assert_called_once()

    def test_stream_claude_process_not_found(self):
        """测试Claude CLI不存在时回退到直连。"""
        from server.web.brain import _stream_claude

        with patch("server.web.brain._get_brain_direct", return_value=False):
            with patch("server.web.brain._get_brain_claude_bin", return_value="nonexistent"):
                with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
                    with patch("server.web.brain._get_brain_auth_token", return_value="token"):
                        with patch("server.web.brain._effective_model", return_value="model"):
                            with patch("server.web.brain._get_brain_thinking", return_value=""):
                                with patch("server.web.brain._stream_relay_direct") as mock_relay:
                                    mock_relay.return_value = iter([])
                                    result = list(_stream_claude("test prompt"))
                                    mock_relay.assert_called()


# ═══════════════════════════════════════════════════════════════════
# 7. 直连中继测试
# ═══════════════════════════════════════════════════════════════════

class TestStreamRelayDirect:
    """直连中继测试。"""

    def test_stream_relay_direct_anthropic(self):
        """测试Anthropic协议直连。"""
        from server.web.brain import _stream_relay_direct

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [
            b'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}}\n',
            b'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}\n',
            b'',
        ]

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_resp

        with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
            with patch("server.web.brain._effective_model", return_value="claude-3"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain.http.client.HTTPConnection", return_value=mock_conn):
                        result = list(_stream_relay_direct("test prompt"))
                        assert len(result) >= 2
                        assert result[0][0] == "meta"

    def test_stream_relay_direct_openai(self):
        """测试OpenAI协议直连。"""
        from server.web.brain import _stream_relay_direct

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n',
            b'data: [DONE]\n',
            b'',
        ]

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_resp

        with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6102"):
            with patch("server.web.brain._effective_model", return_value="deepseek-chat"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain.http.client.HTTPConnection", return_value=mock_conn):
                        result = list(_stream_relay_direct("test prompt"))
                        assert len(result) >= 2
                        assert result[0][0] == "meta"

    def test_stream_relay_direct_error_response(self):
        """测试直连中继错误响应。"""
        from server.web.brain import _stream_relay_direct

        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.read.return_value = b"Internal Server Error"

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_resp

        with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
            with patch("server.web.brain._effective_model", return_value="claude-3"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain.http.client.HTTPConnection", return_value=mock_conn):
                        result = list(_stream_relay_direct("test prompt"))
                        assert result[0][0] == "error"
                        assert result[0][1]["status"] == 500

    def test_stream_relay_direct_connection_error(self):
        """测试直连中继连接错误。"""
        from server.web.brain import _stream_relay_direct

        with patch("server.web.brain._get_brain_base_url", return_value="http://127.0.0.1:6100"):
            with patch("server.web.brain._effective_model", return_value="claude-3"):
                with patch("server.web.brain._get_brain_auth_token", return_value="token123"):
                    with patch("server.web.brain.http.client.HTTPConnection", side_effect=ConnectionRefusedError("refused")):
                        result = list(_stream_relay_direct("test prompt"))
                        assert result[0][0] == "error"
                        assert result[0][1]["status"] == 502
