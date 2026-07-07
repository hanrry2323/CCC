"""test_queue_e2e_mid_fail.py — 验 ccc-queue.sh 中途失败场景

场景:
  - 3 个 pending phase
  - fake launcher 在 phase-2 时 exit 1
  - 预期:queue exit 5,phase-1 done,phase-2/3 仍 pending
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


def test_queue_mid_fail_pauses(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "phases").mkdir(parents=True)

    phases_file = workspace / ".ccc" / "phases" / "test-midfail.phases.json"
    with open(phases_file, "w") as f:
        for i in range(1, 4):
            f.write(json.dumps({"phase": f"phase-{i}", "status": "pending"}) + "\n")

    # fake launcher:phase-2 时 exit 1
    fake = _write_fake_launcher(
        tmp_path,
        """\
PHASE_ID="${1:-}"
if [[ "$PHASE_ID" == "phase-2" ]]; then
  echo "  [fake] phase-2 故意失败" >&2
  exit 1
fi
exit 0
""",
    )

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["CCC_LAUNCHER_OVERRIDE"] = str(fake)

    proc = subprocess.run(
        ["bash", str(QUEUE), str(workspace), "test-midfail"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )

    # 队列暂停 → exit 5
    assert proc.returncode == 5, (
        f"queue 应 exit 5(暂停),实际 {proc.returncode}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )

    statuses = _read_phase_status(phases_file)
    # phase-1 成功 → done;phase-2 失败 → pending;phase-3 未触达 → pending
    assert statuses["phase-1"] == "done", f"phase-1 应 done,实际 {statuses['phase-1']}"
    assert statuses["phase-2"] == "pending", (
        f"phase-2 应保持 pending,实际 {statuses['phase-2']}"
    )
    assert statuses["phase-3"] == "pending", (
        f"phase-3 应保持 pending,实际 {statuses['phase-3']}"
    )

    # L3 通知应已落到 fakehome/.ccc/alerts
    alerts = list((fake_home / ".ccc" / "alerts").glob("*-L3.md"))
    assert alerts, f"应有 L3 告警文件,实际目录:{fake_home / '.ccc' / 'alerts'}"
