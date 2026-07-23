"""engine.gates — testing/verified 列门禁（reviewer/tester/pytest/kb）。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from _config import Config, get_logger
from _executor import _sanitized_env
from board.phase import _current_running_phase, _load_phases
from board.roles import kb_role, reviewer_role, tester_role
from engine.workspace import (
    _activate_workspace,
    _ensure_task_in_testing,
    _find_task_column,
    _get_store,
    _ws_label,
)

_log = get_logger("engine")
cfg = Config()

_PYTEST_FAIL_MAX = 3  # F-FLOW-01: pytest 连续失败上限 → abnormal


def _eng():
    for name in ("ccc_engine", "ccc_engine_test", "ccc_engine_parallel_test", "__main__"):
        m = sys.modules.get(name)
        if m is not None and hasattr(m, "engine_log"):
            return m
    for m in sys.modules.values():
        f = getattr(m, "__file__", None)
        if f and str(f).endswith("ccc-engine.py") and hasattr(m, "engine_log"):
            return m
    return None


def _engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)


def _verdict_file(ws: Path, tid: str) -> Path:
    return ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"


def _verdict_is_valid(ws: Path, tid: str) -> bool:
    """verdict 文件必须存在且非空（空文件视为未产出）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        return bool(vf.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def _verdict_is_timeout(ws: Path, tid: str) -> bool:
    """检查 verdict 文件是否标记为 TIMEOUT（reviewer LLM 超时但未 quarantine）。"""
    vf = _verdict_file(ws, tid)
    if not vf.is_file():
        return False
    try:
        content = vf.read_text(encoding="utf-8")
        return "**Verdict:** TIMEOUT" in content
    except OSError:
        return False


def _clear_verdict(ws: Path, tid: str) -> None:
    """删除 verdict 文件，使 _verdict_is_valid 返回 False，触发 engine 重试。"""
    vf = _verdict_file(ws, tid)
    try:
        vf.unlink(missing_ok=True)
    except OSError:
        pass


def _parse_verdict_status(content: str) -> str | None:
    """F-FLOW-03: 从 verdict 文件解析 **Verdict:** 字段，不使用裸子串。"""
    for line in content.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("**verdict:**") or low.startswith("verdict:"):
            raw = stripped.split(":", 1)[1].strip().strip("*").strip()
            return raw.split()[0].upper() if raw else None
    return None


def _run_pytest(ws: Path) -> tuple[int, str]:
    """在 workspace 跑 pytest tests/；有 .venv 则走 .venv/bin/pytest。"""
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]
    try:
        r = subprocess.run(
            cmd,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=cfg.phase_timeout,
        )
        stdout = (
            r.stdout
            if isinstance(r.stdout, str)
            else (r.stdout.decode("utf-8", errors="replace") if r.stdout else "")
        )
        stderr = (
            r.stderr
            if isinstance(r.stderr, str)
            else (r.stderr.decode("utf-8", errors="replace") if r.stderr else "")
        )
        output = stdout + stderr
        return r.returncode, output
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout
            if isinstance(exc.stdout, str)
            else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        )
        stderr = (
            exc.stderr
            if isinstance(exc.stderr, str)
            else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
        )
        output = stdout + stderr
        return 1, output
    except OSError as exc:
        return 1, str(exc)


def _record_pytest_failure(ws: Path, tid: str, exit_code: int, output: str) -> None:
    """pytest 失败时写 verdict + pids 摘要（供 OpenCode relaunch 回灌）。"""
    vf = _verdict_file(ws, tid)
    vf.parent.mkdir(parents=True, exist_ok=True)
    snippet = output[-2000:] if output else "(无输出)"
    section = (
        f"\n\n## Engine pytest 检查\n\n"
        f"- **退出码**: {exit_code}\n\n"
        f"```\n{snippet}\n```\n"
    )
    try:
        if vf.is_file():
            vf.write_text(vf.read_text(encoding="utf-8") + section, encoding="utf-8")
        else:
            vf.write_text(
                f"# Verdict: {tid}\n\n**FAIL** (engine pytest)\n{section}",
                encoding="utf-8",
            )
    except OSError as exc:
        _engine_log(f"写入 pytest 失败记录到 verdict 失败: {exc}")
    try:
        pids = ws / ".ccc" / "pids"
        pids.mkdir(parents=True, exist_ok=True)
        (pids / f"{tid}.pytest_fail.md").write_text(
            f"exit_code={exit_code}\n\n{snippet}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        _engine_log(f"写入 pytest_fail.md 失败: {exc}")


def _git_sequencer_active(ws: Path) -> bool:
    """True if mid revert / merge / cherry-pick / rebase."""
    git = Path(ws) / ".git"
    markers = (
        git / "REVERT_HEAD",
        git / "MERGE_HEAD",
        git / "CHERRY_PICK_HEAD",
        git / "rebase-merge",
        git / "rebase-apply",
        git / "sequencer",
    )
    return any(m.exists() for m in markers)


def _abort_in_progress_git(ws: Path) -> None:
    """Best-effort abort any in-progress git sequencer. Never leave REVERT_HEAD."""
    env = _sanitized_env()
    for args in (
        ["git", "revert", "--abort"],
        ["git", "merge", "--abort"],
        ["git", "cherry-pick", "--abort"],
        ["git", "rebase", "--abort"],
    ):
        try:
            subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=20,
                cwd=str(ws),
                env=env,
            )
        except Exception:
            continue


