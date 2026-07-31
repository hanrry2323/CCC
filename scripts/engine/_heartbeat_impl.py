"""engine._heartbeat_impl — git stash + pids + heartbeat r/w

Extracted from ccc-engine.py (v1.1 glue slim).
Loaded via engine.heartbeat.attach().
"""
# flake8: noqa

def _git_stash_ws(ws: Path, tid: str, phase_num: int) -> bool:
    """cd ws && git stash push -m 'ccc-auto-stash: ...'。返回是否成功。"""
    try:
        result = subprocess.run(
            ["git", "stash", "push", "-m", f"ccc-auto-stash: {tid} phase {phase_num}"],
            cwd=str(ws),
            capture_output=True,
            timeout=30,
            text=True,
            env=_sanitized_env(),
        )
    except subprocess.TimeoutExpired:
        _log.warning("git stash timed out for %s", tid)
        return False
    except OSError as exc:
        _log.warning("git stash failed for %s: %s", tid, exc)
        return False
    if result.returncode != 0:
        _log.warning(
            "git stash non-zero exit for %s: rc=%d stderr=%s",
            tid,
            result.returncode,
            (result.stderr or "")[:200],
        )
        return False
    return True


def _get_running_pids(ws: Path) -> list[int]:
    """扫描 .ccc/pids/ 目录，返回没有对应 .done 标记的 PID 列表。"""
    pids_dir = ws / ".ccc" / "pids"
    if not pids_dir.is_dir():
        return []
    result: list[int] = []
    for f in sorted(pids_dir.iterdir()):
        if f.suffix != ".pid":
            continue
        subid = f.stem
        if (pids_dir / f"{subid}.done").exists():
            continue
        try:
            pid = int(f.read_text().strip())
            if pid > 0:
                result.append(pid)
        except (ValueError, OSError) as exc:
            _log.debug("[collect_pids] read %s: %s", f, exc)
    return result


def _read_heartbeat(ws: Path) -> dict | None:
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    if hb_file.exists():
        try:
            return json.loads(hb_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            _log.debug("[read_engine_heartbeat] %s: %s", hb_file, exc)
    return None


def _write_heartbeat(
    ws: Path,
    running_task_id: str | None,
    active_task_count: int = 0,
    running_pids: list[int] | None = None,
    memory_mb: dict | None = None,
    *,
    testing_count: int | None = None,
    global_active_count: int | None = None,
) -> None:
    ws = ws.resolve()
    # 保留上次 memory_mb，避免常规 heartbeat 覆盖掉内存采样
    if memory_mb is None:
        prev = _read_heartbeat(ws)
        if prev and isinstance(prev.get("memory_mb"), dict):
            memory_mb = prev["memory_mb"]
    used = global_active_count if global_active_count is not None else active_task_count
    if testing_count is None:
        try:
            testing_count = len(_get_store(ws).list_tasks("testing"))
        except Exception:
            testing_count = 0
    hb = {
        "workspace": str(ws),
        "running": running_task_id or None,
        "active_task_count": active_task_count,
        "running_pids": running_pids or [],
        "timestamp": now_iso(),
        "dev_slots": {"used": used, "max": MAX_CONCURRENT},
        "product_inflight": len(_product_inflight),
        "testing": testing_count,
        "pending_relaunch": len(_pending_relaunch),
    }
    if memory_mb is not None:
        hb["memory_mb"] = memory_mb
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    try:
        from _board_store import _atomic_write

        _atomic_write(hb_file, json.dumps(hb, ensure_ascii=False) + "\n")
    except OSError as e:
        _log.warning("engine heartbeat write failed for %s: %s", ws, e)


