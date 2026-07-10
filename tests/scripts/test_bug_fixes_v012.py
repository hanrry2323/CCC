"""test_bug_fixes_v012.py — 验 v0.12 修的几个 bug

测试：
  1. opencode-exec 长 prompt 跑完 → 临时文件被 unlink（Bug 1+3）
  2. ccc-hook CCC_HOOK_TIMEOUT=2 + sleep 3 → exit 124 (Bug 6)
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
EXEC = ROOT / "scripts" / "opencode-exec.py"
HOOK = ROOT / "scripts" / "ccc-hook.sh"


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_opencode_exec_v012", str(EXEC))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_bug_1_3_long_prompt_tmp_file_cleaned():
    """长 prompt 跑完, 临时文件应被 unlink（不再泄漏）"""
    import asyncio

    m = _load_module()
    # 用 echo 模拟 opencode（短 cmd 必不调真模型）
    long_prompt = "X" * 300  # > 200 触发 --file 协议

    async def main():
        return await m.run_opencode(
            phase_id="bug-1-3-test",
            prompt_text=long_prompt,
            timeout=10,
            cwd=None,
            cmd=["echo", "ok"],  # 短 cmd 不调真模型
        )

    result = asyncio.run(main())
    assert result["exit_code"] == 0

    # 验证临时文件已被 unlink
    leftover = list(Path("/tmp").glob("tmp*.md"))
    leftover += list(Path("/var/folders").glob("**/tmp*.md"))
    leftover = [p for p in leftover if p.exists()]
    # 我们的 test phase_id 是 bug-1-3-test
    bug_files = [p for p in leftover if p.stat().st_mtime > time.time() - 60]
    assert not bug_files, f"残留临时文件: {bug_files}"


def test_executor_sanitized_env_catches_access_key():
    """_sanitized_env 应过滤 ACCESS_KEY / CERTIFICATE / PRIVATE_KEY 等（H1 修复）"""
    import importlib.util
    import os
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "_executor", str(ROOT / "scripts" / "_executor.py")
    )
    executor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(executor)

    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
    os.environ["AZURE_CLIENT_SECRET"] = "secret-value"
    os.environ["MY_PRIVATE_KEY"] = "-----BEGIN RSA PRIVATE KEY-----"
    os.environ["SSH_CERTIFICATE"] = "ssh-rsa-cert..."
    os.environ["SESSION_TOKEN"] = "session-token-value"

    env = executor._sanitized_env()

    assert "AWS_ACCESS_KEY_ID" not in env, "AWS_ACCESS_KEY_ID 应被过滤"
    assert "AZURE_CLIENT_SECRET" not in env, "AZURE_CLIENT_SECRET 应被过滤"
    assert "MY_PRIVATE_KEY" not in env, "MY_PRIVATE_KEY 应被过滤"
    assert "SSH_CERTIFICATE" not in env, "SSH_CERTIFICATE 应被过滤"
    assert "SESSION_TOKEN" not in env, "SESSION_TOKEN 应被过滤"

    for key in [
        "AWS_ACCESS_KEY_ID",
        "AZURE_CLIENT_SECRET",
        "MY_PRIVATE_KEY",
        "SSH_CERTIFICATE",
        "SESSION_TOKEN",
    ]:
        os.environ.pop(key, None)


def test_bug_6_hook_timeout_override():
    """CCC_HOOK_TIMEOUT 可配，timeout=2 + sleep 3 应被 kill"""
    with tempfile.TemporaryDirectory() as tmpdir:
        slow_hook = Path(tmpdir) / "slow.sh"
        slow_hook.write_text("#!/bin/bash\nsleep 3\necho done\n")
        slow_hook.chmod(0o755)

        # 复制到 ~/.ccc/hooks/ 让 ccc-hook 找到
        hook_dir = Path.home() / ".ccc" / "hooks"
        hook_dir.mkdir(parents=True, exist_ok=True)
        target = hook_dir / "test-bug-6.sh"
        target.write_text(slow_hook.read_text())
        target.chmod(0o755)

        try:
            # CCC_HOOK_TIMEOUT=2 + sleep 3 → 应被 kill (exit 124)
            proc = subprocess.run(
                ["bash", str(HOOK), "test-bug-6"],
                capture_output=True,
                timeout=10,
                env={
                    "HOME": str(Path.home()),
                    "CCC_HOOK_TIMEOUT": "2",
                    "PATH": "/usr/bin:/bin:/usr/local/bin",
                },
            )
            out = proc.stdout.decode("utf-8", errors="replace")
            assert "exit=124" in out or "❌" in out, (
                f"应被 kill 报 exit=124, 实际: {out[:500]}"
            )
        finally:
            target.unlink(missing_ok=True)
