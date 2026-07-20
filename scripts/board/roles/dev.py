"""board.roles.dev — extracted from ccc-board.py (behavior-preserving)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import uuid
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config, get_logger, parse_duration
from _executor import _claude_env, _sanitized_env
from _board_store import FileBoardStore, _atomic_write as _store_atomic_write
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _utils import sanitize_prompt_input as _sanitize_prompt_input
from _claude_cli import ClaudeCliMissing, resolve_claude_cli
import phase_lint

from board.context import get_workspace, set_workspace, board_dir, ccc_home
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import build_dev_phase_prompt
from board.phase import (
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _move_task_to_abnormal_if_all_terminal_failed,
)
from board.roles.common import (
    cfg,
    store,
    _log,
    CCC_HOME,
    MAX_RETRY,
    MAX_STALE_HOURS,
    sanitize_id,
    now_iso,
    _quarantine,
    list_tasks,
    move_task,
    create_task,
    update_index,
    _get_cfg,
    _get_store,
    _reset_lazy,
    _backoff_seconds,
    _load_timeout,
    _load_retry_cap,
    _load_retry_from_phases,
    _claude_bin,
    _get_relay_url,
    WORKSPACES,
)

def dev_role() -> dict:
    """开发工程师: 查 in_progress（重试）→ 查 planned（新的）→ opencode 执行"""
    from _role_lock import assert_role_executor

    assert_role_executor("dev", "opencode")
    import subprocess as sp

    moved = []
    task = None
    task_id = ""
    from_col = ""

    # Step 1: 有卡在 in_progress 的任务吗？
    stuck = list_tasks("in_progress")
    if stuck:
        task = stuck[-1]
        task_id = task["id"]
        from_col = "in_progress"
        _log.info("发现卡住任务 %s，准备重试", task_id)

        # 读 phases 里的 retry 计数 + retry_at（JSONL 格式，跳过 schema_version 元数据行）
        phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        retry_at = None
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line:
                            continue
                        try:
                            _meta = json.loads(_line)
                            if "schema_version" in _meta:
                                continue  # 跳过 schema_version 元数据行
                        except json.JSONDecodeError:
                            continue
                        parsed = _meta
                        # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                        if isinstance(parsed, list):
                            parsed = parsed[0] if parsed else {}
                        retry = parsed.get("retry", 0)
                        retry_at = parsed.get("retry_at")
                        break
        except json.JSONDecodeError as exc:
            _log.debug("phases parse failed for %s: %s", task_id, exc)

        # ★ 退避前先检查 .done（防退避死锁）
        _done_early = get_workspace() / ".ccc" / "pids" / f"{task_id}.done"
        if _done_early.exists():
            _log.info("%s .done 存在，跳过退避直接处理结果", task_id)
        else:
            # 退避检查：如果在退避期内，跳过此任务的这一轮
            if retry_at:
                from datetime import datetime as _dt

                try:
                    wait_until = _dt.fromisoformat(retry_at)
                    if _dt.now(timezone.utc) < wait_until.replace(tzinfo=timezone.utc):
                        remaining = (
                            wait_until.replace(tzinfo=timezone.utc)
                            - _dt.now(timezone.utc)
                        ).total_seconds()
                        _log.info(
                            "%s 退避中（还剩 %.0fs），跳过本轮，检查 planned",
                            task_id,
                            remaining,
                        )
                        # 重置 task，使执行流落入 Step 2（planned）
                        task = None
                        task_id = ""
                        from_col = ""
                except (ValueError, TypeError) as exc:
                    _log.debug("retry_at parse failed for %s: %s", task_id, exc)

        # 退避跳过：不增 retry，直接 fall through 到 Step 2（planned）
        if task is not None:
            retry += 1

        if retry >= MAX_RETRY:
            # 达到最大重试 → 异常隔离
            _quarantine(task_id, f"重试{MAX_RETRY}次全部失败，已移入异常列")
            # 同时创建紧急修复任务到 backlog
            bug_id = f"emergency-{task_id}"
            bug_title = (
                f"紧急修复: {task.get('title', task_id)}（重试{MAX_RETRY}次失败）"
            )
            create_task(
                {
                    "id": bug_id,
                    "title": bug_title,
                    "description": f"自动升舱:\n{task_id} 重试{MAX_RETRY}次均失败，已移入异常列。",
                }
            )
            _log.error(
                "%s 重试%d次失败 → quarantine + 升舱 %s",
                task_id,
                MAX_RETRY,
                bug_id,
            )
            return {
                "role": "dev",
                "moved": [],
                "error": "quarantined",
                "counts": update_index(),
            }

        # 计算退避时间（v0.24.7 A24-14: retry=0 也强制 60s 最小退避 first backoff）
        backoff = _backoff_seconds(retry - 1) if retry else 60
        retry_at_iso = (
            (datetime.now(timezone.utc) + timedelta(seconds=backoff)).isoformat()
            if retry >= 0
            else None
        )
        # 更新 retry 计数 + retry_at（JSONL，跳过 schema_version 元数据行）
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _line_s = _line.strip()
                    if not _line_s:
                        continue
                    try:
                        _meta = json.loads(_line_s)
                        if "schema_version" in _meta:
                            continue  # 跳过 schema_version 元数据行
                    except json.JSONDecodeError:
                        continue
                    phase = _meta
                    # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                    if isinstance(phase, list):
                        phase = phase[0] if phase else {}
                    phase["retry"] = retry
                    phase["retry_at"] = retry_at_iso
                    lines[i] = json.dumps(phase, ensure_ascii=False)
                    break
                _store_atomic_write(phases_file, "\n".join(lines))
        except json.JSONDecodeError as exc:
            _log.debug("phases update failed for %s: %s", task_id, exc)
        _log.info("%s 第 %d/%d 次重试，退避 %s", task_id, retry, MAX_RETRY, backoff)

    # Step 2: in_progress 无事，取 planned（迭代，跳过错/缺 plan 的任务）
    if not task:
        planned = list_tasks("planned")
        if not planned:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "无任务",
            }
        # 迭代 planned 任务，跳过缺 plan/phases 的（移入异常），处理第一个合法的
        for candidate in planned:
            cid = candidate["id"]
            cplan = get_workspace() / ".ccc" / "plans" / f"{cid}.plan.md"
            cphases = get_workspace() / ".ccc" / "phases" / f"{cid}.phases.json"
            if cplan.exists() and cphases.exists():
                task = candidate
                task_id = cid
                from_col = "planned"
                break
            else:
                # 缺失 plan/phases → 移入异常列，不阻塞其他任务
                _quarantine(cid, "dev_role: 缺 plan 或 phases 文件, 无法执行")
                _log.info("%s 缺 plan/phases, 已移入 abnormal", cid)
        if not task:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "planned 任务均缺 plan/phases",
            }
        move_task(task_id, "planned", "in_progress")

    plan = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(phases_file, default=cfg.default_timeout)
    # F-PROMPT-01: 定位当前 phase（非硬编码 p1）
    try:
        _cur = _current_running_phase(task_id) or 1
    except Exception:
        _cur = 1
    phase_id = f"{task_id}-p{_cur}"

    # 从 plan.md 生成 executor prompt
    plan_content = plan.read_text()
    # v0.28.0 (F-2): 大变更优化 — 估算 plan 长度，>100 行强制模型分批改
    # v0.28.0 (F2-H1 修): 加权判定 — 纯行数 + 文件引用数×20 + section 数×10
    plan_lines = plan_content.splitlines()
    plan_size = len(plan_lines)
    file_mentions = len(
        set(
            line.strip()
            for line in plan_lines
            if line.strip().startswith(("/", "`/"))
            and not line.strip().startswith(("//", "#"))
        )
    )
    section_count = len(
        [
            line
            for line in plan_lines
            if line.strip().startswith("##") and " " in line and line.strip() != "##"
        ]
    )
    plan_weight = plan_size + file_mentions * 20 + section_count * 10
    size_hint = ""
    if plan_weight > cfg.size_hint_threshold:
        size_hint = (
            f"\n## 大变更提示（v0.28.0 F-2）\n"
            f"plan 加权 {plan_weight}（{plan_size} 行 + {file_mentions} 文件引用×20 + "
            f"{section_count} 章节×10）> {cfg.size_hint_threshold}，属于大变更。\n"
            f"- **必须分批改**：先改一个核心文件 + commit，再继续\n"
            f"- 每个 commit 控制在 50 行内（避免 reviewer LLM timeout）\n"
            f"- 白名单路径一次只动 1-2 个\n"
        )
    _ws = str(get_workspace().resolve())
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## 工作目录硬门（违者本卡 FAIL）\n"
        f"- **唯一 cwd**：`{_ws}`\n"
        f"- 所有 Read/Write/Edit/Bash/git 必须在该目录内；相对路径相对该 cwd\n"
        f"- **禁止**写到 `/Users/apple/program/CCC` 或其他仓库"
        f"（除非本 workspace 路径就是该仓库）\n"
        f"- plan 若误写其他绝对路径，以本 cwd 为准，忽略错误根路径\n\n"
        f"## 当前 Phase（强制）\n"
        f"- **只做 Phase {_cur}**，不得实现其他 phase 的需求\n"
        f"- 不得修改不属于本 phase 白名单的文件\n"
        f"- 完成定义仅对本 phase 生效；其他 phase 留给后续调度\n\n"
        f"## Plan（全文供参考；执行范围仍以本 phase 为准）\n\n{plan_content}\n\n"
        f"{size_hint}\n"
        f"## 完成定义（仅 Phase {_cur}）\n"
        f"1. 仅实现 Phase {_cur} 对应需求\n"
        f"2. 跑本 phase 相关测试（如有）\n"
        f"3. 提交一个 commit（message 含 `{task_id}` 与 `phase={_cur}`）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单，且不提前做后续 phase\n"
    )

    # 写 prompt 文件到 .ccc/pids/（跟其他 task 文件一起清理，不泄漏）
    pids_dir = get_workspace() / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    try:
        _log.info(
            "%s phase=%s timeout=%s retry=%d",
            task_id,
            phase_id,
            timeout_s,
            retry if from_col == "in_progress" else 0,
        )
        done_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.done"
        exitcode_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.exitcode"
        result_path = get_workspace() / ".ccc" / "reports" / f"{task_id}.result.json"
        pid_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.pid"

        # ❗.done 检查必须在 PID 检查之前
        # stale PID 被回收后 os.kill 返回成功，先查 .done 再查 PID
        if done_path.exists():
            exit_code = (
                exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
            )
            result_raw = result_path.read_text() if result_path.exists() else "{}"
            report_dir = get_workspace() / ".ccc" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_dir.joinpath(f"{task_id}.report.md").write_text(
                f"# {task_id} 执行报告\n\n## 信息\n- Phase: {phase_id}\n"
                f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
            )
            for p in [
                done_path,
                exitcode_path,
                pid_path,
                result_path,
                get_workspace() / ".ccc" / "pids" / f"{task_id}.prompt.md",
            ]:
                try:
                    p.unlink()
                except OSError as exc:
                    _log.debug("pids cleanup %s: %s", p, exc)
            if exit_code == "0":
                move_task(task_id, "in_progress", "testing")
                moved.append(task_id)
                _log.info("%s ✓ → testing", task_id)
            else:
                _log.error(
                    "%s ✗ rc=%s（留在 in_progress 下轮重试）", task_id, exit_code
                )
            return {"role": "dev", "moved": moved, "counts": update_index()}

        # PID 检查：.done 不存在时确认 opencode 是否还在跑
        if pid_path.exists():
            try:
                old_pid = int(pid_path.read_text().strip())
                try:
                    os.kill(old_pid, 0)
                    _log.info("%s opencode %d 仍在运行，跳过", task_id, old_pid)
                    return {
                        "role": "dev",
                        "moved": [],
                        "counts": update_index(),
                        "info": f"opencode PID={old_pid} 运行中",
                    }
                except OSError:
                    # stale PID
                    _log.info("%s PID %d 不存在，清理后重试", task_id, old_pid)
                    try:
                        pid_path.unlink()
                    except OSError as exc:
                        _log.debug("stale pid unlink failed for %s: %s", task_id, exc)
            except (ValueError, OSError) as exc:
                _log.debug("pid check parse failed for %s: %s", task_id, exc)

        # 启动 opencode（通过 runner.sh 持久化结果）
        report_dir = get_workspace() / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.report.md"

        proc = sp.Popen(
            [
                str(CCC_HOME / "scripts" / "opencode-runner.sh"),
                task_id,
                str(CCC_HOME),
                str(get_workspace()),
                "--phase",
                phase_id,
                "--prompt",
                prompt_file,
                "--timeout",
                str(timeout_s),
                "--cwd",
                str(get_workspace()),
            ],
            cwd=str(get_workspace()),
            start_new_session=True,
        )
        pid_dir = get_workspace() / ".ccc" / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
        report_path.write_text(
            f"# {task_id} 执行报告\n\n## 信息\n- 状态: 运行中\n- PID: {proc.pid}\n- Started: {now_iso()}\n"
        )
        _log.info("%s 后台启动 PID=%d，下轮检查结果", task_id, proc.pid)

    except Exception as e:  # debug
        import traceback as _tb

        _log.error("\n%s 启动失败: %s\n%s", task_id, e, _tb.format_exc())
    finally:
        # prompt 保留给后台读
        pass

    return {"role": "dev", "moved": moved, "counts": update_index()}


def _phase_scope(task_id: str, phase_num: int) -> list[str]:
    """从 phases.json 取指定 phase 的 scope；空则从 plan 回填（v0.42.1）。"""
    try:
        plan_text = ""
        try:
            pf = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
            if pf.is_file():
                plan_text = pf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        for p in _load_phases(task_id):
            if int(p.get("phase", -1)) == int(phase_num):
                scope = p.get("scope") or []
                if isinstance(scope, list):
                    scope = [str(x) for x in scope if x]
                else:
                    scope = []
                if not scope and plan_text:
                    from _plan_adopt import backfill_scopes

                    filled = backfill_scopes([dict(p)], plan_text)
                    scope = [str(x) for x in (filled[0].get("scope") or []) if x]
                return scope
    except Exception:
        pass
    return []


def _read_pytest_failure_feedback(task_id: str) -> str:
    """读取 pytest 失败摘要（供 relaunch / OpenCode 回灌）。"""
    path = get_workspace() / ".ccc" / "pids" / f"{task_id}.pytest_fail.md"
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        pass
    return ""


def _task_skill_hints_block(task_id: str) -> str:
    """从看板 task.hints 读 Skill 软偏好，拼 prompt 段落。"""
    try:
        from _skills_catalog import format_skill_hints_block
    except ImportError:
        return ""
    tid = sanitize_id(task_id)
    for col in ("in_progress", "planned", "testing", "backlog", "verified"):
        task = next((t for t in list_tasks(col) if t.get("id") == tid), None)
        if not task:
            continue
        hints = task.get("hints") if isinstance(task.get("hints"), dict) else {}
        skills = hints.get("skills") if isinstance(hints.get("skills"), list) else []
        note = hints.get("note") if isinstance(hints.get("note"), str) else ""
        return format_skill_hints_block(skills, note)
    return ""


def _compose_dev_prompt(task_id: str, phase_num: int, plan_content: str) -> str:
    """统一 launch/relaunch 的 OpenCode prompt（cwd 硬门 + scope + pytest 回灌）。"""
    return build_dev_phase_prompt(
        task_id,
        phase_num,
        plan_content,
        workspace=get_workspace(),
        scope=_phase_scope(task_id, phase_num),
        pytest_failure=_read_pytest_failure_feedback(task_id),
        skill_hints=_task_skill_hints_block(task_id),
    )


def _task_pre_head_path(task_id: str) -> Path:
    return get_workspace() / ".ccc" / "pids" / f"{task_id}.pre_head"


def _capture_task_pre_head(task_id: str) -> str:
    """Launch 时记录 HEAD + 跨仓隔离基线（H1 + isolation）。"""
    import subprocess as _sp

    from _workspace_isolation import capture_isolation_baseline

    pids = get_workspace() / ".ccc" / "pids"
    pids.mkdir(parents=True, exist_ok=True)
    head = ""
    try:
        r = _sp.run(
            ["git", "rev-parse", "HEAD"],
            cwd=get_workspace(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            head = (r.stdout or "").strip()
    except Exception as exc:
        _log.warning("[commit-gate] %s capture pre_head failed: %s", task_id, exc)
    _task_pre_head_path(task_id).write_text(head + "\n", encoding="utf-8")
    try:
        capture_isolation_baseline(get_workspace(), task_id)
    except Exception as exc:
        _log.warning("[isolation] %s baseline failed: %s", task_id, exc)
    return head


def _find_task_commit_hash(task_id: str) -> str:
    """仅认 git log --grep=task_id（work 可回落父 epic id）；禁止 HEAD 降级（H1）。"""
    from _task_commit import find_task_commit

    return find_task_commit(get_workspace(), task_id) or ""


def _require_task_commit_for_testing(task_id: str) -> tuple[bool, str, str]:
    """过 testing 前必须有含 task_id 的新 commit，且无跨仓污染。

    DoD 内生化：若工作区有改动但缺 task_id commit，先自动补 commit，
    再验收——禁止 exit 0 后才突然 quarantine。

    Returns: (ok, reason, commit_hash)
    """
    if (os.environ.get("CCC_SKIP_COMMIT_GATE") or "").strip() in ("1", "true", "yes"):
        return True, "skip", ""

    from _workspace_isolation import audit_isolation_after, isolation_enabled

    if isolation_enabled():
        ok_iso, iso_errs = audit_isolation_after(get_workspace(), task_id)
        if not ok_iso:
            return False, "; ".join(iso_errs), ""

    pre_path = _task_pre_head_path(task_id)
    pre = ""
    if pre_path.is_file():
        try:
            pre = pre_path.read_text(encoding="utf-8").strip()
        except OSError:
            pre = ""

    commit = _find_task_commit_hash(task_id)
    if not commit or (pre and commit == pre):
        from _task_commit import ensure_task_commit

        cur_phase = None
        try:
            cur_phase = _current_running_phase(task_id)
        except Exception:
            cur_phase = None
        ok_auto, why_auto, commit = ensure_task_commit(
            get_workspace(),
            task_id,
            phase_num=cur_phase if isinstance(cur_phase, int) else None,
            pre_head=pre,
        )
        if not ok_auto:
            return False, why_auto, commit or ""
        _log.info("[commit-gate] %s DoD auto-commit: %s (%s)", task_id, why_auto, commit[:12])

    if pre and commit == pre:
        return (
            False,
            f"task commit {commit[:12]} equals pre_head — no new commit for {task_id}",
            commit,
        )
    return True, "ok", commit


def _smoke_deliverable_satisfied(task_id: str) -> bool:
    """small 烟测：交付物文件存在且有含 task/epic id 的 commit（不代写 SELF-CHECKS）。"""
    ws = get_workspace()
    tasks = list_tasks("in_progress") + list_tasks("planned") + list_tasks("abnormal")
    task = next((t for t in tasks if t.get("id") == task_id), None)
    complexity = str((task or {}).get("complexity") or "medium").lower()
    blob = f"{(task or {}).get('title', '')} {(task or {}).get('description', '')}"
    smokeish = (
        complexity in ("small", "sm")
        or "flow-smoke" in blob
        or "flow-green" in blob
        or "flow-opt" in blob
        or "写入并提交" in blob
    )
    if not smokeish:
        return False

    candidates: list[str] = [".ccc/flow-smoke.md", "docs/flow-smoke.md"]
    for ph in _load_phases(task_id):
        for s in ph.get("scope") or []:
            if not isinstance(s, str) or not s.strip():
                continue
            s = s.strip()
            p = ws / s
            if p.is_file():
                candidates.append(s)
            elif p.is_dir():
                for name in ("flow-smoke.md", "flow-green.md"):
                    sub = p / name
                    if sub.is_file():
                        candidates.append(str(Path(s) / name))

    existing = []
    seen: set[str] = set()
    for s in candidates:
        if s in seen:
            continue
        seen.add(s)
        if (ws / s).is_file():
            existing.append(s)
    if not existing:
        return False

    from _task_commit import find_task_commit

    commit = find_task_commit(ws, task_id)
    if not commit:
        return False

    # Prefer commit that touches deliverable; else any task commit + file on disk
    try:
        r = subprocess.run(
            ["git", "show", "--name-only", "--format=", commit],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            names = {
                (ln or "").strip().lstrip("./")
                for ln in (r.stdout or "").splitlines()
                if ln.strip()
            }
            if any(s.lstrip("./") in names for s in existing):
                return True
        # Look back a few matching commits
        from _task_commit import _commit_grep_needles

        for needle in _commit_grep_needles(task_id):
            r2 = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--grep",
                    needle,
                    "--format=%H",
                    "--max-count",
                    "5",
                ],
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r2.returncode != 0:
                continue
            for h in (r2.stdout or "").splitlines():
                h = h.strip()
                if len(h) < 40:
                    continue
                r3 = subprocess.run(
                    ["git", "show", "--name-only", "--format=", h],
                    cwd=str(ws),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if r3.returncode != 0:
                    continue
                names = {
                    (ln or "").strip().lstrip("./")
                    for ln in (r3.stdout or "").splitlines()
                    if ln.strip()
                }
                if any(s.lstrip("./") in names for s in existing):
                    return True
    except Exception:
        pass
    # Do NOT green on "file on disk + any task-id commit" — ignored paths
    # (e.g. AGENTS.md under /agents.md gitignore) would false-pass Phase12-style.
    return False

def try_complete_if_gates_satisfied(task_id: str) -> dict | None:
    """门禁已满足时收口 → testing，禁止无意义 relaunch。

    Returns:
      success dict，或 None（未满足 / 不在 in_progress）。
    """
    task_id = sanitize_id(task_id)
    in_prog = list_tasks("in_progress")
    if not any(t["id"] == task_id for t in in_prog):
        return None

    from _opencode_quality_gate import (
        agent_declared_self_checks_passed,
        report_has_self_checks_passed,
    )
    from _task_commit import ensure_task_commit, find_task_commit

    ws = get_workspace()
    commit = find_task_commit(ws, task_id)
    if not commit:
        # DoD：有交付物脏树时先补 task_id commit，再谈收口
        cur_phase = None
        try:
            cur_phase = _current_running_phase(task_id)
        except Exception:
            cur_phase = None
        ok_auto, why_auto, commit = ensure_task_commit(
            ws,
            task_id,
            phase_num=cur_phase if isinstance(cur_phase, int) else None,
            pre_head="",
        )
        if ok_auto and commit:
            _log.info(
                "[salvage] %s DoD auto-commit before gates: %s (%s)",
                task_id,
                why_auto,
                commit[:12],
            )
        else:
            commit = find_task_commit(ws, task_id) or ""
    if not commit:
        return None

    report_path = ws / ".ccc" / "reports" / f"{task_id}.report.md"
    result_path = ws / ".ccc" / "reports" / f"{task_id}.result.json"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    result_raw = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""

    declared = agent_declared_self_checks_passed(report, result_raw)
    smoke_ok = False if declared else _smoke_deliverable_satisfied(task_id)
    if not declared and not smoke_ok:
        return None

    # 禁止用 missing-SELF-CHECKS stub 盖住已有标记；有标记则 materialize
    if declared and not report_has_self_checks_passed(report):
        body = (report or f"# {task_id} 执行报告\n").rstrip()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(body + "\n\nALL SELF-CHECKS PASSED\n", encoding="utf-8")
        _log.info(
            "[salvage] %s materialize SELF-CHECKS from agent evidence → report.md",
            task_id,
        )
    elif smoke_ok and not report.strip():
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            f"# {task_id} 执行报告\n\n"
            f"## 信息\n- 状态: salvage（commit+deliverable 已齐）\n"
            f"- commit: {commit[:12]}\n",
            encoding="utf-8",
        )

    cur_phase = _current_running_phase(task_id) or 1
    # 记录 commit 到 phases + mark done
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if phases_file.is_file():
        try:
            lines = phases_file.read_text(encoding="utf-8").splitlines()
            updated: list[str] = []
            for line in lines:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                    if "schema_version" in d:
                        d["commit"] = commit
                    elif d.get("phase") == cur_phase:
                        d["status"] = "done"
                        d["commit"] = commit
                    updated.append(json.dumps(d, ensure_ascii=False))
                except json.JSONDecodeError:
                    updated.append(raw)
            phases_file.write_text("\n".join(updated) + "\n", encoding="utf-8")
        except OSError as exc:
            _log.warning("[salvage] %s phases write failed: %s", task_id, exc)

    try:
        _mark_phase_done(task_id, cur_phase)
    except Exception as exc:
        _log.warning("[salvage] %s mark done failed: %s", task_id, exc)

    # 清 pid 标记；尽力杀残留
    pids_dir = ws / ".ccc" / "pids"
    pid_path = pids_dir / f"{task_id}.pid"
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text().strip())
            if pid > 0:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (OSError, ProcessLookupError):
                        pass
        except (ValueError, OSError):
            pass

    for suffix in (
        ".done",
        ".exitcode",
        ".pid",
        ".prompt.md",
        ".pre_head",
        ".isolation.json",
    ):
        fp = pids_dir / f"{task_id}{suffix}"
        try:
            if fp.exists():
                fp.unlink()
        except OSError:
            pass

    # 若仍有后续 phase，不硬推 testing
    phases_now = _load_phases(task_id)
    executable, blocked, skipped = _resolve_phase_dependencies(phases_now)
    _apply_phase_status_updates(task_id, blocked, skipped)
    phases_now = _load_phases(task_id)
    executable, _blocked, _skipped = _resolve_phase_dependencies(phases_now)
    if executable:
        _log.info(
            "[salvage] %s gates ok but more phases %s — leave in_progress",
            task_id,
            executable,
        )
        return {
            "status": "phase_done",
            "task_id": task_id,
            "phase": cur_phase,
            "next_phase": min(executable),
            "salvaged": True,
        }

    ok_c, why_c, _ch = _require_task_commit_for_testing(task_id)
    if not ok_c:
        _log.warning("[salvage] %s commit-gate after mark: %s", task_id, why_c)
        return None

    move_task(task_id, "in_progress", "testing")
    _log.info(
        "[salvage] %s ✓ gates satisfied → testing (commit=%s declared=%s smoke=%s)",
        task_id,
        commit[:12],
        declared,
        smoke_ok,
    )
    return {
        "status": "success",
        "task_id": task_id,
        "salvaged": True,
        "commit": commit[:40],
    }


def dev_role_launch(task_id: str) -> dict:
    """引擎用：启 opencode 执行 task，返回启动结果

    1. 确认 task 在 planned，有 plan+phases
    2. 挪 planned → in_progress
    3. 启 opencode-runner.sh（后台进程）
    4. 不等待，立即返回
    """
    from _role_lock import assert_role_executor

    assert_role_executor("dev", "opencode")
    task_id = sanitize_id(task_id)
    planned = list_tasks("planned")
    task = next((t for t in planned if t["id"] == task_id), None)
    if not task:
        return {"error": f"task '{task_id}' not in planned", "task_id": task_id}

    cplan = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine: 缺 plan 或 phases 文件")
        return {
            "error": f"task '{task_id}' missing plan/phases, quarantined",
            "task_id": task_id,
        }

    move_task(task_id, "planned", "in_progress")

    # v0.24.3: 用 _current_running_phase() 决定当前应跑哪个 phase，而不是硬编码 -p1。
    # phases.json 可能尚未标 in_progress（launch 是入口），退回到 pending/blocked 中的第一个 phase。
    cur_phase = _current_running_phase(task_id)

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(cphases, default=cfg.default_timeout)

    # 从 phases.json 读 max_retry cap
    max_retry_cap = _load_retry_cap(
        cphases, phase_id=cur_phase, default=getattr(cfg, "DEFAULT_RETRY", 3)
    )

    phase_id = f"{task_id}-p{cur_phase}"
    plan_content = cplan.read_text()
    prompt = _compose_dev_prompt(task_id, cur_phase, plan_content)

    pids_dir = get_workspace() / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)
    _capture_task_pre_head(task_id)

    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp

    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # $2: CCC_HOME（opencode-exec.py 所在目录）
            str(get_workspace()),  # $3: ROOT_DIR（结果文件写到 workspace）
            "--phase",
            phase_id,
            "--prompt",
            prompt_file,
            "--timeout",
            str(timeout_s),
            "--cwd",
            str(get_workspace()),  # opencode 工作目录 = workspace
        ],
        cwd=str(get_workspace()),
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    _log.info(
        "[engine] %s launched PID=%d (retry 0/%d, timeout %ds)",
        task_id,
        proc.pid,
        max_retry_cap,
        timeout_s,
    )

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_relaunch(task_id: str) -> dict:
    """引擎用：失败重试时重新启 opencode（task 已在 in_progress 不挪列）

    与 dev_role_launch 的区别：
    - 不检查 planned，直接读 plan+phases
    - 不挪列（已在 in_progress）
    - 清理旧的 .done/exitcode 后重新启动
    """

    task_id = sanitize_id(task_id)
    salvaged = try_complete_if_gates_satisfied(task_id)
    if salvaged and salvaged.get("status") == "success":
        return {"ok": True, "task_id": task_id, "salvaged": True, **salvaged}

    cplan = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine relaunch: 缺 plan 或 phases 文件")
        return {"error": f"task '{task_id}' missing plan/phases", "task_id": task_id}

    # 清理旧的标记文件
    pids_dir = get_workspace() / ".ccc" / "pids"
    for suffix in [".done", ".exitcode", ".pid", ".prompt.md", ".result.json"]:
        f = pids_dir / f"{task_id}{suffix}"
        if f.exists():
            try:
                f.unlink()
            except OSError as e:
                _log.warning("relaunch marker unlink failed %s: %s", f, e)
        # 也检查 reports/
        f2 = get_workspace() / ".ccc" / "reports" / f"{task_id}{suffix}"
        if f2.exists():
            try:
                f2.unlink()
            except OSError as e:
                _log.warning("relaunch report unlink failed %s: %s", f2, e)

    # v0.24.3: 重启也用 _current_running_phase() 定位当前 phase
    cur_phase = _current_running_phase(task_id)
    phase_id = f"{task_id}-p{cur_phase}"

    # 读 phases 列表（一次读，复用给 timeout/retry）
    phases = _load_phases(task_id)

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(cphases, default=cfg.default_timeout)
    plan_content = cplan.read_text()
    prompt = _compose_dev_prompt(task_id, cur_phase, plan_content)

    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)
    # 保留首次 launch 的 pre_head；缺失时补记（H1）
    if not _task_pre_head_path(task_id).is_file():
        _capture_task_pre_head(task_id)

    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp

    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # $2: CCC_HOME
            str(get_workspace()),  # $3: ROOT_DIR
            "--phase",
            phase_id,
            "--prompt",
            prompt_file,
            "--timeout",
            str(timeout_s),
            "--cwd",
            str(get_workspace()),
        ],
        cwd=str(get_workspace()),
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    max_retry_cap = _load_retry_cap(
        cphases, phase_id=cur_phase, default=getattr(cfg, "DEFAULT_RETRY", 3)
    )
    retry_now = _load_retry_from_phases(phases, phase_id=cur_phase)
    _log.info(
        "[engine] %s relaunched PID=%d (retry %d/%d, timeout %ds)",
        task_id,
        proc.pid,
        retry_now,
        max_retry_cap,
        timeout_s,
    )

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_check_complete(task_id: str) -> dict:
    """引擎用：检查 task 的 opencode 是否完成

    返回:
      {"status": "running"} — 仍在跑
      {"status": "success"} — 完成，已从 in_progress 移到 testing
      {"status": "failed", "retry": N} — 可重试
      {"status": "quarantined"} — 重试耗尽，已隔离
      {"status": "not_found"} — task 不在 in_progress
    """
    task_id = sanitize_id(task_id)
    in_prog = list_tasks("in_progress")
    if not any(t["id"] == task_id for t in in_prog):
        return {"status": "not_found", "task_id": task_id}

    done_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.done"
    if not done_path.exists():
        # A2: 进程仍在跑但门禁已齐 → 收口，不空等
        salvaged = try_complete_if_gates_satisfied(task_id)
        if salvaged and salvaged.get("status") in ("success", "phase_done"):
            return salvaged
        # G4: 检查 PID 是否存活（重启后 .pid 可能指向已死进程）
        pid_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.pid"
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)  # 信号 0 = 只检查存活
                return {"status": "running", "task_id": task_id}
            except (ValueError, OSError, ProcessLookupError):
                # PID 不存在 → 清理标记文件，返回 failed 让 engine 重启
                for f in [
                    pid_path,
                    done_path,
                    get_workspace() / ".ccc" / "pids" / f"{task_id}.exitcode",
                ]:
                    try:
                        f.unlink()
                    except OSError as e:
                        _log.warning("G4 marker unlink failed %s: %s", f, e)
                return {"status": "failed", "retry": 0, "task_id": task_id}
        # 没有 .done 也没有 .pid → 进程已死且标记丢失，返回 failed 让 engine 重启
        # Lesson 44: 此前返回 "running" 导致任务永久卡在 in_progress
        _log.warning("%s 没有 .done 也没有 .pid 标记，视同失败让 engine 重启", task_id)
        return {"status": "failed", "retry": 0, "task_id": task_id}

    exitcode_path = get_workspace() / ".ccc" / "pids" / f"{task_id}.exitcode"
    result_path = get_workspace() / ".ccc" / "reports" / f"{task_id}.result.json"
    exit_code = exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
    result_raw = result_path.read_text() if result_path.exists() else "{}"

    phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
    cur_phase = _current_running_phase(task_id)
    # engine-phase-retry-config: 从 phases.json 读 timeout 用于日志输出
    timeout_s = _load_timeout(phases_file, default=cfg.default_timeout)

    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{task_id}.report.md"
    # v0.37: 不覆盖 opencode/agent 已写的 report.md（此前 stub 覆盖导致
    # SELF-CHECKS 门禁永远失败，触发无限 relaunch）
    _existing_report = (
        report_path.read_text() if report_path.exists() else ""
    ).strip()

    # 标记文件列表（用于清算）
    marker_files = [
        done_path,
        exitcode_path,
        get_workspace() / ".ccc" / "pids" / f"{task_id}.pid",
        get_workspace() / ".ccc" / "pids" / f"{task_id}.prompt.md",
        result_path,
    ]

    if exit_code == "0":
        # v0.30.0: 空报告门禁 — exit_code=0 但报告空或过短，视同失败
        if result_path.exists():
            _result_raw = result_path.read_text()
            if len(_result_raw.strip()) < 50:
                _log.warning(
                    "[gate] %s exit_code=0 但报告 <50 字节，视同失败",
                    task_id,
                )
                return {"status": "failed", "retry": 0, "task_id": task_id}
        # v0.52: 空心成功门禁 — 拒读 ~/.ccc / external_directory 仍 exit 0
        from _opencode_quality_gate import (
            agent_declared_self_checks_passed,
            detect_hollow_opencode_run,
            report_has_self_checks_passed,
        )

        _hollow = detect_hollow_opencode_run(result_raw, _existing_report)
        if _hollow:
            _log.error("[gate] %s hollow success: %s", task_id, _hollow)
            if not _existing_report:
                report_path.write_text(
                    f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
                    f"- 退出码: {exit_code}\n- 门禁: HOLLOW FAIL\n\n"
                    f"## 原因\n{_hollow}\n\n"
                    f"## 输出\n```\n{result_raw[:2000]}\n```\n"
                )
            return {
                "status": "failed",
                "retry": 0,
                "task_id": task_id,
                "error": f"hollow-gate: {_hollow}",
            }

        # SELF-CHECKS：必须由 agent 写出（report.md 或 result stdout）；禁止代写
        if not agent_declared_self_checks_passed(_existing_report, result_raw):
            # 再试 salvage（commit+smoke deliverable）
            salvaged = try_complete_if_gates_satisfied(task_id)
            if salvaged and salvaged.get("status") == "success":
                return salvaged
            _log.error(
                "[gate] %s report/result 缺少 'ALL SELF-CHECKS PASSED'（不代写）",
                task_id,
            )
            # 禁止用 missing stub 覆盖已有含标记的 report
            if not _existing_report:
                report_path.write_text(
                    f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
                    f"- 退出码: {exit_code}\n- 门禁: missing SELF-CHECKS\n\n"
                    f"## 输出\n```\n{result_raw[:2000]}\n```\n"
                )
            elif "ALL SELF-CHECKS PASSED" in _existing_report:
                pass  # keep evidence
            return {
                "status": "failed",
                "retry": 0,
                "task_id": task_id,
                "error": "self-checks-gate: missing ALL SELF-CHECKS PASSED",
            }
        # Agent 只在 stdout 声明时，落盘到 report 供下游可读（不发明新标记）
        if not report_has_self_checks_passed(_existing_report):
            body = (_existing_report or f"# {task_id} 执行报告\n").rstrip()
            report_path.write_text(body + "\n\nALL SELF-CHECKS PASSED\n")
            _existing_report = report_path.read_text()
            _log.info(
                "[gate] %s materialize SELF-CHECKS from agent result → report.md",
                task_id,
            )

        # 成功：清标记文件 + 记录 commit hash + 挪列
        for p in marker_files:
            try:
                p.unlink()
            except OSError as e:
                _log.warning("success marker unlink failed %s: %s", p, e)
        # G1/H1: 仅记录 git log --grep=task_id 的 commit（禁止 HEAD 降级）
        _phases_file = get_workspace() / ".ccc" / "phases" / f"{task_id}.phases.json"
        _hash = _find_task_commit_hash(task_id)
        if _phases_file.exists() and _hash:
            try:
                _lines = _phases_file.read_text().splitlines()
                _updated = []
                for _line in _lines:
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _d = json.loads(_line)
                        if "schema_version" in _d:
                            _d["commit"] = _hash
                        else:
                            _d.setdefault("commit", _hash)
                        _updated.append(json.dumps(_d, ensure_ascii=False) + "\n")
                    except json.JSONDecodeError:
                        _updated.append(_line + "\n")
                _phases_file.write_text("".join(_updated))
                _log.info("[engine] %s ✓ commit %s recorded", task_id, _hash[:12])
            except Exception as _e:
                _log.warning("record commit hash for %s failed: %s", task_id, _e)
        elif not _hash:
            _log.warning(
                "[commit-gate] %s exit_code=0 但无含 task_id 的 commit（不记 HEAD）",
                task_id,
            )
        # v0.38: 多 phase 续跑 — 先 peek 是否终态；终态则 H1 commit 门禁通过后再 mark done
        _phases_peek = []
        for _p in _load_phases(task_id):
            _pc = dict(_p)
            if _pc.get("phase") == cur_phase:
                _pc["status"] = "done"
            _phases_peek.append(_pc)
        _exec_peek, _blk_peek, _skip_peek = _resolve_phase_dependencies(_phases_peek)
        if not _exec_peek:
            _ok, _why, _ch = _require_task_commit_for_testing(task_id)
            if not _ok:
                _log.error("[commit-gate] %s 拒绝进 testing: %s", task_id, _why)
                return {
                    "status": "failed",
                    "retry": 0,
                    "task_id": task_id,
                    "error": f"commit-gate: {_why}",
                }
        _mark_phase_done(task_id, cur_phase)
        _phases_now = _load_phases(task_id)
        _executable, _blocked, _skipped = _resolve_phase_dependencies(_phases_now)
        _apply_phase_status_updates(task_id, _blocked, _skipped)
        _phases_now = _load_phases(task_id)
        _executable, _blocked, _skipped = _resolve_phase_dependencies(_phases_now)
        if _executable:
            _next = min(_executable)
            _log.info(
                "[engine] %s phase %s done → 续跑 phase %s（仍留 in_progress）",
                task_id,
                cur_phase,
                _next,
            )
            return {
                "status": "phase_done",
                "task_id": task_id,
                "phase": cur_phase,
                "next_phase": _next,
            }
        move_task(task_id, "in_progress", "testing")
        _ch = _find_task_commit_hash(task_id)
        _log.info(
            "[engine] %s ✓ all phases done → testing (commit=%s)",
            task_id,
            (_ch[:12] if _ch else "?"),
        )
        return {"status": "success", "task_id": task_id}
    else:
        # 失败 stub（仅当无既有 report 时写入，避免覆盖证据）
        if not _existing_report:
            report_path.write_text(
                f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
                f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
            )
        # 失败：读 retry 计数，保留 .done 文件供 engine 下次 check
        max_retry_cap = _load_retry_cap(
            phases_file,
            phase_id=cur_phase,
            default=getattr(cfg, "DEFAULT_RETRY", 3),
        )

        retry = 0
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line or not _line.startswith("{"):
                            continue
                        phase = json.loads(_line)
                        if "schema_version" in phase:
                            continue
                        if phase.get("phase") == cur_phase:
                            retry = phase.get("retry", 0)
                            break
        except (json.JSONDecodeError, OSError) as e:
            _log.warning("read retry count failed for %s: %s", task_id, e)

        retry += 1
        # 更新 phases.json 当前 phase 的 retry 计数
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                updated = False
                for i, _line in enumerate(lines):
                    _ls = _line.strip()
                    if not _ls or not _ls.startswith("{"):
                        continue
                    try:
                        phase = json.loads(_ls)
                        if "schema_version" in phase:
                            continue
                        if phase.get("phase") != cur_phase:
                            continue
                        phase["retry"] = retry
                        lines[i] = json.dumps(phase, ensure_ascii=False)
                        updated = True
                        break
                    except json.JSONDecodeError as e:
                        _log.warning(
                            "update retry JSON parse failed for %s: %s", task_id, e
                        )
                if updated:
                    _store_atomic_write(
                        phases_file, "\n".join(lines) + ("\n" if lines else "")
                    )
        except OSError as e:
            _log.warning("write retry count failed for %s: %s", task_id, e)

        if retry >= max_retry_cap:
            # 重试耗尽：清理标记 + 异常隔离
            for p in marker_files:
                try:
                    p.unlink()
                except OSError as e:
                    _log.warning("quarantine marker unlink failed %s: %s", p, e)
            # v0.24: 标记 phase failed + 触发失败传染链路
            _mark_phase_failed(task_id, phase_id=cur_phase)
            failure_summary = _check_phase_failures(task_id)
            # v0.31 (P0.1): phase 图无法解析 → abnormal 标记
            if failure_summary.get("unresolvable"):
                _move_task_to_abnormal_if_all_terminal_failed(task_id)
                _quarantine(
                    task_id,
                    f"engine: phase 图无法解析"
                    f"(blocked={failure_summary.get('blocked')}) → abnormal",
                )
                _log.error(
                    "[engine] %s retry=%d >= %d, phase graph unresolvable → abnormal",
                    task_id, retry, max_retry_cap,
                )
                return {"status": "quarantined", "task_id": task_id}
            if failure_summary.get("all_failed_or_skipped"):
                _move_task_to_abnormal_if_all_terminal_failed(task_id)
                _quarantine(
                    task_id,
                    f"engine: 重试{max_retry_cap}次全部失败，"
                    f"下游 phase {failure_summary['skipped']} 自动跳过 → abnormal",
                )
            else:
                _quarantine(task_id, f"engine: 重试{max_retry_cap}次全部失败，隔离")
            _log.error(
                "[engine] %s retry=%d >= %d, quarantined (skipped_downstream=%d)",
                task_id,
                retry,
                max_retry_cap,
                failure_summary["skipped"],
            )
            return {"status": "quarantined", "task_id": task_id}

        # 失败但未耗尽：传播依赖链（上游 fail → 下游 skip），再让 engine relaunch
        fs = _check_phase_failures(task_id)
        if fs.get("unresolvable"):
            _log.warning(
                "[engine] %s phase 图无法解析但仍可重试，继续 retry "
                "(blocked=%s)", task_id, fs.get("blocked")
            )
        _log.info(
            "[engine] %s rc=%s retry %d/%d, timeout %ds",
            task_id,
            exit_code,
            retry,
            max_retry_cap,
            timeout_s,
        )
        return {"status": "failed", "task_id": task_id, "retry": retry}

