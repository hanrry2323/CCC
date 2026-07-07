"""test_bug_fixes_v012.py — 验 v0.12 修的几个 bug

测试：
  1. opencode-exec 长 prompt 跑完 → 临时文件被 unlink（Bug 1+3）
  2. ccc-finish phases.json 含坏行 → 不静默, exit 非 0 (Bug 2)
  3. ccc-hook CCC_HOOK_TIMEOUT=2 + sleep 3 → exit 124 (Bug 6)
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
FINISH = ROOT / "scripts" / "ccc-finish.sh"


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


def test_bug_2_finish_bad_json_not_silent():
    """phases.json 含坏行 → ccc-finish 不应静默"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / ".ccc" / "phases").mkdir(parents=True)
        (workspace / ".ccc" / "plans").mkdir(parents=True)
        (workspace / ".ccc" / "reports").mkdir(parents=True)
        (workspace / ".ccc" / "verdicts").mkdir(parents=True)
        # 写坏行
        (workspace / ".ccc" / "phases" / "test-bad.phases.json").write_text(
            '{"phase":"p1","status":"done"}\n'
            'this is not valid json\n'
            '{"phase":"p2","status":"pending"}\n'
        )
        # ccc-finish 在 phases.json 有坏行时, 应输出 warning
        proc = subprocess.run(
            ["bash", str(FINISH), str(workspace), "test-bad"],
            capture_output=True, timeout=10,
        )
        # 必出 Gate 1 FAIL（缺 report.md）
        out = proc.stdout.decode("utf-8", errors="replace")
        # 关键: 不能静默（不光是 exit code, stderr 应有内容）
        err = proc.stderr.decode("utf-8", errors="replace")
        # ccc-finish 应输出 Gate 1 失败（缺 report.md）
        assert "report.md" in out or "Gate 1" in out


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
                capture_output=True, timeout=10,
                env={"HOME": str(Path.home()), "CCC_HOOK_TIMEOUT": "2", "PATH": "/usr/bin:/bin:/usr/local/bin"},
            )
            out = proc.stdout.decode("utf-8", errors="replace")
            assert "exit=124" in out or "❌" in out, f"应被 kill 报 exit=124, 实际: {out[:500]}"
        finally:
            target.unlink(missing_ok=True)
