"""engine._recover_retry_impl — retry abnormal + enqueue + stale

Extracted from ccc-engine.py (min-pipeline refactor 2026-07-31).
Loaded into ccc_engine host namespace via engine.recover_retry.attach().
"""
# flake8: noqa
# This file is exec'd into ccc_engine.__dict__; do not import symbols directly.

def _classify_failure(reason: str, tid: str, phase_note: str = "") -> str:
    """将失败原因分为 transient / permanent。

    不匹配任何关键词时按 transient（宁可错重试也不漏）。

    2026-07-24 方案 P1-3：委托给 failure_router.classify_failure（统一入口），
    ccc-engine.py 仍保留 _PERMANENT_KEYWORDS / _TRANSIENT_KEYWORDS 常量给
    line 2931 关键词扫描复用。
    """
    from engine.failure_router import classify_failure as _impl

    blob = f"{reason} {phase_note} {tid}"
    return _impl(blob)


def _retry_cooldown_seconds(retry_count: int) -> int:
    """第 N 次重试冷却 = base × factor^N，上限 max。"""
    base = getattr(cfg, "retry_base_interval", _RETRY_BASE_INTERVAL)
    factor = getattr(cfg, "retry_backoff_factor", _RETRY_BACKOFF_FACTOR)
    max_iv = getattr(cfg, "retry_max_interval", _RETRY_MAX_INTERVAL)
    cool = base * (factor ** max(0, int(retry_count)))
    return min(int(cool), int(max_iv))


def _workspace_project_id(ws: Path) -> str:
    """Best-effort project_id for repair-queue (registry name or folder).

    Align with Desktop/Hub：qx-observer 仓 → qxo（否则 L3b claim 按 qxo 取空）。
    """
    try:
        from _workspace_registry import lookup_entry

        ent = lookup_entry(str(ws))
        if isinstance(ent, dict):
            name = str(ent.get("name") or ent.get("id") or "").strip()
            if name:
                if name == "qx-observer":
                    return "qxo"
                return name
    except Exception as exc:  # noqa: BLE001
        engine_log(f"[repair-queue] workspace_project_id lookup failed: {exc}")
    folder = Path(ws).name
    if folder == "qx-observer":
        return "qxo"
    return folder


def _enqueue_post_exhaust_optimize(
    ws: Path,
    tid: str,
    *,
    reason: str,
    task: dict | None = None,
) -> None:
    """耗尽后：写 transfer_lessons；L3b repair-queue 仅史径/显式开关。

    最小可跑通（默认）：blocked 证据回 Desktop，不入 repair-queue 热路径。
    """
    try:
        from engine.min_pipeline import l3b_repair_queue_enabled
    except Exception:
        def l3b_repair_queue_enabled() -> bool:
            return False

    try:
        from _failure_buckets import classify_failure_bucket, is_exhaust_reason
    except Exception as exc:
        engine_log(f"[epic-optimize] import failed: {exc}")
        return
    if not is_exhaust_reason(reason):
        pass
    task = task or {}
    parent = str(task.get("parent_id") or "").strip() or tid
    bucket = classify_failure_bucket(reason)
    pid = _workspace_project_id(ws)
    hint = f"{tid}: {reason}"[:400]

    # Agent craft lesson (L1) — always train next epic draft
    try:
        from _failure_buckets import bucket_optimize_hints
        from chat_server.services import agent_mind as _am

        _am.append_transfer_lesson(
            Path(ws),
            epic_id=parent,
            bucket=bucket,
            title_snip=str((task or {}).get("title") or tid)[:80],
            hint=bucket_optimize_hints(bucket)[:240],
            bad_pattern=str(reason or "")[:160],
            good_fix=bucket_optimize_hints(bucket)[:160],
            source="post_exhaust",
        )
    except Exception as exc:
        engine_log(f"[{_ws_label(ws)}] transfer_lesson append failed: {exc}")

    if not l3b_repair_queue_enabled():
        engine_log(
            f"[{_ws_label(ws)}] min-pipeline: skip L3b repair-queue "
            f"project={pid} epic={parent} bucket={bucket} hint={hint[:80]}"
        )
        return

    try:
        from chat_server.services.repair_queue import enqueue_epic_optimize

        out = enqueue_epic_optimize(
            project_id=pid,
            epic_id=parent,
            hint=hint,
            buckets=bucket,
        )
        engine_log(
            f"[{_ws_label(ws)}] epic_optimize enqueue "
            f"project={pid} epic={parent} bucket={bucket} "
            f"deduped={out.get('deduped')} key={out.get('key')}"
        )
    except Exception as exc:
        engine_log(f"[{_ws_label(ws)}] epic_optimize enqueue failed: {exc}")

