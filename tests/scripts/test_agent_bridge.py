"""测试 _agent_bridge — 文件桥接协议"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from _agent_bridge import AgentBridge, BridgeRun


class TestAgentBridge:
    def test_create_run(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("project-scan", params={"target": "src"}, prompt="请扫描 src 目录")
        assert run.run_id
        assert run.status == "pending"
        assert run.request["action"] == "project-scan"
        assert run.run_dir.exists()
        assert (run.run_dir / "request.json").exists()
        assert (run.run_dir / "prompt.md").exists()
        assert (run.run_dir / "response.json").exists()
        assert (run.run_dir / "artifacts").exists()

    def test_mark_in_progress(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test-task", prompt="test")
        assert run.mark_in_progress()
        loaded = bridge.poll_run(run.run_id)
        assert loaded.status == "in_progress"

    def test_mark_completed(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test-task", prompt="test")
        resp = {"result": "ok", "summary": "all good"}
        assert run.mark_completed(resp)
        loaded = bridge.poll_run(run.run_id)
        assert loaded.status == "completed"

        # 读 response
        r = run.get_response()
        assert r["result"] == "ok"

    def test_mark_failed(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test-task", prompt="do it")
        assert run.mark_failed("something went wrong")
        loaded = bridge.poll_run(run.run_id)
        assert loaded.status == "failed"
        r = run.get_response()
        assert "error" in r

    def test_list_runs(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        bridge.create_run("task-1", prompt="a")
        bridge.create_run("task-2", prompt="b")
        runs = bridge.list_runs()
        assert len(runs) == 2

    def test_list_runs_filter_status(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        r1 = bridge.create_run("task-1", prompt="a")
        r2 = bridge.create_run("task-2", prompt="b")
        r1.mark_completed({"status": "ok"})
        runs = bridge.list_runs(status="completed")
        assert len(runs) == 1
        assert runs[0].run_id == r1.run_id

    def test_wait_run_completed(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test", prompt="go")
        # 模拟 Agent 异步完成
        run.mark_completed({"status": "ok"})
        result = bridge.wait_run(run.run_id, timeout=5)
        assert result is not None
        assert result.status == "completed"

    def test_cleanup_removes_old(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        bridge.create_run("old-task", prompt="old")
        # 模拟过期的 mtime
        for d in bridge._bridge_dir.iterdir():
            if d.is_dir():
                old = time.time() - 48 * 3600  # 48 hours ago
                os.utime(d, (old, old))
        removed = bridge.cleanup(max_age_hours=24)
        assert removed == 1
        assert len(bridge.list_runs()) == 0

    def test_validate_response_is_complete(self, tmp_path):
        """response.json 不会读到半写内容。"""
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test", prompt="test")
        # 直接写 staging
        staging = run.run_dir / ".response.json.tmp"
        final = run.run_dir / "response.json"
        staging.write_text('{"status": "incomplete"}')
        assert not final.exists() or final.read_text() != '{"status": "incomplete"}'
        # 完成
        run.mark_completed({"status": "complete"})
        assert json.loads(final.read_text())["status"] == "complete"

    def test_to_dict(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test", prompt="hello")
        d = run.to_dict()
        assert d["run_id"] == run.run_id
        assert d["status"] == "pending"
        assert d["request"]["action"] == "test"

    def test_instructions_file(self, tmp_path):
        bridge = AgentBridge(tmp_path)
        run = bridge.create_run("test", prompt="do", instructions="no dangerous ops")
        instr_file = run.run_dir / "instructions.md"
        assert instr_file.exists()
        assert instr_file.read_text() == "no dangerous ops"