def _record_revert_skip(ws: Path, tid: str, why: str) -> None:
    try:
        from _failure_ledger import record_failure

        record_failure(
            ws,
            task_id=tid,
            role="verdict-gate",
            reason=f"revert_skipped: {why}",
            related_stats_event="revert_skip",
            to_col="planned",
            extra={"why": why},
        )
    except Exception as exc:
        _engine_log(f"[verdict-gate] {tid} record revert_skip failed: {exc}")


def _revert_task_commit(ws: Path, tid: str) -> bool:
    """Verdict FAIL 时回滚 task 的最后一个 commit（须属于本 task 且仍在 HEAD 祖先）。

    产线提效 P3：冲突/失败必须 ``git revert --abort``，禁止留下半截 revert 停仓。
    冲突策略：skip revert + failures 账本，卡回 planned（由调用方移动）。
    """
    phases_file = ws / ".ccc" / "phases" / f"{tid}.phases.json"
    if not phases_file.exists():
        return False

    # 已有半截 sequencer → 先 abort 再决定
    if _git_sequencer_active(ws):
        _engine_log(
            f"[verdict-gate] {tid} 检测到进行中的 git 操作，先 abort 再评估 revert"
        )
        _abort_in_progress_git(ws)
        if _git_sequencer_active(ws):
            _engine_log(f"[verdict-gate] {tid} abort 后仍有 sequencer → skip revert")
            _record_revert_skip(ws, tid, "sequencer_stuck_after_abort")
            return False

    try:
        phases_data = _load_phases(tid, ws)
        commits = [
            p.get("commit", "")
            for p in phases_data
            if p.get("commit") and p.get("commit") not in ("null", "None", "")
        ]
        if not commits:
            return False
        last_commit = str(commits[-1]).strip()
    except (OSError, json.JSONDecodeError) as exc:
        _engine_log(f"[verdict-gate] {tid} 读 commit hash 失败: {exc}")
        return False

    # 安全：commit 必须是当前 HEAD 的祖先，且 log 提到本 task id（避免 revert 错卡/错仓）
    try:
        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", last_commit, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(ws),
            env=_sanitized_env(),
        )
        if anc.returncode != 0:
            _engine_log(
                f"[verdict-gate] {tid} skip revert {last_commit[:12]}: not ancestor of HEAD"
            )
            _record_revert_skip(ws, tid, "not_ancestor")
            return False
        msg = subprocess.run(
            ["git", "log", "-1", "--format=%s%n%b", last_commit],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(ws),
            env=_sanitized_env(),
        )
        body = (msg.stdout or "") + (msg.stderr or "")
        if tid not in body and tid.split("-w")[0] not in body:
            _engine_log(
                f"[verdict-gate] {tid} skip revert {last_commit[:12]}: "
                f"commit message does not mention task id"
            )
            _record_revert_skip(ws, tid, "commit_msg_mismatch")
            return False
    except Exception as exc:
        _engine_log(f"[verdict-gate] {tid} revert precheck 异常: {exc}")
        _abort_in_progress_git(ws)
        return False

    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", last_commit],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ws),
            env=_sanitized_env(),
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "")[:300]
            _engine_log(
                f"[verdict-gate] {tid} revert {last_commit[:12]} 失败 → abort: {err}"
            )
            _abort_in_progress_git(ws)
            if _git_sequencer_active(ws):
                _engine_log(
                    f"[verdict-gate] {tid} CRITICAL: abort 后仍有 REVERT_HEAD/sequencer"
                )
            _record_revert_skip(ws, tid, f"conflict_or_fail: {err[:120]}")
            return False
        _engine_log(f"[verdict-gate] {tid} 已 revert commit {last_commit[:12]}")
        return True
    except Exception as exc:
        _engine_log(f"[verdict-gate] {tid} revert 异常 → abort: {exc}")
        _abort_in_progress_git(ws)
        _record_revert_skip(ws, tid, f"exception: {exc}")
        return False


