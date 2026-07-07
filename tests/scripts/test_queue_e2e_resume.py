"""test_queue_e2e_resume.py — 验 ccc-queue.sh 断点续跑场景

场景:
  - 3 个 pending phase
  - 跑第 1 轮:fake launcher 让 phase-2 失败,队列暂停
  - 把 phase-2 改回 pending
  - 跑第 2 轮:fake launcher 全成功
  - 预期:两轮结束后所有 phase 都 done

注:当前 ccc-queue.sh 不跳过已 done 的 phase,会重跑所有 phase。
fake launcher 的责任是:遇到 done 立即 exit 0(不重复处理)。
这模拟"已完成 phase 跳过"的语义。
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
    p = tmp_path / "fake-launcher.sh"
    p.write_text("#!/bin/bash\n" + body)
    p.chmod(0o755)
    return p


def _read_phase_status(phases_file: Path) -> dict[str, str]:
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


def _set_phase_status(phases_file: Path, phase_id: str, status: str) -> None:
    """重写 JSONL phases.json,设指定 phase 的 status"""
    lines = []
    with open(phases_file) as f:
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            obj = json.loads(line)
            pid = obj.get("phase") or obj.get("phase_id")
            if pid == phase_id:
                obj["status"] = status
            lines.append(json.dumps(obj, ensure_ascii=False))
    with open(phases_file, "w") as f:
        f.write("\n".join(lines) + "\n")


def test_queue_resume_after_partial(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "phases").mkdir(parents=True)

    phases_file = workspace / ".ccc" / "phases" / "test-resume.phases.json"
    with open(phases_file, "w") as f:
        for i in range(1, 4):
            f.write(json.dumps({"phase": f"phase-{i}", "status": "pending"}) + "\n")

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()

    # fake launcher 逻辑:
    #   1. 读 phases.json,如果当前 phase 已 done → 跳过(exit 0)
    #   2. 否则:用 .ccc/phases/.fake-fail-<phase_id> 标记决定行为
    #   3. 如果 .fake-fail-<phase_id> 存在 → 永远失败(exit 1,触发 max retries 后队列 pause)
    #   4. 否则 → 成功(exit 0) + 写 done
    # 测试流程:
    #   轮 1: phase-1 成功,phase-2 被 fake-fail 标记 → 永远失败 → 队列 pause
    #   手动: 清 fake-fail-phase-2 + phase-2 改回 pending
    #   轮 2: phase-1 已 done 跳过,phase-2 成功,phase-3 成功
    fake = _write_fake_launcher(
        tmp_path,
        f"""\
PHASE_ID="${{1:-}}"
PHASES_FILE="{phases_file}"
FAIL_FLAG="{workspace}/.ccc/phases/.fake-fail-$PHASE_ID"

# 检查 phases.json 当前 status
CURRENT_STATUS=$(grep -F "\\"phase\\": \\"$PHASE_ID\\"" "$PHASES_FILE" 2>/dev/null \\
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('status',''))" 2>/dev/null \\
  || echo "")

if [[ "$CURRENT_STATUS" == "done" ]]; then
  echo "  [fake] $PHASE_ID 已 done → 跳过" >&2
  exit 0
fi

if [[ -f "$FAIL_FLAG" ]]; then
  echo "  [fake] $PHASE_ID 标记 fail → 永远失败" >&2
  exit 1
fi

echo "  [fake] $PHASE_ID 成功" >&2
exit 0
""",
    )

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["CCC_LAUNCHER_OVERRIDE"] = str(fake)

    # === 第 1 轮:设 fail flag,phase-2 永远失败 → 队列 pause ===
    fail_flag = workspace / ".ccc" / "phases" / ".fake-fail-phase-2"
    fail_flag.touch()

    proc1 = subprocess.run(
        ["bash", str(QUEUE), str(workspace), "test-resume"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc1.returncode == 5, (
        f"第 1 轮应 exit 5(暂停),实际 {proc1.returncode}\n"
        f"stdout:\n{proc1.stdout}\nstderr:\n{proc1.stderr}"
    )

    s1 = _read_phase_status(phases_file)
    assert s1["phase-1"] == "done", f"第 1 轮后 phase-1 应 done:{s1}"
    assert s1["phase-2"] == "pending", f"第 1 轮后 phase-2 应 pending:{s1}"
    assert s1["phase-3"] == "pending", f"第 1 轮后 phase-3 应 pending:{s1}"

    # === 模拟"老板拍板" → 清 fail flag + phase-2 改回 pending ===
    fail_flag.unlink()
    _set_phase_status(phases_file, "phase-2", "pending")

    # === 第 2 轮:phase-1 已 done 跳过,phase-2 成功,phase-3 成功 ===
    proc2 = subprocess.run(
        ["bash", str(QUEUE), str(workspace), "test-resume"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert proc2.returncode == 0, (
        f"第 2 轮应 exit 0,实际 {proc2.returncode}\n"
        f"stdout:\n{proc2.stdout}\nstderr:\n{proc2.stderr}"
    )

    s2 = _read_phase_status(phases_file)
    assert s2 == {
        "phase-1": "done",
        "phase-2": "done",
        "phase-3": "done",
    }, f"第 2 轮后应全 done,实际:{s2}"
