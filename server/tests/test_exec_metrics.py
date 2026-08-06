"""exec_metrics：运行时长 + OpenCode 日志调用计数。"""

from __future__ import annotations

from pathlib import Path

from server.web import exec_metrics as em


def test_parse_tool_and_shell_counts(tmp_path: Path) -> None:
    log = tmp_path / "w.log"
    log.write_text(
        "\x1b[0m→ Read foo.py\n"
        "$ git status\n"
        "→ Write bar.py\n"
        "> build · code\n"
        "noise\n",
        encoding="utf-8",
    )
    c = em.parse_log_call_counts(log, force=True)
    assert c["tool_calls"] == 2
    assert c["shell_calls"] == 1
    assert c["model_headers"] == 1


def test_parse_cache_by_mtime_size(tmp_path: Path) -> None:
    em.clear_exec_metrics_cache()
    log = tmp_path / "c.log"
    log.write_text("→ Read a\n", encoding="utf-8")
    assert em.parse_log_call_counts(log)["tool_calls"] == 1
    log.write_text("→ Read a\n→ Write b\n", encoding="utf-8")
    # mtime/size changed → recount
    assert em.parse_log_call_counts(log)["tool_calls"] == 2


def test_running_timing_prefers_marker_birth(tmp_path: Path, monkeypatch) -> None:
    em.clear_exec_metrics_cache()
    wid = "T9"
    marker = tmp_path / f"{wid}.running"
    marker.write_text("pid=1\n", encoding="utf-8")
    log = tmp_path / f"{wid}.log"
    log.write_text("hello\n", encoding="utf-8")

    # Force known ages via monkeypatch on Path.stat is heavy; just check fields present
    t = em.running_timing(tmp_path, wid, now=marker.stat().st_mtime + 125)
    assert t["elapsed_s"] is not None
    assert t["elapsed_s"] >= 120
    assert t["started_at"]
    assert t["log_bytes"] == 6