def _handle_fail_to_planned(
    ws: Path,
    tid: str,
    store,
    *,
    status: str,
    eng=None,
) -> bool:
    """R1/R2/R3: fail pack → maybe repair → revert+align phases → planned.

    Returns False (gate not passed). Quarantines when fail_loops≥3.
    """
    label = _ws_label(ws)
    vtxt = ""
    try:
        vf = _verdict_file(ws, tid)
        if vf.is_file():
            vtxt = vf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        vtxt = ""

    try:
        from _failure_learning import write_review_fail_pack

        write_review_fail_pack(ws, tid, status=status, verdict_text=vtxt)
    except Exception as exc:
        _engine_log(f"[verdict-gate] [{label}] {tid} write review_fail: {exc}")

    fail_n = 0
    try:
        meta = next(
            (t for t in store.list_tasks("testing") if t["id"] == tid),
            None,
        )
        if meta is None:
            _col, meta = store.find_task(tid)
        fail_n = int((meta or {}).get("review_fail_loops") or 0) + 1
        store.patch_task(tid, {"review_fail_loops": fail_n})
    except Exception as exc:
        _engine_log(f"[verdict-gate] [{label}] {tid} fail_loop patch: {exc}")
        fail_n = 1

    if fail_n >= 3:
        cur_phase = _current_running_phase(tid)
        if eng:
            eng._quarantine_with_notify(
                ws,
                tid,
                f"reviewer_fail_loop_exhausted ({fail_n})",
                store,
                phase=cur_phase,
            )
        return False

    try:
        from _failure_learning import (
            needs_plan_repair,
            read_review_fail_pack,
            repair_work_plan,
        )

        pack = read_review_fail_pack(ws, tid)
        if needs_plan_repair(fail_loops=fail_n, fail_pack_text=pack):
            rr = repair_work_plan(ws, tid, fail_loops=fail_n, use_llm=False)
            _engine_log(f"[verdict-gate] [{label}] {tid} R2 repair → {rr}")
    except Exception as exc:
        _engine_log(f"[verdict-gate] [{label}] {tid} R2 repair err: {exc}")

    reverted = _revert_task_commit(ws, tid)
    try:
        from _failure_learning import align_phases_after_revert

        al = align_phases_after_revert(ws, tid)
        _engine_log(
            f"[verdict-gate] [{label}] {tid} phases align "
            f"reverted={reverted} {al}"
        )
    except Exception as exc:
        _engine_log(f"[verdict-gate] [{label}] {tid} phases align: {exc}")

    col_now = _find_task_column(store, tid)
    if col_now == "testing":
        store.move_task(tid, "testing", "planned")
    elif col_now and col_now != "planned":
        try:
            if col_now == "abnormal":
                store.move_task(tid, "abnormal", "planned")
            elif col_now == "in_progress":
                store.move_task(tid, "in_progress", "planned")
        except Exception as exc:
            _engine_log(
                f"[verdict-gate] [{label}] {tid} "
                f"rollback move from {col_now} failed: {exc}"
            )
    _clear_verdict(ws, tid)
    store.update_index()
    return False


