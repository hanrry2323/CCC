"""v0.42: get_recent_lessons 过滤 stub"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from _lessons import get_recent_lessons, record_failure


def test_stub_filtered_closed_loop_kept(tmp_path):
    lessons = tmp_path / ".ccc" / "lessons"
    lessons.mkdir(parents=True)

    (lessons / "stub1.json").write_text(
        json.dumps(
            {
                "task_id": "stub1",
                "phase": 1,
                "error": "fail",
                "analysis": "",
                "timestamp": "2026-07-17T01:00:00",
                "fixed": False,
            }
        )
    )
    (lessons / "stub2.json").write_text(
        json.dumps(
            {
                "task_id": "stub2",
                "phase": 1,
                "error": "fail",
                "analysis": "未匹配到已知失败模式，待人工分析",
                "timestamp": "2026-07-17T02:00:00",
                "fixed": False,
            }
        )
    )
    (lessons / "real.json").write_text(
        json.dumps(
            {
                "task_id": "real",
                "phase": 2,
                "error": "timeout",
                "analysis": "opencode 卡在 scope 外文件；应收紧白名单",
                "timestamp": "2026-07-17T03:00:00",
                "fixed": False,
            }
        )
    )

    recent = get_recent_lessons(tmp_path, count=50)
    ids = [r["task_id"] for r in recent]
    assert ids == ["real"]
    assert "stub1" not in ids
    assert "stub2" not in ids


def test_record_failure_empty_analysis_is_stub(tmp_path):
    record_failure(tmp_path, "t1", 1, "boom", analysis="")
    assert get_recent_lessons(tmp_path) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
