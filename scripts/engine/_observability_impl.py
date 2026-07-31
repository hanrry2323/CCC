"""engine._observability_impl — stats jsonl + opencode_done + host sample

Extracted from ccc-engine.py (v1.1 glue slim).
Loaded via engine.observability.attach().
"""
# flake8: noqa

_STATS_DIR: Path | None = None


def _stats_dir(ws: Path) -> Path:
    global _STATS_DIR
    if _STATS_DIR is None:
        _STATS_DIR = ws / ".ccc" / "stats"
        _STATS_DIR.mkdir(parents=True, exist_ok=True)
    return _STATS_DIR


def _log_stats(ws: Path, event: str, tid: str, **extra) -> None:
    """写一条结构化事件到 .ccc/stats/events.jsonl。

    修复 stability-audit-2026-07-24 类别②：事件写失败不再完全静默，
    至少 log.warning 让 ops 看到（仍不阻塞业务）。
    """
    sf = _stats_dir(ws) / "events.jsonl"
    record = {
        "t": now_iso(),
        "event": event,
        "task": tid,
        "workspace": ws.name,
    }
    record.update(extra)
    try:
        from _jsonl_rotate import append_jsonl

        append_jsonl(sf, record)
    except ImportError:
        try:
            with sf.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            _log.warning(
                "[stats] events.jsonl plain-append failed for %s event=%s: %s",
                sf,
                event,
                exc,
            )
    except OSError as exc:
        _log.warning(
            "[stats] events.jsonl append_jsonl failed for %s event=%s: %s",
            sf, event, exc,
        )
    # 跨仓耗时 SSOT（小卡分钟数统计用）
    if event in ("opencode_start", "opencode_done"):
        try:
            gdir = Path.home() / ".ccc" / "stats"
            gdir.mkdir(parents=True, exist_ok=True)
            from _jsonl_rotate import append_jsonl as _aj

            _aj(gdir / "opencode-timings.jsonl", record)
        except Exception:
            try:
                with (Path.home() / ".ccc" / "stats" / "opencode-timings.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as exc:
                _log.warning("[stats] opencode-timings.jsonl write failed: %s", exc)


def _maybe_sample_host_resources(active_tasks: dict[str, dict]) -> None:
    """~60s Mac2017 CPU/内存曲线 → ~/.ccc/stats/host-resources.jsonl。"""
    try:
        from _host_resources import sample_and_append
        from engine.slots import global_opencode_count

        sample_and_append(
            active_dev=len(active_tasks),
            max_concurrent=MAX_CONCURRENT,
            opencode_slots=int(global_opencode_count()),
            interval_sec=60.0,
        )
    except Exception as exc:
        _log.warning("[heartbeat] write failed: %s", exc)


def _wall_seconds_from_started(started_at: str | None) -> float | None:
    """Parse active_tasks started_at → wall seconds; None if unparseable."""
    if not started_at:
        return None
    try:
        from datetime import datetime, timezone

        s = str(started_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds()), 2)
    except (TypeError, ValueError, OSError):
        return None


def _log_opencode_done(
    ws: Path,
    tid: str,
    *,
    status: str,
    complexity: str = "medium",
    started_at: str | None = None,
    result: dict | None = None,
) -> None:
    """埋点：小卡/阶段 OpenCode 墙钟 + result.duration_s。"""
    duration_s = None
    exit_code = None
    killed = None
    # result.json 优先（opencode-exec 写出）；容忍污染
    result_path = Path(ws) / ".ccc" / "reports" / f"{tid}.result.json"
    if result_path.is_file():
        try:
            from _result_json import parse_result_file

            raw_txt = result_path.read_text(encoding="utf-8", errors="replace")
            parsed, dirty = parse_result_file(result_path, raw=raw_txt)
            if dirty:
                _log_stats(ws, "dirty_result", tid, keys=list(parsed)[:20])
            if isinstance(parsed, dict) and parsed:
                if "duration_s" in parsed:
                    duration_s = float(parsed["duration_s"])
                if "exit_code" in parsed:
                    exit_code = parsed["exit_code"]
                if "killed" in parsed:
                    killed = bool(parsed["killed"])
        except (OSError, ValueError, TypeError) as exc:
            engine_log("[task_result] result.json parse failed for %s: %s", tid, str(exc))
    wall_s = _wall_seconds_from_started(started_at)
    # result dict 兜底（salvage / check_complete 可能未落盘 result.json）
    if duration_s is None and isinstance(result, dict):
        try:
            if result.get("duration_s") is not None:
                duration_s = float(result["duration_s"])
        except (TypeError, ValueError) as exc:
            engine_log("[task_result] duration_s fallback parse failed for %s: %s", tid, str(exc))
    # P2/KPI: 缺 duration_s 时用墙钟回填；双空则 0.0（保 fill_rate 可统计）
    duration_from_wall = False
    if duration_s is None and wall_s is not None:
        duration_s = wall_s
        duration_from_wall = True
    if duration_s is None:
        duration_s = 0.0
        duration_from_wall = True
    _log_stats(
        ws,
        "opencode_done",
        tid,
        status=status,
        complexity=complexity,
        duration_s=duration_s,
        wall_s=wall_s,
        duration_min=round(duration_s / 60.0, 3) if duration_s is not None else None,
        wall_min=round(wall_s / 60.0, 3) if wall_s is not None else None,
        exit_code=exit_code,
        killed=killed,
        result_status=(result or {}).get("status"),
        duration_from_wall=duration_from_wall,
    )


# KPI R4: short-path fail budget — ban 1Hz planned↔in_progress storm
_SHORT_PATH_FAIL_MAX = 3
_ACCEPTANCE_FAIL_MAX = 2