def _run_reviewer_tester_gate(ws: Path, tid: str) -> bool:
    """reviewer verdict + tester + engine pytest 双门禁。通过才移 verified。"""
    eng = _eng()
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)

    # complexity=small 仅表规模提示，禁止 stub 跳过 reviewer+tester（假绿）
    task_meta = next((t for t in store.list_tasks("testing") if t["id"] == tid), None)
    _ = task_meta  # retained for future size-based timeouts

    timeout_retries = cfg.reviewer_retry_on_timeout
    timeout_count = 0
    verdict_ok = False
    max_attempts = max(2, timeout_retries)

    for attempt in range(max_attempts):
        reviewer_role()
        if _verdict_is_valid(ws, tid):
            if _verdict_is_timeout(ws, tid):
                timeout_count += 1
                if timeout_count >= timeout_retries:
                    _engine_log(
                        f"[{label}] {tid} reviewer 超时重试 {timeout_count}/{timeout_retries} 耗尽 → abnormal"
                    )
                    cur_phase = _current_running_phase(tid)
                    if eng:
                        eng._quarantine_with_notify(
                            ws, tid, "reviewer 超时重试耗尽", store, phase=cur_phase
                        )
                    return False
                _clear_verdict(ws, tid)
                _ensure_task_in_testing(store, tid)
                _engine_log(
                    f"[{label}] {tid} reviewer 超时，等待重试 (attempt {attempt + 1}/{timeout_retries})"
                )
                time.sleep(30)
                continue
            # 有效 verdict 必须是 PASS 才继续 tester；FAIL 立即回滚，禁止 tester 抢先 verified
            try:
                _early = _parse_verdict_status(_verdict_file(ws, tid).read_text())
            except OSError:
                _early = None
            if _early in ("FAIL", "FALLBACK", "QUARANTINED"):
                _engine_log(
                    f"[verdict-gate] [{label}] {tid} "
                    f"verdict={_early} — 触发回滚（先于 tester）"
                )
                return _handle_fail_to_planned(
                    ws, tid, store, status=str(_early), eng=eng
                )
            if _early == "PASS" or _early is None:
                # None: 旧格式无 Verdict 行但文件非空 — 保守视为可继续（兼容）
                verdict_ok = True
                break
            _engine_log(
                f"[{label}] {tid} verdict status={_early!r} 非 PASS，重试"
            )
            _clear_verdict(ws, tid)
            _ensure_task_in_testing(store, tid)
            continue

        _engine_log(
            f"[{label}] {tid} reviewer 未产出有效 verdict (attempt {attempt + 1}/{max_attempts})"
        )
        _ensure_task_in_testing(store, tid)
        if attempt == max_attempts - 1 and not verdict_ok:
            _engine_log(f"[{label}] {tid} reviewer verdict 重试耗尽 → abnormal")
            cur_phase = _current_running_phase(tid)
            if eng:
                eng._quarantine_with_notify(
                    ws, tid, "reviewer 未产出 verdict", store, phase=cur_phase
                )
            store.update_index()
            return False

    _ensure_task_in_testing(store, tid)

    try:
        tester_role()
    except Exception as exc:
        _engine_log(f"[{label}] {tid} tester_role 异常: {exc}")

    _ensure_task_in_testing(store, tid)

    tests_dir = ws / "tests"
    skip_pytest = False
    try:
        from _ccc_hygiene import task_skips_forced_pytest

        skip_pytest = task_skips_forced_pytest(ws, tid, task_meta)
    except Exception as exc:
        _engine_log(f"[{label}] {tid} hygiene pytest probe: {exc}")
    if skip_pytest:
        _engine_log(
            f"[{label}] {tid} ops/ccc-hygiene — 跳过 engine 强制 pytest"
        )
    elif tests_dir.is_dir():
        exit_code, output = _run_pytest(ws)
        if eng:
            eng._log_stats(ws, "pytest", tid, exit_code=exit_code, output_len=len(output))
        if exit_code != 0:
            _record_pytest_failure(ws, tid, exit_code, output)
            pids_dir = ws / ".ccc" / "pids"
            pids_dir.mkdir(parents=True, exist_ok=True)
            fail_marker = pids_dir / f"{tid}.pytest_fails"
            try:
                fails = int(fail_marker.read_text().strip() or "0")
            except (OSError, ValueError):
                fails = 0
            fails += 1
            fail_marker.write_text(str(fails))
            if fails >= _PYTEST_FAIL_MAX:
                _engine_log(
                    f"[{label}] {tid} pytest 连续失败 {fails}/{_PYTEST_FAIL_MAX} → abnormal"
                )
                cur_phase = _current_running_phase(tid)
                if eng:
                    eng._quarantine_with_notify(
                        ws,
                        tid,
                        f"pytest 连续失败 {fails} 次 (exit={exit_code})",
                        store,
                        phase=cur_phase,
                    )
                try:
                    fail_marker.unlink(missing_ok=True)
                except OSError:
                    pass
                return False
            _engine_log(
                f"[{label}] {tid} pytest 失败 (exit={exit_code}) "
                f"count={fails}/{_PYTEST_FAIL_MAX}，留在 testing"
            )
            if eng:
                eng._ccc_notify(
                    "CCC",
                    f"任务 {tid} pytest 未通过 (exit={exit_code}) "
                    f"{fails}/{_PYTEST_FAIL_MAX}",
                )
            store.update_index()
            return False
        fail_marker = ws / ".ccc" / "pids" / f"{tid}.pytest_fails"
        fail_summary = ws / ".ccc" / "pids" / f"{tid}.pytest_fail.md"
        try:
            fail_marker.unlink(missing_ok=True)
            fail_summary.unlink(missing_ok=True)
        except OSError:
            pass
    else:
        _engine_log(f"[{label}] {tid} 无 tests/ 目录，跳过 engine pytest")

    if _verdict_is_valid(ws, tid):
        _vf = _verdict_file(ws, tid)
        try:
            _vcontent = _vf.read_text()
            status = _parse_verdict_status(_vcontent)
            if status in ("FAIL", "FALLBACK", "QUARANTINED"):
                _engine_log(
                    f"[verdict-gate] [{_ws_label(ws)}] {tid} "
                    f"verdict={status} — 触发回滚"
                )
                return _handle_fail_to_planned(
                    ws, tid, store, status=str(status), eng=eng
                )
        except OSError:
            pass

    if verdict_ok:
        col = _find_task_column(store, tid)
        if col == "testing":
            store.move_task(tid, "testing", "verified")
            if eng:
                eng._log_stats(ws, "move", tid, from_col="testing", to_col="verified")
        store.update_index()
        return _find_task_column(store, tid) == "verified"

    store.update_index()
    return False


