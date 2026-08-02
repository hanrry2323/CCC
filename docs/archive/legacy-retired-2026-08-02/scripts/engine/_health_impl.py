"""engine._health_impl — regen / degraded / audit schedule

Extracted from ccc-engine.py (v1.1 glue slim).
Loaded via engine.health.attach().
"""
# flake8: noqa

def _read_regen_count(ws: Path, tid: str) -> int:
    """读 phase_graph_unresolvable regen 计数器（来自 warnings.json）"""
    try:
        _wf = ws / ".ccc" / "warnings.json"
        if not _wf.exists():
            return 0
        import json as _json

        _data = _json.loads(_wf.read_text())
        if not isinstance(_data, list):
            return 0
        _regen = [w for w in _data if w.get("type") == "phase_graph_regen" and w.get("task_id") == tid]
        return len(_regen)
    except Exception:
        return 0


def _record_regen(ws: Path, tid: str) -> None:
    """记录一次 phase_graph_regen 到 warnings.json（原子写 + 文件锁）。"""
    try:
        import fcntl
        import tempfile

        _wf = ws / ".ccc" / "warnings.json"
        _wf.parent.mkdir(parents=True, exist_ok=True)
        # 锁文件与目标同目录，跨进程互斥
        lock_path = _wf.with_suffix(".json.lock")
        with open(lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                _existing: list = []
                if _wf.exists():
                    try:
                        raw = json.loads(_wf.read_text(encoding="utf-8"))
                        if isinstance(raw, list):
                            _existing = raw
                    except Exception:
                        _existing = []
                _regen_count = (
                    sum(
                        1
                        for w in _existing
                        if isinstance(w, dict) and w.get("type") == "phase_graph_regen" and w.get("task_id") == tid
                    )
                    + 1
                )
                _existing.append(
                    {
                        "type": "phase_graph_regen",
                        "task_id": tid,
                        "regen_count": _regen_count,
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                payload = json.dumps(_existing, ensure_ascii=False, indent=2)
                fd, tmp_name = tempfile.mkstemp(dir=str(_wf.parent), prefix=".warnings-", suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as tf:
                        tf.write(payload)
                        tf.flush()
                        os.fsync(tf.fileno())
                    os.replace(tmp_name, str(_wf))
                except Exception:
                    try:
                        os.unlink(tmp_name)
                    except OSError as exc:
                        _log.debug("[plan_write] tmp unlink %s: %s", tmp_name, exc)
                    raise
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        _log.warning("[regen] _record_regen %s failed: %s", tid, str(exc))


# ═══════════════════════════════════════════════════════════════
# v0.35: degraded mode — 引擎自我保护
# ═══════════════════════════════════════════════════════════════


def _recent_events(ws: Path, event_type: str, window_sec: int) -> list[dict]:
    """从 events.jsonl 读最近指定类型事件（滑动窗口）。

    大文件只扫尾部（默认 512KiB），避免每 6 tick 全量解析。
    """
    ev_file = ws / ".ccc" / "stats" / "events.jsonl"
    if not ev_file.exists():
        return []
    now = time.time()
    events = []
    max_bytes = int(os.environ.get("CCC_RECENT_EVENTS_BYTES", "524288"))
    try:
        size = ev_file.stat().st_size
        with ev_file.open("r", encoding="utf-8", errors="replace") as f:
            if size > max_bytes:
                f.seek(max(0, size - max_bytes))
                f.readline()  # 丢弃可能截断的首行
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == event_type:
                    ts = ev.get("t", 0)
                    if isinstance(ts, (int, float)) and ts > now - window_sec:
                        events.append(ev)
    except OSError as exc:
        _log.debug("[recent_events] read %s: %s", ev_file, exc)
    return events


def _check_degraded(ws: Path) -> None:
    """检查是否需要进入/退出 degraded 模式。

    degraded 模式下:
    - 停 backlog→planned intake（新 task 不进 pipeline）
    - 现有 in_progress/testing 继续跑完
    - 维护任务照跑（audit, stale check, cleanup）

    v0.36: upstream 不可用时同步开熔断，暂停 abnormal 自动重试。
    """
    global _degraded_mode, _degraded_since, _breaker_open, _breaker_since

    # v0.36: upstream 熔断
    # CCC Relay 2026-07-25:fail-open — relay 不可达不 block,只警告;任务走直连
    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if not _is_upstream_healthy():
        if not _breaker_open:
            _breaker_open = True
            _breaker_since = time.time()
            engine_log(
                "[breaker] upstream(relay) 不可用 → 开熔断并切 fail-open 直连,"
                " 任务继续跑不 block(2026-07-25 fail-open 共识)"
            )
            _ccc_notify("CCC", "engine upstream 不可用,已切 fail-open 直连")
    elif _breaker_open:
        elapsed = time.time() - _breaker_since
        if elapsed >= recovery:
            _breaker_open = False
            _breaker_since = 0.0
            engine_log(f"[breaker] relay 已恢复（熔断 {elapsed:.0f}s）→ 关熔断,回切")

    q_count = len(_recent_events(ws, "quarantine", 1800))
    f_count = len(_recent_events(ws, "product_fail", 1800))
    _any_success = len(_recent_events(ws, "product_done", 1800)) + len(_recent_events(ws, "auto_fixed", 1800))

    should_degrade = (
        q_count > _DEGRADED_QUARANTINE_THRESHOLD
        or f_count > _DEGRADED_FAIL_THRESHOLD
        or (q_count > 0 and _any_success == 0)
    )

    if should_degrade and not _degraded_mode:
        _degraded_mode = True
        _degraded_since = time.time()
        engine_log(
            f"[degraded] 30min 异常过高 (q={q_count}, f={f_count}, ok={_any_success}), 进入 degraded 模式 — 暂停 intake"
        )
        _ccc_notify("CCC", "engine 进入 degraded 模式（异常率过高，暂停 intake）")

    if _degraded_mode and not should_degrade:
        elapsed = time.time() - (_degraded_since or time.time())
        if elapsed > _DEGRADED_RECOVERY_SECONDS:
            _degraded_mode = False
            _degraded_since = None
            engine_log(f"[degraded] 异常率已恢复 (q={q_count}, f={f_count}), 退出 degraded 模式")
            _ccc_notify("CCC", "engine 退出 degraded 模式（指标恢复正常）")


# --- extracted 1224-1363; see engine.*.attach() ---

# --- extracted 1365-1701; see engine.*.attach() ---

# --- extracted 1703-2336; see engine.*.attach() ---

# --- extracted 2338-2795; see engine.*.attach() ---
def _audit_should_run(workspace: str, interval_hours: int = 2) -> bool:
    from datetime import datetime as _dt

    ws_slug = Path(workspace).name if workspace else "CCC"
    last_run_file = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
    if not last_run_file.exists():
        old_file = Path.home() / ".ccc" / "audit-last-run.json"
        if old_file.exists():
            return _audit_check_old(old_file, interval_hours)
        return True
    try:
        data = json.loads(last_run_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _audit_check_old(old_file, interval_hours: int = 2) -> bool:
    from datetime import datetime as _dt

    try:
        data = json.loads(old_file.read_text())
        last = _dt.fromisoformat(data["last_run"].replace("Z", "+00:00"))
        now = _dt.now(timezone.utc)
        hours = (now - last).total_seconds() / 3600
        return hours >= interval_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


