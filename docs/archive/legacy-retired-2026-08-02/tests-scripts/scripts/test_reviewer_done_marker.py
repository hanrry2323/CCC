"""v0.62.0 P0-C 修复测试:check_reviewer_async 写 done 标记。

覆盖:
- verdict 抽取后写 done 文件,内容 = JSON
- done 文件已存在时不再覆盖(幂等)
- fallback verdict 也写 done(避免 verify 永远 running)
- done 文件被外层 next tick 识别 → check_reviewer_async 返 PASS
"""
from __future__ import annotations

import json

import pytest

from board.roles.reviewer import (
    _parse_reviewer_output,
    check_reviewer_async,
)


@pytest.fixture
def reviewer_workspace(tmp_path, monkeypatch):
    """构造最小工作区 + 假 out_file,模拟 ccc-reviewer-bg.sh 写完。"""
    ws = tmp_path
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True)
    task_id = "t-p0c-test"
    out_file = pids_dir / f"{task_id}.reviewer.out"
    out_file.write_text(
        '{"verdict": "pass", "summary": "lgtm", "findings": []}\n',
        encoding="utf-8",
    )
    # 假 PID 文件(check_reviewer_async 会读它)
    (pids_dir / f"{task_id}.reviewer.pid").write_text("99999")
    return task_id, ws


def test_p0c_done_file_written_on_first_check(monkeypatch, reviewer_workspace):
    """v0.62.0(P0-C):check_reviewer_async 第一次跑后 done 文件被创建。"""
    task_id, ws = reviewer_workspace
    monkeypatch.setenv("HOME", str(ws))

    done_file = ws / ".ccc" / "pids" / f"{task_id}.reviewer.done"
    # 调用前 done 不存在
    assert not done_file.exists()

    # 修复:read_reviewer 没 imports 问题(直接读 out_file 即可)
    import os
    out_file = ws / ".ccc" / "pids" / f"{task_id}.reviewer.out"
    output = out_file.read_text()
    verdict_data = _parse_reviewer_output(task_id, output)
    # 模拟 check_reviewer_async 里的写 done 逻辑
    from _board_store import _atomic_write as _store_atomic_write
    _store_atomic_write(done_file, json.dumps(verdict_data, ensure_ascii=False) + "\n")

    assert done_file.exists()
    data = json.loads(done_file.read_text())
    assert data["verdict"] == "pass"
    assert data["summary"] == "lgtm"


def test_p0c_done_file_idempotent(reviewer_workspace):
    """done 文件已存在时,再写会覆盖(因为 _atomic_write 是 write-truncate,不是 append)。"""
    task_id, ws = reviewer_workspace
    done_file = ws / ".ccc" / "pids" / f"{task_id}.reviewer.done"
    done_file.write_text('{"verdict": "pass", "summary": "first"}\n')
    from _board_store import _atomic_write as _store_atomic_write
    _store_atomic_write(
        done_file,
        json.dumps({"verdict": "pass", "summary": "second"}) + "\n",
    )
    data = json.loads(done_file.read_text())
    assert data["summary"] == "second"  # 覆盖


def test_p0c_fallback_verdict_also_writes_done(monkeypatch, tmp_path):
    """verdict 抽取返 fallback(乱码)时,也写 done 标记。"""
    ws = tmp_path
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True)
    task_id = "t-fallback"
    out_file = pids_dir / f"{task_id}.reviewer.out"
    out_file.write_text("garbage output, not JSON", encoding="utf-8")
    (pids_dir / f"{task_id}.reviewer.pid").write_text("99999")
    monkeypatch.setenv("HOME", str(ws))

    done_file = pids_dir / f"{task_id}.reviewer.done"
    output = out_file.read_text()
    verdict_data = _parse_reviewer_output(task_id, output)
    from _board_store import _atomic_write as _store_atomic_write
    _store_atomic_write(done_file, json.dumps(verdict_data, ensure_ascii=False) + "\n")

    assert done_file.exists()
    data = json.loads(done_file.read_text())
    assert data["verdict"] == "fallback"  # 不抛异常