def _refresh_parent_epic(ws: Path, work_tid: str) -> None:
    """子卡进入 verified/released 后立刻刷新 parent epic 五态。"""
    try:
        store = _get_store(ws)
        _col, task = store.find_task(work_tid)
        parent = (task or {}).get("parent_id")
        if not parent:
            from _board_store import normalize_task_view as _ntv

            task = _ntv(task or {"id": work_tid}, column=_col or "testing")
            parent = task.get("parent_id")
        if not parent:
            return
        from _product_fanout import refresh_epic_lifecycle

        new = refresh_epic_lifecycle(store, str(parent))
        if new:
            _engine_log(f"[{_ws_label(ws)}] epic {parent} refresh → {new}")
    except Exception as exc:
        _engine_log(f"[{_ws_label(ws)}] refresh parent epic for {work_tid}: {exc}")


def _run_verified_kb_gate(ws: Path) -> None:
    """v0.38: 扫 verified → kb_role → released（补齐 7 角色闭环）。"""
    eng = _eng()
    _activate_workspace(ws)
    store = _get_store(ws)
    verified = store.list_tasks("verified")
    if not verified:
        return
    label = _ws_label(ws)
    _engine_log(f"[{label}] verified 列有 {len(verified)} 个任务，跑 kb_role")
    try:
        result = kb_role()
        moved = (result or {}).get("moved") or []
        for tid in moved:
            if eng:
                eng._log_stats(ws, "move", tid, from_col="verified", to_col="released")
            _engine_log(f"[{label}] {tid} ✓ kb → released")
            _refresh_parent_epic(ws, tid)
        store.update_index()
    except Exception as exc:
        _engine_log(f"[{label}] kb_role 异常: {exc}")


def _testing_gate_budget() -> tuple[int, float]:
    """Return (max_tasks_per_tick, wall_budget_sec). Env overrides Config."""
    import os

    max_n = getattr(cfg, "testing_gate_max_per_tick", 1)
    budget = getattr(cfg, "testing_gate_budget_sec", 180)
    try:
        max_n = int(os.environ.get("CCC_TESTING_GATE_MAX", max_n) or max_n)
    except (TypeError, ValueError):
        pass
    try:
        budget = float(os.environ.get("CCC_TESTING_GATE_BUDGET", budget) or budget)
    except (TypeError, ValueError):
        pass
    return max(1, max_n), max(30.0, float(budget))


