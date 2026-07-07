"""test_queue_e2e_3phase_pass.py — 验 ccc-queue.sh 跑 3 phase 全成功场景

场景：
  - 3 个 pending phase
  - fake launcher 全 exit 0
  - 预期：queue exit 0，3 个 phase 全标记 done
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE = ROOT / "scripts" / "ccc-queue.sh"


def _write_fake_launcher(tmp_path: Path, body: str) -> Path:
    """写一个 fake launcher,返回路径"""
    p = tmp_path / "fake-launcher.sh"
    p.write_text("#!/bin/bash\n" + body)
    p.chmod(0o755)
    return p


def _read_phase_status(phases_file: Path) -> dict[str, str]:
    """读 JSONL phases.json,返回 {phase_id: status}"""
    out: dict[str, str] = {}
    with open(phases_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            pid = obj.get("phase") or obj.get("phase_id")
            out[pid] = obj.get("status", "")
    return out


def test_queue_3phase_all_pass(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "phases").mkdir(parents=True)

    # 3 个 pending phase 的 JSONL
    phases_file = workspace / ".ccc" / "phases" / "test-3pass.phases.json"
    with open(phases_file, "w") as f:
        for i in range(1, 4):
            f.write(json.dumps({"phase": f"phase-{i}", "status": "pending"}) + "\n")

    # fake launcher 永远 exit 0
    fake = _write_fake_launcher(tmp_path, "exit 0\n")

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["CCC_LAUNCHER_OVERRIDE"] = str(fake)
    # queue 不会自动识别这个 env(它读 argv),但 launcher 通过 argv 拿到 task id
    # 不需要再传 CCC_WORKSPACE:argv 第 1 位传

    proc = subprocess.run(
        ["bash", str(QUEUE), str(workspace), "test-3pass"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc.returncode == 0, (
        f"queue 应 exit 0,实际 {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )

    # 所有 phase 应为 done
    statuses = _read_phase_status(phases_file)
    assert statuses == {
        "phase-1": "done",
        "phase-2": "done",
        "phase-3": "done",
    }, f"phase 状态错误:{statuses}"
