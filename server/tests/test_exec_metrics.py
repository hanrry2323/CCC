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
    assert t["live"] is True


def test_running_timing_freezes_without_marker(tmp_path: Path) -> None:
    """进机审/已回写后无 .running：时长冻结在日志末次活动，不随 now 涨。"""
    em.clear_exec_metrics_cache()
    wid = "Tfreeze"
    log = tmp_path / f"{wid}.log"
    log.write_text("→ Read a\n", encoding="utf-8")
    far_future = log.stat().st_mtime + 50_000
    t = em.running_timing(tmp_path, wid, now=far_future)
    assert t["live"] is False
    assert t["elapsed_s"] is not None
    assert t["elapsed_s"] < 120
    assert em.parse_log_call_counts(log, force=True)["tool_calls"] == 1


def test_marker_pid_alive_only_true_for_live_pid(tmp_path: Path) -> None:
    """死 PID 残留标记不点亮 live；活 PID（本进程）点亮；audit 标记同规则。"""
    import os

    em.clear_exec_metrics_cache()
    wid = "Tmark"
    (tmp_path / f"{wid}.running").write_text(
        "engine_pid=99999999\npid=99999998\nchild_pid=99999997\n",
        encoding="utf-8",
    )
    assert em.marker_pid_alive(tmp_path, wid) is False

    (tmp_path / f"{wid}.running").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    assert em.marker_pid_alive(tmp_path, wid) is True

    # audit 标记：活 PID 也点亮；不存在的标记 → False
    (tmp_path / f"{wid}-audit.running").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    assert em.marker_pid_alive(tmp_path, wid) is True
    assert em.marker_pid_alive(tmp_path, "Tmissing") is False


def test_card_wants_runtime_columns() -> None:
    assert em.card_wants_runtime({"state": "已回写"}) is True
    assert em.card_wants_runtime({"state": "执行中"}) is True
    assert em.card_wants_runtime({"state": "待分派"}) is False
    assert em.card_wants_runtime({"state": "已回写", "board_column": "机审"}) is True
    assert em.card_wants_runtime({"state": "待分派", "board_column": "机审"}) is True


def test_aggregate_phases_and_sidecar_high_water(tmp_path: Path) -> None:
    """开发 log + 机审 audit.log 汇总；sidecar 高水位防覆盖归零。"""
    em.clear_exec_metrics_cache()
    wid = "cccX"
    (tmp_path / f"{wid}.log").write_text("→ Read a\n→ Write b\n", encoding="utf-8")
    (tmp_path / f"{wid}.audit.log").write_text("→ Read card\n", encoding="utf-8")
    c = em.parse_work_call_counts(tmp_path, wid, force=True)
    assert c["tool_calls"] == 3
    assert (tmp_path / f"{wid}.metrics.json").is_file()

    # 模拟旧逻辑：主 log 被机审覆盖成无 → 行
    (tmp_path / f"{wid}.log").write_text("[ccc.engine] start audit\n", encoding="utf-8")
    (tmp_path / f"{wid}.audit.log").unlink()
    c2 = em.parse_work_call_counts(tmp_path, wid, force=True)
    assert c2["tool_calls"] == 3  # sidecar 保住


def test_list_work_log_includes_run_archive(tmp_path: Path) -> None:
    wid = "T80"
    (tmp_path / f"{wid}.log").write_text("→ A\n", encoding="utf-8")
    (tmp_path / f"{wid}.run1.log").write_text("→ B\n→ C\n", encoding="utf-8")
    paths = {p.name for p in em.list_work_log_paths(tmp_path, wid)}
    assert f"{wid}.log" in paths
    assert f"{wid}.run1.log" in paths
    assert em.parse_work_call_counts(tmp_path, wid, force=True)["tool_calls"] == 3