def _kill_ws_gate_procs(ws: Path, tid: str) -> list[int]:
    """止损：杀掉本仓门禁相关的 pytest / claude 子进程树，清 review-lock。

    返回被发信号的 pid 列表（best-effort）。
    """
    import os
    import signal

    killed: list[int] = []
    ws_s = str(Path(ws).resolve())
    patterns = (
        f"{ws_s}/.venv/bin/pytest",
        f"{ws_s}/.venv/bin/python",  # pytest often shows as python + argv
        "claude -p",
        "claude -p --model",
    )
    try:
        r = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=8,
            env=_sanitized_env(),
        )
        lines = (r.stdout or "").splitlines()
    except Exception as exc:
        _engine_log(f"[testing-gate] ps for kill failed: {exc}")
        lines = []

    candidates: list[int] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        cmd = parts[1]
        # pytest：命令行含本仓路径
        if "pytest" in cmd and ws_s in cmd:
            candidates.append(pid)
            continue
        # claude：与评审相关；偏保守只杀含 -p 的
        if "claude" in cmd and " -p" in cmd:
            candidates.append(pid)
            continue
        for pat in patterns:
            if pat in cmd and (ws_s in cmd or "claude" in cmd):
                candidates.append(pid)
                break

    # 去重并排除自己
    self_pid = os.getpid()
    for pid in sorted(set(candidates)):
        if pid == self_pid:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    if killed:
        time.sleep(1.0)
        for pid in killed:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    # 清本卡 review-lock，避免下一 tick 永久「持锁跳过」
    lock = Path(ws) / ".ccc" / "review-locks" / f"{tid}.lock"
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        pass
    if killed:
        _engine_log(
            f"[testing-gate] {tid} budget timeout → killed pids={killed}"
        )
    return killed


def _run_reviewer_tester_gate_budgeted(
    ws: Path, tid: str, *, timeout_s: float
) -> str:
    """在墙钟内跑门禁。返回 ok|fail|timeout。

    timeout：杀门禁子进程，卡留 testing，供下一 tick 续。
    """
    import threading

    box: dict = {"done": False, "ok": False, "err": None}

    def _worker() -> None:
        try:
            box["ok"] = bool(_run_reviewer_tester_gate(ws, tid))
        except Exception as exc:  # noqa: BLE001 — 门禁异常不得拖死 tick
            box["err"] = exc
        finally:
            box["done"] = True

    t = threading.Thread(
        target=_worker,
        name=f"testing-gate-{tid[:24]}",
        daemon=True,
    )
    t.start()
    # 使用调用方传入的剩余预算；勿抬到固定 5s（单测与紧预算会失真）
    t.join(timeout=max(0.05, float(timeout_s)))
    if t.is_alive() or not box["done"]:
        _kill_ws_gate_procs(ws, tid)
        # 再给线程一点时间从 TimeoutExpired/BrokenPipe 退出
        t.join(timeout=5.0)
        _engine_log(
            f"[{_ws_label(ws)}] {tid} testing 门禁墙钟超时 "
            f"({timeout_s:.0f}s) → 留 testing，下 tick 续"
        )
        return "timeout"
    if box["err"] is not None:
        _engine_log(
            f"[{_ws_label(ws)}] {tid} reviewer/tester 门禁异常: {box['err']}"
        )
        return "fail"
    return "ok" if box["ok"] else "fail"


def _run_testing_tasks_gate(ws: Path) -> None:
    """对 testing 列跑 reviewer/tester 门禁（限张 + 限时，产线提效 P4）。

    单次门禁也受墙钟约束：超时杀 pytest/claude 进程树，留 testing，下一 tick 续。
    """
    _activate_workspace(ws)
    store = _get_store(ws)
    label = _ws_label(ws)
    max_n, budget_s = _testing_gate_budget()
    deadline = time.monotonic() + budget_s
    done_n = 0
    for task in store.list_tasks("testing"):
        if done_n >= max_n:
            _engine_log(
                f"[{label}] testing 门禁达每 tick 上限 {max_n}，余卡下 tick"
            )
            break
        remaining = deadline - time.monotonic()
        if remaining <= 5.0:
            _engine_log(
                f"[{label}] testing 门禁墙钟预算 {budget_s:.0f}s 耗尽，余卡下 tick"
            )
            break
        tid = task["id"]
        _engine_log(
            f"[{label}] testing 门禁: {tid} "
            f"({done_n + 1}/{max_n}, budget={remaining:.0f}s)"
        )
        outcome = _run_reviewer_tester_gate_budgeted(
            ws, tid, timeout_s=remaining
        )
        if outcome == "ok":
            try:
                _refresh_parent_epic(ws, tid)
            except Exception as exc:
                _engine_log(f"[{label}] {tid} refresh epic: {exc}")
        if outcome == "timeout":
            # 本 tick 不再开下一张，避免连环超时
            break
        done_n += 1