def _retry_abnormal_failures(ws: Path) -> None:
    """enabled 下有限回灌：仅业务仓 work 卡、瞬态、每卡 ≤2，走 reopen_task。

    禁止 orch/invent；permanent / fail_loop_exhausted 不重开。
    """
    from datetime import datetime as _dt
    import json as _json

    global _breaker_open, _breaker_since

    recovery = getattr(cfg, "breaker_recovery_seconds", _BREAKER_RECOVERY_SECONDS)
    if _breaker_open and time.time() - _breaker_since < recovery:
        engine_log(f"[{_ws_label(ws)}] 熔断中，跳过 abnormal 重试")
        return

    try:
        from _workspace_registry import is_orch_path

        if is_orch_path(ws):
            return
    except Exception:
        # registry 不可用时仍允许业务路径启发式
        if "CCC" in str(ws) and (ws / "scripts" / "ccc-engine.py").is_file():
            return

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    retry_counter_file = ws / ".ccc" / ".dev_auto_retry.json"
    retry_counts: dict[str, int] = {}
    if retry_counter_file.exists():
        try:
            retry_counts = _json.loads(retry_counter_file.read_text())
        except (_json.JSONDecodeError, OSError):
            retry_counts = {}
    MAX_AUTO_RETRY = 2
    _EXHAUSTED = (
        "reviewer_fail_loop_exhausted",
        "tester_fail_loop_exhausted",
        "fail_loop_exhausted",
        "重试耗尽",
        "次全部失败",
        "missing plan",
        "缺 plan",
        "缺 phases",
    )

    moved_tasks: list[str] = []

    for task in store.list_tasks("abnormal"):
        tid = task["id"]
        kind_card = str(task.get("card_kind") or "")
        if kind_card == "epic":
            continue
        # work 或有 parent 的子卡；裸 backlog 杂卡跳过
        if kind_card and kind_card not in ("work", "task"):
            if not task.get("parent_id"):
                continue

        reason = str(task.get("note") or task.get("abnormal_reason") or "")
        low = reason.lower()
        # 015: pure gate (epic/exhausted/permanent/max) before heavier work
        try:
            from engine.failure_router import should_auto_refeed

            _auto_n = int(retry_counts.get(tid, 0) or 0)
            _dec = should_auto_refeed(
                card_kind=kind_card or "work",
                reason=reason,
                auto_retried=_auto_n,
                max_auto_retry=MAX_AUTO_RETRY,
                has_pack_or_transient=True,  # pack check below may still skip
            )
            if not _dec.should and _dec.reason in (
                "epic",
                "exhausted_keyword",
                "permanent",
                f"max_retry_reached({_auto_n})",
            ):
                engine_log(
                    f"[{label}] skip auto-retry {tid}: should_auto_refeed={_dec.reason}"
                )
                if _dec.reason != "epic":
                    _enqueue_post_exhaust_optimize(ws, tid, reason=reason, task=task)
                continue
        except Exception as exc:
            engine_log(f"[{label}] {tid} should_auto_refeed probe: {exc}")

        if any(m.lower() in low for m in _EXHAUSTED):
            engine_log(f"[{label}] skip auto-retry {tid}: exhausted/permanent marker")
            _enqueue_post_exhaust_optimize(ws, tid, reason=reason, task=task)
            continue

        kind = _classify_failure(reason, tid, task.get("note") or "")
        if kind == "permanent":
            engine_log(f"[{label}] skip auto-retry {tid}: 不可恢复错误（permanent）")
            _enqueue_post_exhaust_optimize(ws, tid, reason=reason, task=task)
            continue

        # 须有 review_fail 包，或 reason 命中瞬态关键字（兼容旧 quarantine）
        try:
            from _failure_learning import (
                review_fail_path,
                write_review_fail_pack,
            )

            pack_p = review_fail_path(ws, tid)
            has_pack = pack_p.is_file()
        except Exception:
            has_pack = False
            write_review_fail_pack = None  # type: ignore
        transient_hit = any(kw.lower() in low for kw in _TRANSIENT_KEYWORDS)
        keyword_hit = any(kw in reason for kw in _ABNORMAL_RETRY_KEYWORDS)
        if not has_pack and not (transient_hit or keyword_hit):
            continue
        if not has_pack and write_review_fail_pack is not None:
            try:
                write_review_fail_pack(ws, tid, status="abnormal", extra=reason[:1500])
            except Exception as exc:
                engine_log(f"[{label}] {tid} seed review_fail: {exc}")

        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            minutes_since = (now - updated).total_seconds() / 60
        except (ValueError, TypeError):
            continue

        auto_retried = int(retry_counts.get(tid, 0) or 0)
        if auto_retried >= MAX_AUTO_RETRY:
            continue

        # v0.62.1: 前置校验 — 不通过不扣 retry budget
        try:
            from _role_tool import prepare_role_call

            ok, reason = prepare_role_call(tid, ws)
            if not ok:
                engine_log(
                    f"[{label}] {tid} prepare 校验失败 ({reason})，跳过，不扣 retry budget"
                )
                continue
        except Exception as exc:
            engine_log(f"[{label}] {tid} prepare_role_call error: {exc}")
            continue

        # 2026-07-24 方案 P1-1：retry budget 跨层统一闸（auto + review + hang）
        # 2026-07-25 修 P0-2:auto-refeed 改用 increment_retry_count(主动递增+抛异常),
        # 与 reviewer/hang 三路径一致;不依赖 caller 后续再 increment。
        from engine.failure_router import (
            MAX_TASK_RETRY_BUDGET,
            RetryBudgetExceeded,
            increment_retry_count,
        )

        try:
            _used = increment_retry_count(ws, tid, store)
            engine_log(
                f"[{label}] {tid} auto-refeed retry {_used}/{MAX_TASK_RETRY_BUDGET}"
            )
        except RetryBudgetExceeded:
            engine_log(
                f"[{label}] {tid} retry budget 耗尽，跳过 auto-refeed"
            )
            _enqueue_post_exhaust_optimize(ws, tid, reason=reason, task=task)
            continue
        needed_minutes = _retry_cooldown_seconds(auto_retried) / 60
        if minutes_since < needed_minutes:
            continue

        try:
            from _task_reopen import reopen_task

            note = f"auto-refeed #{auto_retried + 1}/{MAX_AUTO_RETRY}: {reason[:80]}"
            abn = ws / ".ccc/board/abnormal" / f"{tid}.jsonl"
            if abn.is_file():
                try:
                    task_json = _json.loads(abn.read_text(encoding="utf-8"))
                    if isinstance(task_json, dict):
                        task_json["note"] = note
                        task_json["updated_at"] = now_iso()
                        from _board_store import _atomic_write

                        _atomic_write(
                            abn,
                            _json.dumps(task_json, ensure_ascii=False) + "\n",
                        )
                except Exception as exc:
                    engine_log(
                        "[%s] %s auto-refeed task json update failed: %s",
                        label, tid, str(exc),
                    )
            rr = reopen_task(ws, tid, to_col="planned", wake=True)
            if not rr.get("ok"):
                raise RuntimeError(rr.get("error") or "reopen failed")
            retry_counts[tid] = auto_retried + 1
            engine_log(
                f"[{label}] auto-refeed #{auto_retried + 1}/{MAX_AUTO_RETRY}: "
                f"{tid} (冷却 {minutes_since:.0f}/{needed_minutes:.0f}min, "
                f"{kind}) → planned"
            )
            moved_tasks.append(tid)
        except Exception as e:
            _log.warning("auto-refeed failed for %s: %s", tid, e)

    try:
        from _board_store import _atomic_write

        _atomic_write(
            retry_counter_file,
            _json.dumps(retry_counts, ensure_ascii=False) + "\n",
        )
    except OSError as exc:
        _log.warning(
            "[%s] retry counter file write failed for %s: %s",
            label, retry_counter_file, exc,
        )

    if moved_tasks:
        engine_log(f"[{label}] abnormal refeed moved={moved_tasks}")


