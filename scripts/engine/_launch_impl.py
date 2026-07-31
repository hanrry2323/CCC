"""engine._launch_impl — parallel launch / phase helpers

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.launch.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _phase_market_subid(tid: str, phase_num: int) -> str:
    """Per-phase marker subid，避免并行 phase 写在同 task_id.{done,pid,exitcode}。

    用「task_id__p{N}」双下划线，与 ccc-board 的「task_id-p{N}」区分。
    """
    return f"{tid}__p{phase_num}"


def _group_parallel_phases(phases: list[dict], executable: set[int]) -> list[list[int]]:
    """将 executable phases 分组：同组内 phase 之间无 depends_on 关系。

    Args:
        phases: 所有 phase dict（来自 _load_phases）
        executable: 当前可执行的 phase id 集合（来自 _resolve_phase_dependencies）

    Returns:
        list[list[int]]：每个内层 list 是一组可并行 phase（组内相位无依赖）。
        多组间必须先后顺序执行（前组全部完成才执行下一组）。

    算法：贪心。每个 phase 顺序遍历 — 能加入最后一个 group 当存在互不依赖，
    否则开新 group。
    """
    if not executable:
        return []
    by_id = {p.get("phase"): p for p in phases if p.get("phase") is not None}
    sorted_executable = sorted(executable)
    groups: list[list[int]] = []
    for pid in sorted_executable:
        phase_deps = set(by_id.get(pid, {}).get("depends_on") or [])
        placed = False
        # 尝试放入最后一个 group
        if groups:
            last_group = groups[-1]
            last_group_ids = set(last_group)
            # 若本 phase 与组内所有 phase 不互依赖（last_group_ids ∩ phase_deps == ∅）
            # 且组内其他 phase 也不依赖本 phase（避免环）
            conflicts = last_group_ids & phase_deps
            reverse_deps_conflict = any(pid in set(by_id.get(g, {}).get("depends_on") or []) for g in last_group)
            if not conflicts and not reverse_deps_conflict:
                last_group.append(pid)
                placed = True
        if not placed:
            groups.append([pid])
    return groups


def _top_level_roots(paths: list[str]) -> set[str]:
    """Distinct top-level path prefixes (skip .ccc hygiene)."""
    roots: set[str] = set()
    for raw in paths:
        s = str(raw or "").strip().lstrip("./")
        if not s or s.startswith(".ccc"):
            continue
        part = Path(s).parts[0] if Path(s).parts else ""
        if part:
            roots.add(part)
    return roots


def _force_serial_multi_root(
    phases: list[dict],
    executable: set[int],
    *,
    ws: Path | None = None,
    tid: str = "",
) -> bool:
    """Cross-directory fan-out is unstable under parallel OpenCode writes.

    Force serial when executable scopes (or acceptance paths) span ≥2 top-level
    roots — e.g. src/ + dashboard/ + tests/ (stress-2 class).
    """
    by_id = {p.get("phase"): p for p in phases if p.get("phase") is not None}
    scopes: list[str] = []
    for pid in executable:
        sc = by_id.get(pid, {}).get("scope") or []
        if isinstance(sc, list):
            scopes.extend(str(x) for x in sc if x)
        elif sc:
            scopes.append(str(sc))
    roots = _top_level_roots(scopes)
    if len(roots) >= 2:
        return True
    if ws is not None and tid:
        try:
            from _acceptance_gate import (
                _bullets_and_cmds,
                _paths_from_bullets,
                load_acceptance_text,
            )

            sec = load_acceptance_text(Path(ws), tid)
            if sec.strip():
                bullets, _cmds = _bullets_and_cmds(sec)
                acc_roots = _top_level_roots(_paths_from_bullets(bullets))
                if len(acc_roots) >= 2:
                    return True
        except Exception as exc:
            _log.debug("[scope_check] accept probe %s: %s", tid, str(exc))
    return False


def _phase_to_pgroup(p: int) -> str:
    """OpenCode pool / marker 用的 phase id（与 ccc-board 一致：task_id-pN）。"""
    # 注：当前 _try_launch_planned 调 dev_role_launch，里头 phase_id=task_id-pN。
    # 本 dispatcher 用 pgroup = task_id__pN 双下划线以隔离 task-level 标记。
    return f"p{p}"


def _build_phase_prompt(task_id: str, phase_num: int, plan_content: str, *, workspace: Path) -> str:
    """构造单 phase 的 prompt（委托 board.prompt，显式传 workspace）。"""
    from board.prompt import build_dev_phase_prompt

    scope: list[str] = []
    pytest_fail = ""
    skill_hints = ""
    try:
        for p in _load_phases(task_id):
            if int(p.get("phase", -1)) == int(phase_num):
                sc = p.get("scope") or []
                if isinstance(sc, list):
                    scope = [str(x) for x in sc if x]
                # v0.42.1: 空 scope 从 plan 回填，避免 OpenCode「未提供 scope」盲跑
                if not scope and plan_content:
                    try:
                        from _plan_adopt import backfill_scopes

                        filled = backfill_scopes([dict(p)], plan_content)
                        scope = list(filled[0].get("scope") or [])
                    except Exception as exc:
                        _log.debug("[plan_adopt] backfill_scopes %s: %s", task_id, str(exc))
                break
    except Exception as exc:
        _log.debug("[plan_adopt] scope resolve: %s", str(exc))
    try:
        pf = workspace / ".ccc" / "pids" / f"{task_id}.pytest_fail.md"
        if pf.is_file():
            pytest_fail = pf.read_text(encoding="utf-8", errors="replace")[:4000]
    except Exception as exc:
        _log.debug("[build_dev_prompt] pytest_fail read %s: %s", task_id, str(exc))
    try:
        from board.store_ops import list_tasks as _lt
        from _skills_catalog import format_skill_hints_block

        tid = str(task_id)
        for col in ("in_progress", "planned", "testing", "backlog"):
            task = next((t for t in _lt(col) if t.get("id") == tid), None)
            if not task:
                continue
            hints = task.get("hints") if isinstance(task.get("hints"), dict) else {}
            skills = hints.get("skills") if isinstance(hints.get("skills"), list) else []
            note = hints.get("note") if isinstance(hints.get("note"), str) else ""
            skill_hints = format_skill_hints_block(skills, note)
            break
    except Exception as exc:
        _log.debug("[build_dev_prompt] skill hints: %s", str(exc))
    return build_dev_phase_prompt(
        task_id,
        phase_num,
        plan_content,
        workspace=workspace,
        scope=scope,
        pytest_failure=pytest_fail,
        skill_hints=skill_hints,
    )


def _launch_parallel_phase(
    ws: Path,
    task_id: str,
    phase_num: int,
    plan_content: str,
    timeout_s: int,
    label: str,
) -> dict | None:
    """启单个 phase 的 opencode-runner.sh 后台进程，用 per-phase 命名空间隔离。

    Returns:
        {"subid": str, "pid": int, "proc": Popen} 或 None（失败）。
    """
    import subprocess as _sp

    subid = _phase_market_subid(task_id, phase_num)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = Path.home() / ".ccc" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"{subid}.prompt.md"
    prompt_file.write_text(
        _build_phase_prompt(task_id, phase_num, plan_content, workspace=ws),
        encoding="utf-8",
    )
    try:
        os.chmod(prompt_file, 0o600)
    except OSError as exc:
        _log.debug("[dev_launch] chmod %s: %s", prompt_file, exc)
    try:
        # 用 phase_id = subid 命名 opencode-runner.sh 的输出 marker
        # opencode-runner.sh 内部会写 ${PID_DIR}/${TASK_ID}.{done,exitcode}
        # 这里 TASK_ID 用 subid，故 marker 也隔离。
        tkey = _task_key(ws, task_id)
        if not _try_acquire_opencode_slot(tkey):
            engine_log(f"[engine] 全局 opencode 已达上限 ({_GLOBAL_OPENCODE_COUNT}/{_GLOBAL_OPENCODE_MAX})，等待")
            return None
        try:
            try:
                from _workspace_isolation import capture_isolation_baseline

                capture_isolation_baseline(ws, task_id)
            except Exception as _iso_exc:
                engine_log(f"[isolation] baseline {task_id}: {_iso_exc}")
            proc = _sp.Popen(
                [
                    "bash",
                    str(_script_dir / "opencode-runner.sh"),
                    subid,
                    str(_script_dir.parent),  # CCC_HOME
                    str(ws),  # ROOT_DIR
                    "--phase",
                    f"{task_id}-p{phase_num}",  # 与 ccc-board 一致 phase_id 命名
                    "--prompt",
                    str(prompt_file),
                    "--timeout",
                    str(timeout_s),
                    "--cwd",
                    str(ws),
                ],
                cwd=ws,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_sanitized_env(),
            )
        except Exception:
            _release_opencode_slot(tkey, 1)
            raise
        pids_dir.joinpath(f"{subid}.pid").write_text(str(proc.pid))
        engine_log(
            f"[{label}] {task_id}-p{phase_num} launched PID={proc.pid} "
            f"(subid={subid}, retry 0/{cfg.DEFAULT_RETRY}, timeout {timeout_s}s)"
        )
        return {"subid": subid, "pid": proc.pid, "proc": proc}
    except Exception as exc:
        engine_log(f"[{label}] {task_id}-p{phase_num} launch failed: {exc}")
        return None


def _check_parallel_phase_done(ws: Path, subid: str) -> dict:
    """检查单个并行 phase 完成状态。

    Returns:
        {"status": "running" | "success" | "failed", "exit_code": int}
    """
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{subid}.done"
    if not done_file.exists():
        # 检查 PID 是否存活
        pid_file = pids_dir / f"{subid}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running", "exit_code": -1}
            except (ValueError, OSError, ProcessLookupError) as exc:
                _log.debug("[check_phase_done] pid probe %s: %s", subid, exc)
        return {"status": "running", "exit_code": -1}
    exit_file = pids_dir / f"{subid}.exitcode"
    try:
        exit_code = int(exit_file.read_text().strip()) if exit_file.exists() else 1
    except ValueError:
        exit_code = 1
    return {
        "status": "success" if exit_code == 0 else "failed",
        "exit_code": exit_code,
    }


def _launch_parallel_group(
    ws: Path,
    task_id: str,
    phase_nums: list[int],
    plan_content: str,
    timeout_s: int,
    label: str,
) -> tuple[bool, dict[int, dict]]:
    """并行启一组 phase（max_workers 个线程）。返回 (success, phase_meta)。

    Args:
        phase_nums: 这组 phase 编号列表
        plan_content: 完整 plan 文本（每个 phase 都用同一份 prompt）
        timeout_s: 超时秒数

    Returns:
        (True, {phase_num: {"subid": ..., "pid": ...}}) 全部成功
        (False, {...}) 部分/全部失败
    """
    if not phase_nums:
        return True, {}

    max_w = min(PHASE_PARALLEL_MAX_WORKERS, len(phase_nums))
    engine_log(
        f"[parallel] [{label}] {task_id} 并行启动 "
        f"phase {' + '.join(f'phase-{n}' for n in phase_nums)} "
        f"(max_workers={max_w})"
    )
    phase_meta: dict[int, dict] = {}
    try:
        with ThreadPoolExecutor(max_workers=max_w) as ex:
            futures = {
                ex.submit(
                    _launch_parallel_phase,
                    ws,
                    task_id,
                    pn,
                    plan_content,
                    timeout_s,
                    label,
                ): pn
                for pn in phase_nums
            }
            for fut, pn in futures.items():
                try:
                    res = fut.result(timeout=15)
                except Exception as exc:
                    engine_log(f"[{label}] {task_id}-p{pn} parallel submit exception: {exc}")
                    res = None
                if res is None:
                    engine_log(f"[parallel][warn] {task_id}-p{pn} 启动失败，此 phase 将被跳过（其他 phase 继续）")
                    continue
                phase_meta[pn] = res
        success = len(phase_meta) > 0
        if success:
            engine_log(
                f"[parallel] [{label}] {task_id} 并行 phase 已启动: "
                f"{[(pn, phase_meta[pn]['pid']) for pn in sorted(phase_meta)]}"
            )
        return success, phase_meta
    except Exception as exc:
        engine_log(f"[parallel][warn] {task_id} ThreadPoolExecutor 异常: {exc}，fallback 串行模式")
        _set_parallel_disabled(True)
        return False, {}


def _salvage_phases_done_planned(
    ws: Path,
    tid: str,
    store,
    *,
    label: str,
) -> str | None:
    """When all phases are done but card stuck in planned, advance to testing.

    Prevents hot-loop: prepare fails (no pending phase) every tick while column stays planned.
    """
    col, task = store.find_task(tid)
    if col != "planned" or not task:
        return None
    try:
        from _role_tool import _read_phases_json

        phases = _read_phases_json(Path(ws), tid) or []
    except Exception:
        phases = []
    if not phases:
        return None
    statuses = {str(p.get("status") or "?") for p in phases}
    if not statuses or statuses - {"done"}:
        # any non-done → not this salvage
        return None
    if store.move_task(tid, "planned", "testing"):
        store.patch_task(
            tid,
            {
                "status": "testing",
                "note": (
                    str(task.get("note") or "")
                    + "\n[engine] salvage_phases_done→testing"
                ).strip(),
            },
        )
        engine_log(
            f"[{label}] {tid} salvage: phases all done + planned → testing（破空转）"
        )
        return "testing"
    return None


def _try_launch_planned(ws: Path, active_tasks: dict[str, dict]) -> bool:
    """从 planned 启动一个 task。返回 True 表示已启动。

    2026-07-29 Wave C：实现迁入 engine.dispatch.try_launch_planned。
    """
    from engine.dispatch import try_launch_planned

    return try_launch_planned(ws, active_tasks)


def _lookup_phase_timeout(tid: str, phases: list[dict]) -> int:
    """查 phases 里 phase 1 的 timeout，单位秒；找不到走 cfg.default_timeout。

    engine-phase-retry-config: 缺省 600 → cfg.default_timeout（1800），
    与 ccc-board._load_timeout 默认值保持一致。
    """
    default_to = cfg.default_timeout
    for p in phases:
        if p.get("phase") == 1:
            try:
                return int(p.get("timeout", default_to))
            except (TypeError, ValueError):
                return default_to
    return default_to


def _store_atomic_write_phases(path: Path, payload: str) -> None:
    """原子写 phases.json：写 temp + fsync + os.replace。容错 fallback 直写。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as tf:
            tf.write(payload)
            tf.flush()
            os.fsync(tf.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            _log.error("[phases_write] fallback write %s: %s", path, exc)


def _try_launch_planned_parallel(
    ws: Path,
    task_id: str,
    groups: list[list[int]],
    plan_content: str,
    timeout_s: int,
) -> bool:
    """启并行 task 的首个 group，剩余 group 等当前 group 全部完成后再启。

    Args:
        ws: workspace 路径
        task_id: task 名
        groups: 分组后的并行 phase 列表（每组内无相互依赖）
        plan_content: 完整 plan 文本
        timeout_s: 单 phase 超时秒数

    Returns:
        True 至少启了一个 phase；False 全部失败。
    """
    global _parallel_phases

    label = _ws_label(ws)
    key = _task_key(ws, task_id)
    first_group = groups[0]
    engine_log(
        f"[parallel] [{label}] {task_id} 并行调度: {len(groups)} 个 group "
        f"(size={[len(g) for g in groups]}, max_workers={min(PHASE_PARALLEL_MAX_WORKERS, len(first_group))})"
    )
    success, phase_meta = _launch_parallel_group(ws, task_id, first_group, plan_content, timeout_s, label)
    if not success:
        engine_log(f"[parallel][error] [{label}] {task_id} 全部 phase 启动失败")
        return False
    _parallel_phases[key] = {
        "groups": groups,
        "current_group": first_group,
        "phase_meta": phase_meta,
        "any_group_fail": False,
        "ws_path": str(ws),
    }
    engine_log(f"[parallel] [{label}] {task_id} 当前 group={first_group} 启动 {len(phase_meta)} phase OK")
    return True


def _on_parallel_group_complete(ws: Path, task_id: str, phase_nums: list[int]) -> str:
    """检一组并行 phase 是否都写完 marker。

    Returns:
        "still_running" — 仍有 phase 没标 done
        "group_done_ok" — 全部 phase 成功
        "group_done_fail" — 至少 1 条失败
    """
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    exitcodes: dict[int, int] = {}
    for pid in phase_nums:
        subid = _phase_market_subid(task_id, pid)
        done_path = pids_dir / f"{subid}.done"
        exit_path = pids_dir / f"{subid}.exitcode"
        if not done_path.exists():
            return "still_running"
        try:
            ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
        except (ValueError, OSError):
            ec = 1
        exitcodes[pid] = ec
    label = _ws_label(ws)
    any_fail = any(ec != 0 for ec in exitcodes.values())
    engine_log(
        f"[parallel][group-done] [{label}] {task_id} group {phase_nums} → "
        f"{'fail' if any_fail else 'ok'} (exitcodes={exitcodes})"
    )
    # 写回 phases.json：pending → done/failed
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if phases_file.exists():
        try:
            raw = phases_file.read_text(encoding="utf-8")
            new_lines: list[str] = []
            changed = False
            for line in raw.splitlines():
                s = line.strip()
                if not s:
                    new_lines.append(line)
                    continue
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                if not isinstance(obj, dict) or "phase" not in obj:
                    new_lines.append(line)
                    continue
                pid = obj.get("phase")
                if pid in exitcodes:
                    new_status = "done" if exitcodes[pid] == 0 else "failed"
                    if obj.get("status") != new_status:
                        obj["status"] = new_status
                        changed = True
                new_lines.append(json.dumps(obj, ensure_ascii=False))
            if changed:
                _store_atomic_write_phases(phases_file, "\n".join(new_lines) + "\n")
        except OSError as exc:
            engine_log(f"[parallel][status] 写 phases.json 失败: {exc}")
    return "group_done_fail" if any_fail else "group_done_ok"


def _check_parallel_task_complete(ws: Path, task_id: str) -> str:
    """Engine tick 调用：推进并行 task 状态。

    Returns:
        "still_running" — 当前 group 未完 / 等待下一 group
        "task_complete_ok" — 全部 group 完成且全成功
        "task_complete_fail" — 有 group 失败
    """
    global _parallel_phases

    ws = ws.resolve()
    key = _task_key(ws, task_id)
    state = _parallel_phases.get(key)
    if not state:
        return "still_running"

    current_group = state.get("current_group") or []
    if not current_group:
        return "still_running"

    group_state = _on_parallel_group_complete(ws, task_id, current_group)
    if group_state == "still_running":
        return "still_running"
    # v0.30.0: 本组 phase 已结束，释放本组 opencode 槽位（F-CON-01）
    n_launched = len(state.get("phase_meta") or {})
    if n_launched:
        _release_opencode_slot(_task_key(ws, task_id), n_launched)
    if group_state == "group_done_fail":
        state["any_group_fail"] = True

    # 推进到下一 group
    groups = state.get("groups") or [current_group]
    current_group_idx = groups.index(current_group) if current_group in groups else -1
    next_group = None
    for i in range(current_group_idx + 1, len(groups)):
        if groups[i]:
            next_group = groups[i]
            break
    if next_group and len(next_group) >= 2:
        # 启动下一 group
        plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
        if plan_file.exists():
            plan_content = plan_file.read_text(encoding="utf-8")
            # 拿当前 timeout
            timeout_s = 600
            phases = _load_phases(task_id, ws)
            if phases:
                timeout_s = _lookup_phase_timeout(task_id, phases)
            label = _ws_label(ws)
            ok, meta = _launch_parallel_group(
                ws,
                task_id,
                next_group,
                plan_content,
                timeout_s,
                label,
            )
            if ok:
                state["current_group"] = next_group
                state["phase_meta"] = meta
                engine_log(f"[parallel][next-group] {task_id} 下一 group {next_group} 启动")
                return "still_running"
            engine_log(f"[parallel][warn] {task_id} 下一 group 启动失败，标 group fail")
            state["any_group_fail"] = True

    # 全部 group 完成（或后续 group 启不动）
    any_fail = bool(state.get("any_group_fail"))
    _parallel_phases.pop(key, None)
    pids_dir = ws / ".ccc" / "pids"
    try:
        (pids_dir / f"{task_id}.done").write_text("ok")
        (pids_dir / f"{task_id}.exitcode").write_text("1" if any_fail else "0")
    except OSError as exc:
        engine_log(f"[parallel][marker-write] {task_id} 写完成 marker 失败: {exc}")
    label = _ws_label(ws)
    engine_log(f"[parallel][task-done] [{label}] {task_id} 全部 group 完成 (any_fail={any_fail})")
    return "task_complete_fail" if any_fail else "task_complete_ok"


def _parallel_task_marker_to_result(ws: Path, task_id: str) -> dict:
    """类似 dev_role_check_complete: 把并行 task 的 done/exitcode 映射成 status dict。"""
    ws = ws.resolve()
    pids_dir = ws / ".ccc" / "pids"
    done_path = pids_dir / f"{task_id}.done"
    exit_path = pids_dir / f"{task_id}.exitcode"
    if not done_path.exists():
        return {"status": "running", "retry": 0}
    try:
        ec = int(exit_path.read_text().strip()) if exit_path.exists() else 1
    except (ValueError, OSError):
        ec = 1
    if ec == 0:
        return {"status": "success", "retry": 0}
    return {"status": "failed", "retry": 0}


def _reset_parallel_disabled_after_tick() -> None:
    """tick 边界 reset PHASE_PARALLEL_DISABLED（fallback 只对当次 tick 生效）。"""
    global PHASE_PARALLEL_DISABLED
    PHASE_PARALLEL_DISABLED = False

