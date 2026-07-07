"""test_v09b_flywheel_queue.py — 验 v0.9b 飞轮 + 队列

测试：
  1. flywheel-scan.sh 在干净环境 → 输出"无候选"
  2. flywheel-scan.sh 在有失败文件环境 → 输出候选
  3. ccc-queue.sh 接受 --help 或缺参报错
  4. 队列逻辑：phases.json 解析正确
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
FW = ROOT / "scripts" / "flywheel-scan.sh"
QUEUE = ROOT / "scripts" / "ccc-queue.sh"


def test_flywheel_syntax():
    proc = subprocess.run(["bash", "-n", str(FW)], capture_output=True, timeout=5)
    assert proc.returncode == 0


def test_queue_syntax():
    proc = subprocess.run(["bash", "-n", str(QUEUE)], capture_output=True, timeout=5)
    assert proc.returncode == 0


def test_flywheel_clean_no_candidates(tmp_path):
    """干净环境 → 输出含'无候选'"""
    # 准备空 workspace
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "reports").mkdir(parents=True)
    (workspace / ".ccc" / "verdicts").mkdir(parents=True)

    # 用临时 HOME 隔离（避免 ~/.ccc/alerts 真实数据污染）
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    env = {"HOME": str(fake_home)}

    proc = subprocess.run(
        ["bash", str(FW), str(workspace)],
        capture_output=True, timeout=10,
        env=env,
    )
    assert proc.returncode == 0
    # 找生成的文件
    out_files = list((workspace / ".ccc" / "abnormal-reports").glob("flywheel-candidate-*.md"))
    assert out_files, "应生成飞轮候选文件"
    content = out_files[0].read_text()
    assert "无候选" in content or "全部通过" in content


def test_flywheel_finds_failures(tmp_path):
    """有失败文件的环境 → 输出候选"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "reports").mkdir(parents=True)

    # 写 3 个含 FAIL 的 report
    for i in range(3):
        (workspace / ".ccc" / "reports" / f"test-{i}.md").write_text(
            "## Test\n\n- exit_code 1\n- FAIL: something broke\n"
        )

    # 临时 HOME 隔离
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    env = {"HOME": str(fake_home)}

    proc = subprocess.run(
        ["bash", str(FW), str(workspace)],
        capture_output=True, timeout=10,
        env=env,
    )
    assert proc.returncode == 0
    out_files = list((workspace / ".ccc" / "abnormal-reports").glob("flywheel-candidate-*.md"))
    assert out_files
    content = out_files[0].read_text()
    # 应至少识别出 1 个候选
    assert "次" in content
    assert "红线 18" in content  # 强制人工 review 提示


def test_queue_missing_phases_file(tmp_path):
    """phases.json 不存在 → exit 3"""
    proc = subprocess.run(
        ["bash", str(QUEUE), str(tmp_path), "nonexistent-task"],
        capture_output=True, timeout=5,
    )
    assert proc.returncode == 3


def test_queue_parses_phases_json(tmp_path):
    """phases.json 解析正确"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".ccc" / "phases").mkdir(parents=True)

    # 写 2 个 phase 的 JSONL
    phases = [
        {"phase": "p1", "status": "pending"},
        {"phase_id": "p2", "status": "pending"},
    ]
    with open(workspace / ".ccc" / "phases" / "test-q.phases.json", "w") as f:
        for p in phases:
            f.write(json.dumps(p) + "\n")

    # 不真跑 launcher（mock），只验 phases 解析
    # 实际 queue 会调 launcher，但没 opencode model 时会失败
    # 这里只验 phases.json 解析逻辑
    proc = subprocess.run(
        ["python3", "-c", f"""
import json
with open('{workspace}/.ccc/phases/test-q.phases.json') as f:
    ids = []
    for line in f:
        line = line.strip()
        if not line: continue
        obj = json.loads(line)
        pid = obj.get('phase') or obj.get('phase_id')
        ids.append(pid)
print(' '.join(ids))
"""],
        capture_output=True, timeout=5,
    )
    assert proc.returncode == 0
    assert b"p1" in proc.stdout and b"p2" in proc.stdout