# 兼容旧名（测试 / 外部引用）
_retry_abnormal_dev_failures = _retry_abnormal_failures


def _check_new_reviews(ws: Path) -> None:
    try:
        from _review_validator import scan_review_dir

        results = scan_review_dir(str(ws))
        label = _ws_label(ws)
        for r in results:
            if not r.get("valid"):
                fname = Path(r.get("file", "?")).name
                errs = "; ".join(r["errors"][:3])
                engine_log(f"[{label}] 🔴 报告格式错误 {fname}: {errs}")
    except ImportError as e:
        _log.warning("_review_validator unavailable, skipping review scan: %s", e)
    except Exception as exc:
        engine_log(f"review 校验异常: {exc}")


def _check_stale(ws: Path, active_tasks: dict[str, dict] | None = None) -> None:
    from datetime import datetime as _dt

    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    now = _dt.now(timezone.utc)
    for task in store.list_tasks("in_progress"):
        # v0.34 (P4): 优先 phase_last_advanced_ts（phase 级别停滞）
        updated_str = task.get("phase_last_advanced_ts", task.get("updated_at", task.get("created_at", "")))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > cfg.max_stale_hours:
                tid = task["id"]
                reason = f"engine: in_progress 滞留 {hours_stale:.1f}h (阈值 {cfg.max_stale_hours}h)"
                cur_phase = _current_running_phase(tid)
                _quarantine_with_notify(ws, tid, reason, store, phase=cur_phase, active_tasks=active_tasks)
                engine_log(f"[{label}] stale: {tid} in_progress 滞留 {hours_stale:.1f}h → abnormal")
        except (ValueError, TypeError) as e:
            _log.warning("stale task timestamp parse failed for %s: %s", task.get("id"), e)
    try:
        store.cleanup_events(max_days=30)
    except Exception as e:
        _log.warning("events TTL cleanup failed: %s", e, exc_info=True)

