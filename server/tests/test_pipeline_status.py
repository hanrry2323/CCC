"""engine-pipeline.json 读写。"""

from __future__ import annotations

from pathlib import Path

from server.engine.pipeline_status import read_pipeline_status, write_pipeline_status


def test_write_and_read_pipeline_status(tmp_path: Path) -> None:
    log_dir = tmp_path / "exec"
    log_dir.mkdir()
    path = write_pipeline_status(
        log_dir,
        {"git_sync_ok": False, "probe_skips": 2, "ok": False},
    )
    assert path is not None
    assert path.is_file()
    data = read_pipeline_status(log_dir)
    assert data is not None
    assert data["git_sync_ok"] is False
    assert data["probe_skips"] == 2
    assert "updated_at" in data
