"""board.roles.product — extracted from ccc-board.py (behavior-preserving)."""
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
    _write_pass_verdict,
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


_GET_CODE_CONTEXT_TTL_S = 300.0
_get_code_context_cache: dict[str, tuple[str, float]] = {}

def _call_claude_for_plan(task: dict) -> tuple[str, list]:
    """调 Product Sessionful Contract Loop 生成 plan.md + phases.json。"""
    task_id = task["id"]
    plan_dir = get_workspace() / ".ccc" / "plans"
    ref_plans = ""
    if plan_dir.exists():
        plan_files = sorted(
            plan_dir.glob("*.plan.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for pf in plan_files[:2]:
            ref_plans += f"--- {pf.name} ---\n{pf.read_text()}\n\n"

    template_plan = _load_plan_template()
    profile_path = get_workspace() / ".ccc" / "profile.md"
    profile = profile_path.read_text() if profile_path.is_file() else "(no profile.md)"
    code_ctx = _get_code_context(get_workspace())

    def _load_product_skill() -> str:
        candidates = [
            CCC_HOME / "skills" / "ccc-product" / "SKILL.md",
            Path.home()
            / ".claude"
            / "skills"
            / "ccc-protocol"
            / "skills"
            / "ccc-product"
            / "SKILL.md",
        ]
        for p in candidates:
            try:
                if p.is_file():
                    return p.read_text(encoding="utf-8", errors="replace")[:6000]
            except OSError:
                continue
        return ""

    def _build_prompt(include_ref_plans: bool = True) -> str:
        ref = ref_plans if include_ref_plans else "（无，重试模式）"
        skill_text = _load_product_skill()
        skill_block = (
            f"## 角色 Skill（必须遵守）\n{skill_text}\n\n" if skill_text else ""
        )
        baseline_block = ""
        try:
            from _project_baseline import collect_baseline

            bl = collect_baseline(get_workspace())
            baseline_block = (
                f"## 项目基线（程序快照）\n{bl.get('summary', '')}\n"
                f"dirty_sample: {bl.get('git', {}).get('dirty_sample', [])[:15]}\n\n"
            )
        except Exception:
            pass
        return (
            f"你是 CCC 产品经理（product 步骤）。根据 skill + 基线生成 SPEC-合规 plan。\n"
            f"禁止写源码；每 phase 必须非空 scope；验收须含意图+可执行命令。\n"
            f"**工作目录硬门**：workspace=`{get_workspace().resolve()}`；"
            f"plan/phases 的所有路径必须落在该目录下。\n"
            f"硬门：plan 必须含独立二级标题 `## 验收` 或 `## 验证`。\n\n"
            f"{skill_block}"
            f"{baseline_block}"
            f"## 项目概况\n{profile[:1500]}\n\n"
            f"## 当前代码状态\n{code_ctx[:3000] if code_ctx else '（无代码上下文）'}\n\n"
            f"## 任务\n"
            f"- id: {task['id']}\n"
            f"- title: {_sanitize_prompt_input(task.get('title', ''))}\n"
            f"- description: {_sanitize_prompt_input(task.get('description', ''))}\n\n"
            f"## Plan 格式（严格按此结构）\n{template_plan}\n\n"
            f"## Phases 格式\n"
            f"每行一个 JSON object，必须含 description 与非空 scope。\n\n"
            f"## Phase 数上限：最多 {_get_cfg().max_phases} 个。\n\n"
            f"## 参考历史 plan\n{ref}\n\n"
            f"## 输出要求\n"
            f"---PLAN---\n（plan.md 完整内容）\n---END_PLAN---\n"
            f"---PHASES---\n（phases JSONL，每行一个 phase JSON）\n---END_PHASES---\n"
        )

    prompt = _build_prompt(True)
    try:
        from _lessons import get_recent_lessons

        recent = get_recent_lessons(get_workspace())
        if recent:
            lessons_text = "\n".join(
                f"- [{lesson.get('task_id', '?')}] phase={lesson.get('phase')}: "
                f"{lesson.get('error', '')[:100]}"
                for lesson in recent[:20]
                if not lesson.get("fixed")
            )
            if lessons_text:
                prompt += f"\n\n## 近期教训（参考，避免重复）\n{lessons_text}"
    except ImportError:
        pass

    from _product_session import (
        format_work_artifacts,
        parse_work_artifacts,
        run_contract_loop_sync,
    )

    def _validate(text: str) -> None:
        parse_work_artifacts(text)

    def _gate(text: str):
        plan, phases = parse_work_artifacts(text)
        plan, phases = _gate_product_artifacts(
            plan, phases, log_prefix="[product-session]"
        )
        max_phases = _get_cfg().max_phases
        if len(phases) > max_phases:
            raise RuntimeError(f"phase 数 {len(phases)} 超过上限 {max_phases}")
        return format_work_artifacts(plan, phases), (plan, phases)

    result = run_contract_loop_sync(
        prompt=prompt,
        workspace=get_workspace(),
        task_id=task_id,
        mode="work",
        model="flash",
        validate_fn=_validate,
        gate_fn=_gate,
    )
    if not result.get("ok"):
        fallback_dir = get_workspace() / ".ccc" / "product_fallback"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        (fallback_dir / f"{task_id}.last.out").write_text(
            result.get("output") or "", encoding="utf-8"
        )
        (fallback_dir / f"{task_id}.failed").write_text(
            (result.get("error") or "session failed") + "\n", encoding="utf-8"
        )
        raise RuntimeError(result.get("error") or "product session failed")
    plan, phases = parse_work_artifacts(result["output"])
    return plan, phases


def _generate_fallback_plan(task: dict) -> str:
    """API 不可用时生成 fallback plan"""
    return (
        f"# {task['id']}\n\n"
        f"> 此 plan 由 fallback 自动生成（product API 不可用）\n\n"
        f"## 目标\n"
        f"- {task.get('title', task['id'])}\n"
        f"- {task.get('description', '请手动补充详细描述')}\n\n"
        f"## 文件白名单\n"
        f"- （待补充）\n\n"
        f"## 验收\n"
        f"1. 完成任务目标\n"
        f"2. 相关测试通过\n"
    )


def _generate_fallback_phases() -> list:
    """API 不可用时生成 fallback phases（单 phase）"""
    return [
        {
            "phase": 1,
            "status": "pending",
            "description": "fallback — 待人工补全 scope",
            "scope": [],
            "subtasks": {"1.1": "pending"},
            "timeout": 300,
            "commit": None,
            "notes": "fallback",
        }
    ]


def _annotate_plan_git_warn(plan_content: str) -> str:
    """软探针：workspace 无 git 时在 plan 末尾记 WARN，不阻断。"""
    try:
        ws = get_workspace()
        if (ws / ".git").exists():
            return plan_content
    except Exception:
        return plan_content
    marker = "WARN: workspace 无 git"
    if marker in plan_content:
        return plan_content
    return plan_content.rstrip() + f"\n\n> {marker}，基线探针跳过（不阻断）\n"


def _gate_product_artifacts(
    plan_content: str, phases: list, *, log_prefix: str = "[product]"
) -> tuple[str, list]:
    """v0.42 硬门禁：phase_lint + plan 验收；通过后附软 git WARN。失败 raise RuntimeError。"""
    _lint_valid, _lint_errors, _lint_warnings = phase_lint.validate_phases_dict(phases)
    if not _lint_valid:
        raise RuntimeError(f"phase_lint failed: {'; '.join(_lint_errors)}")
    _dep_valid, _dep_errors = phase_lint.suggest_fix_no_missing_dependencies(phases)
    if not _dep_valid:
        raise RuntimeError(f"phase_lint orphan-dep: {'; '.join(_dep_errors)}")
    _cycle_valid, _cycle_errors = phase_lint.validate_no_cycle_dependencies(phases)
    if not _cycle_valid:
        raise RuntimeError(f"phase_lint cycle: {'; '.join(_cycle_errors)}")
    # 先规范化 ### 验收 → ## 验收，再 lint；写入磁盘用规范化后正文
    plan_content = phase_lint.normalize_plan_acceptance_headers(plan_content)
    _plan_ok, _plan_errs = phase_lint.validate_plan_acceptance(plan_content)
    if not _plan_ok:
        raise RuntimeError(f"plan_lint failed: {'; '.join(_plan_errs)}")
    if _lint_warnings:
        _log.warning("%s phase_lint warnings: %s", log_prefix, _lint_warnings)
    return _annotate_plan_git_warn(plan_content), phases


def product_role(task_id: str = "") -> dict:
    """产品经理：扫 backlog，或 --promote 调 Claude API 写 SPEC-合规 plan"""
    from _role_lock import assert_role_executor

    assert_role_executor("product", "claude-code")
    tasks = list_tasks("backlog")

    if task_id:
        task_id = sanitize_id(task_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            _log.error("backlog 中未找到 task '%s'", task_id)
            return {
                "role": "product",
                "error": f"task '{task_id}' not found",
                "counts": update_index(),
            }

        from _board_store import normalize_task_view
        from _product_fanout import apply_fanout, build_fanout_prompt, parse_fanout_output

        task = normalize_task_view(task, column="backlog")
        # ── Epic：Claude 扇出子卡，父卡留 backlog ──
        if task.get("card_kind") != "work":
            _log.info("正在扇出 epic %s（Claude → N 张 work）...", task_id)
            product_lock = get_workspace() / ".ccc" / ".product_role.lock"
            product_lock.parent.mkdir(parents=True, exist_ok=True)
            try:
                _acquire_product_lock(product_lock)
            except Exception as exc:
                return {"role": "product", "error": f"lock: {exc}"}
            try:
                profile_path = get_workspace() / ".ccc" / "profile.md"
                profile = (
                    profile_path.read_text()
                    if profile_path.is_file()
                    else "(no profile.md)"
                )
                prompt = build_fanout_prompt(
                    epic=task,
                    workspace=get_workspace(),
                    profile=profile,
                    code_ctx=_get_code_context(get_workspace()) or "",
                    template_plan=_load_plan_template(),
                    ref_plans="",
                    max_phases=_get_cfg().max_phases,
                )
                from _product_session import run_contract_loop_sync

                def _validate_epic(text: str) -> None:
                    parse_fanout_output(text)

                def _gate_epic(text: str):
                    brief, children = parse_fanout_output(text)
                    return text, (brief, children)

                sess = run_contract_loop_sync(
                    prompt=prompt,
                    workspace=get_workspace(),
                    task_id=task_id,
                    mode="epic",
                    model="flash",
                    validate_fn=_validate_epic,
                    gate_fn=_gate_epic,
                )
                if not sess.get("ok"):
                    return {
                        "role": "product",
                        "error": sess.get("error") or "epic session failed",
                        "task_id": task_id,
                    }
                brief, children = parse_fanout_output(sess.get("output") or "")
                fr = apply_fanout(
                    store,
                    task,
                    children_raw=children,
                    epic_brief=brief,
                    max_phases=_get_cfg().max_phases,
                )
                if not fr.get("ok"):
                    return {
                        "role": "product",
                        "error": fr.get("error") or "fanout failed",
                        "task_id": task_id,
                    }
                return {
                    "role": "product",
                    "fanout": True,
                    "epic": task_id,
                    "child_ids": fr.get("child_ids"),
                    "counts": update_index(),
                }
            except Exception as exc:
                _log.error("epic fanout failed: %s", exc)
                return {
                    "role": "product",
                    "error": str(exc),
                    "task_id": task_id,
                }
            finally:
                _release_product_lock(product_lock)

        # ── 兼容 work：单卡 plan+phases → planned ──
        _log.info("正在拆解 work %s（单卡 plan）...", task_id)
        plan_content = None
        phases = None
        fallback = False
        try:
            plan_content, phases = _call_claude_for_plan(task)
        except RuntimeError as e:
            err_msg = str(e)
            if "phase_lint" in err_msg or "plan_lint" in err_msg:
                _log.error("product 硬门禁失败: %s", e)
                return {
                    "role": "product",
                    "error": err_msg,
                    "task_id": task_id,
                    "lint_blocked": True,
                }
            _log.error("API 调用失败: %s", e)
            return {
                "role": "product",
                "error": f"work promote failed: {e}",
                "task_id": task_id,
            }

        product_lock = get_workspace() / ".ccc" / ".product_role.lock"
        product_lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            _acquire_product_lock(product_lock)
        except Exception as exc:
            return {"role": "product", "error": f"lock acquire failed: {exc}"}

        try:
            _write_async_product_result(task_id, plan_content, phases)
        finally:
            _release_product_lock(product_lock)

        return {
            "role": "product",
            "promoted": task_id,
            "fallback": fallback,
            "fanout": False,
            "counts": update_index(),
        }

    report = {
        "backlog_count": len(tasks),
        "tasks": [{"id": t["id"], "title": t.get("title", "")} for t in tasks],
        "message": "待办是收件箱。使用 --promote <task_id> 拆解。",
    }
    if tasks:
        _log.info("backlog 有 %d 个待处理:", len(tasks))
        for t in tasks:
            _log.info("  • %s: %s", t["id"], t.get("title", "?"))
        _log.info("提示: 使用 --promote <task_id> 拆解")
    else:
        _log.info("backlog 空")
    return {"role": "product", "report": report, "counts": update_index()}


def launch_product_async(task_id: str) -> dict:
    """异步启动 product Sessionful Contract Loop。

    写 prompt 后 Popen ccc-product-session.py（非 claude -p），
    不在引擎 tick 内阻塞。后续由 check_product_async() 检查结果。

    Returns: {"ok": True, "pid": int} 或 {"error": str}
    """
    from _role_lock import assert_role_executor

    assert_role_executor("product", "claude-code")
    task_id = sanitize_id(task_id)
    tasks = list_tasks("backlog")
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return {"error": f"task '{task_id}' not found in backlog"}

    from _board_store import normalize_task_view

    task = normalize_task_view(task, column="backlog")
    if task.get("card_kind") == "epic" and task.get("split_status") == "active":
        kids = task.get("child_ids") or []
        if kids:
            return {"error": f"epic '{task_id}' already split ({len(kids)} children)"}

    pids_dir = get_workspace() / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build prompt
    ref_plans = ""
    plan_dir_obj = get_workspace() / ".ccc" / "plans"
    if plan_dir_obj.exists():
        plan_files = sorted(
            plan_dir_obj.glob("*.plan.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for pf in plan_files[:2]:
            ref_plans += f"--- {pf.name} ---\n{pf.read_text()}\n\n"

    template_plan = _load_plan_template()
    profile_path = get_workspace() / ".ccc" / "profile.md"
    profile = profile_path.read_text() if profile_path.is_file() else "(no profile.md)"
    code_ctx = _get_code_context(get_workspace())

    if task.get("card_kind") != "work":
        from _product_fanout import build_fanout_prompt

        prompt = build_fanout_prompt(
            epic=task,
            workspace=get_workspace(),
            profile=profile,
            code_ctx=code_ctx or "",
            template_plan=template_plan,
            ref_plans=ref_plans,
            max_phases=_get_cfg().max_phases,
        )
    else:
        # 兼容：显式 work 小卡仍走单卡 PLAN/PHASES → planned
        prompt = (
            f"你是 CCC 产品经理。根据以下信息生成 SPEC-合规的执行 plan。\n\n"
            f"## 项目概况\n{profile[:1500]}\n\n"
            f"## 当前代码状态\n{code_ctx[:3000] if code_ctx else '（无代码上下文）'}\n\n"
            f"## 任务\n"
            f"- id: {task['id']}\n"
            f"- title: {_sanitize_prompt_input(task.get('title', ''))}\n"
            f"- description: {_sanitize_prompt_input(task.get('description', ''))}\n\n"
            f"## Plan 格式（严格按此结构）\n{template_plan}\n\n"
            f"## Phases 格式\n"
            f"每行一个 JSON object，必须含 description 与非空 scope。\n\n"
            f"## 输出要求\n"
            f"---PLAN---\n（plan.md）\n---END_PLAN---\n"
            f"---PHASES---\n（phases JSONL）\n---END_PHASES---\n"
        )

    # 2. 注入 lessons 上下文
    try:
        from _lessons import get_recent_lessons

        recent = get_recent_lessons(get_workspace())
        if recent:
            lessons_text = "\n".join(
                f"- [{lesson.get('task_id', '?')}] phase={lesson.get('phase')}: {lesson.get('error', '')[:100]}"
                for lesson in recent[:20]
                if not lesson.get("fixed")
            )
            if lessons_text:
                prompt += f"\n\n## 近期教训（参考，避免重复）\n{lessons_text}"
    except ImportError:
        pass

    # 3. 写 prompt 文件
    prompt_file = pids_dir / f"{task_id}.product.prompt.md"
    prompt_file.write_text(prompt)

    # 4. 清理残留标记
    for sfx in [".product.out", ".product.done", ".product.pid", ".product.exitcode"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass

    # 5. Popen product session runner（Sessionful Contract Loop，非 claude -p）
    result_file = pids_dir / f"{task_id}.product.out"
    err_file = pids_dir / f"{task_id}.product.err"
    relay_url = _get_relay_url()
    env = _claude_env(relay_url=relay_url)

    runner = CCC_HOME / "scripts" / "ccc-product-session.py"
    hub_py = CCC_HOME / ".venv-hub" / "bin" / "python"
    py = str(hub_py) if hub_py.is_file() else sys.executable
    mode = "epic" if task.get("card_kind") != "work" else "work"
    cmd = [
        py,
        str(runner),
        "--workspace",
        str(get_workspace()),
        "--task-id",
        task_id,
        "--prompt-file",
        str(prompt_file),
        "--mode",
        mode,
        "--model",
        "flash",
        "--out-file",
        str(result_file),
        "--err-file",
        str(err_file),
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
            cwd=str(get_workspace()),
        )
        pids_dir.joinpath(f"{task_id}.product.pid").write_text(str(proc.pid))
        _log.info(
            "[product-async] %s session-loop launched PID=%d py=%s mode=%s",
            task_id,
            proc.pid,
            py,
            mode,
        )
        return {"ok": True, "pid": proc.pid, "runner": "product-session"}
    except ClaudeCliMissing as exc:
        _log.error("[product-async] %s claude missing: %s", task_id, exc)
        return {"error": str(exc)}
    except Exception as exc:
        _log.error("[product-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def check_product_async(task_id: str) -> dict:
    """检查异步 product_role 是否完成。

    Returns:
        {"status": "running"} — 仍在跑
        {"status": "success"} — 完成，已写 plan+phases 并移 backlog→planned
        {"status": "failed", "error": str} — 失败
    """
    task_id = sanitize_id(task_id)
    pids_dir = get_workspace() / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.product.done"
    result_file = pids_dir / f"{task_id}.product.out"
    pid_file = pids_dir / f"{task_id}.product.pid"
    prompt_file = pids_dir / f"{task_id}.product.prompt.md"

    # 检查完成标记
    if not done_file.exists():
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                # v0.37: 墙钟超时 — 防止 claude -p 无限挂起吃内存
                _timeout = int(getattr(cfg, "product_async_timeout", 600) or 600)
                try:
                    _age = time.time() - pid_file.stat().st_mtime
                except OSError:
                    _age = 0
                if _age > _timeout:
                    _log.warning(
                        "[product-async] %s PID=%s 超时 %.0fs > %ds，强杀",
                        task_id,
                        pid,
                        _age,
                        _timeout,
                    )
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                    except (ProcessLookupError, PermissionError, OSError):
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError, OSError):
                            pass
                    for sfx in [
                        ".product.pid",
                        ".product.out",
                        ".product.done",
                        ".product.exitcode",
                        ".product.prompt.md",
                    ]:
                        try:
                            (pids_dir / f"{task_id}{sfx}").unlink()
                        except OSError:
                            pass
                    return {
                        "status": "failed",
                        "error": f"product async timeout after {_timeout}s",
                    }

                # v0.29.35: 检测 zombie 进程（STAT=Z）→ 视为已退出
                _zombie = False
                try:
                    _ps = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "state="],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        env=_sanitized_env(),
                    )
                    if _ps.stdout.strip() == "Z":
                        _zombie = True
                except Exception:
                    pass

                if not _zombie:
                    os.kill(pid, 0)
                else:
                    # 回收 zombie 进程表条目，然后视为已退出
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except (ChildProcessError, OSError):
                        pass
                    raise ProcessLookupError(f"zombie pid {pid}")
            except (ValueError, ProcessLookupError):
                # 进程已退出 — 检查输出文件是否有内容
                if result_file.exists() and result_file.stat().st_size > 0:
                    output = result_file.read_text()
                    return _parse_and_finalize_product(task_id, output, pids_dir)
                pass
            except OSError:
                pass
            else:
                return {"status": "running"}
        return {"status": "failed", "error": "process not running"}

    # 读输出（stdout + stderr；鉴权失败常在其一）
    output = result_file.read_text() if result_file.exists() else ""
    err_file = pids_dir / f"{task_id}.product.err"
    if err_file.exists():
        try:
            err = err_file.read_text()
            if err.strip():
                sep = "\n" if output else ""
                output = (output or "") + sep + err
        except OSError:
            pass
    return _parse_and_finalize_product(task_id, output, pids_dir)


def _parse_and_finalize_product(task_id: str, output: str, pids_dir: Path) -> dict:
    """解析 product 输出：epic → 扇出子卡；work → 旧单卡 move planned。"""
    import re as _re

    from _board_store import normalize_task_view
    from _product_fanout import apply_fanout, parse_fanout_output

    _out = output or ""
    _auth = (
        "Not logged in" in _out
        or "Please run /login" in _out
        or "not logged in" in _out.lower()
    )

    def _fail(err: str, *, fatal: bool = False) -> dict:
        try:
            fb = get_workspace() / ".ccc" / "product_fallback"
            fb.mkdir(parents=True, exist_ok=True)
            (fb / f"{task_id}.last.out").write_text(_out, encoding="utf-8")
            (fb / f"{task_id}.failed").write_text(err + "\n", encoding="utf-8")
        except OSError:
            pass
        _log.error("[product-async] %s %s", task_id, err)
        _cleanup_async_product_markers(pids_dir, task_id)
        return {"status": "failed", "error": err, "fatal": fatal or _auth}

    backlog = list_tasks("backlog")
    task = next((t for t in backlog if t["id"] == task_id), None)
    if not task:
        return _fail("task not in backlog")
    task = normalize_task_view(task, column="backlog")

    # ── Epic 扇出路径（主路径）──
    if task.get("card_kind") != "work":
        try:
            brief, children = parse_fanout_output(_out)
        except (ValueError, json.JSONDecodeError) as exc:
            if _auth:
                return _fail(
                    "auth: claude CLI rejected request "
                    "(check ANTHROPIC_AUTH_TOKEN/API_KEY reach subprocess)",
                    fatal=True,
                )
            return _fail(f"fanout parse failed: {exc}")
        try:
            result = apply_fanout(
                store,
                task,
                children_raw=children,
                epic_brief=brief,
                max_phases=_get_cfg().max_phases,
            )
        except Exception as exc:
            return _fail(f"fanout apply failed: {exc}")
        if not result.get("ok"):
            return _fail(result.get("error") or "fanout failed")
        _cleanup_async_product_markers(pids_dir, task_id)
        update_index()
        _log.info(
            "[product-async] %s ✓ fanout %d children color=%s",
            task_id,
            len(result.get("child_ids") or []),
            result.get("color_group"),
        )
        return {
            "status": "success",
            "fanout": True,
            "child_ids": result.get("child_ids"),
        }

    # ── 兼容：work 单卡 PLAN/PHASES ──
    plan_match = _re.search(
        r"---PLAN---\s*\n?(.*?)\n?---END_PLAN---", _out, _re.DOTALL
    )
    phases_match = _re.search(
        r"---PHASES---\s*\n?(.*?)\n?---END_PHASES---", _out, _re.DOTALL
    )
    if not plan_match or not phases_match:
        return _fail(
            "auth: claude CLI rejected request "
            "(check ANTHROPIC_AUTH_TOKEN/API_KEY reach subprocess)"
            if _auth
            else "output parse failed",
            fatal=_auth,
        )

    plan_content = plan_match.group(1).strip()
    phases_data = []
    for line in phases_match.group(1).strip().split("\n"):
        line = line.strip()
        if line:
            try:
                phases_data.append(json.loads(line))
            except json.JSONDecodeError as exc:
                return _fail(f"phases JSON parse: {exc}")

    if len(phases_data) > _get_cfg().max_phases:
        return _fail(f"phases > max {_get_cfg().max_phases}")

    try:
        plan_content, phases_data = _gate_product_artifacts(
            plan_content, phases_data, log_prefix="[product-async]"
        )
    except RuntimeError as exc:
        return _fail(str(exc))

    _write_async_product_result(task_id, plan_content, phases_data)
    _cleanup_async_product_markers(pids_dir, task_id)
    _log.info("[product-async] %s ✓ work card plan+phases → planned", task_id)
    return {"status": "success", "fanout": False}


def _cleanup_async_product_markers(pids_dir: Path, task_id: str) -> None:
    """清理 product_role 异步标记文件"""
    for sfx in [".product.out", ".product.done", ".product.pid", ".product.prompt.md"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass




def _infer_complexity_from_plan(plan_content: str) -> str:
    """v0.28.1 / v0.38: 根据 plan 内容推断 complexity（small/medium/large）。"""
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
            if line.strip().startswith("##")
            and " " in line
            and line.strip() != "##"
        ]
    )
    plan_weight = plan_size + file_mentions * 20 + section_count * 10
    if plan_weight <= 50:
        return "small"
    if plan_weight <= 200:
        return "medium"
    return "large"


def _write_async_product_result(
    task_id: str, plan_content: str, phases_data: list
) -> None:
    """写 plan + phases 文件 + 移 backlog → planned（无锁，engine 单线程保证互斥）"""
    plan_dir = get_workspace() / ".ccc" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    phases_dir = get_workspace() / ".ccc" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)

    phases_tmp = phases_dir / f".{task_id}.phases.tmp"
    phases_content = (
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases_data)
        + "\n"
    )
    phases_tmp.write_text(phases_content)
    phases_tmp.rename(phases_dir / f"{task_id}.phases.json")

    plan_tmp = plan_dir / f".{task_id}.plan.tmp"
    plan_tmp.write_text(plan_content)
    plan_tmp.rename(plan_dir / f"{task_id}.plan.md")

    move_task(task_id, "backlog", "planned")

    # v0.38: 写入 complexity（与 sync product_role 对齐）
    try:
        task_file = get_workspace() / ".ccc" / "board" / "planned" / f"{task_id}.jsonl"
        if task_file.exists():
            task_data = json.loads(task_file.read_text())
            complexity = _infer_complexity_from_plan(plan_content)
            task_data["complexity"] = complexity
            task_file.write_text(json.dumps(task_data, ensure_ascii=False) + "\n")
            _log.info("[product-async] %s complexity=%s", task_id, complexity)
    except Exception as exc:
        _log.warning("[product-async] %s complexity assign failed: %s", task_id, exc)


def _get_code_context(ws_path: Path) -> str:
    """动态获取代码上下文：文件树 + 入口文件 + 近期 git 日志

    v0.23 新增：用于注入 product 角色的 plan 生成 prompt。
    设计原则：轻量（<5KB）、聚焦结构概览、不深入实现细节。

    修复 v0.23 对抗性审查问题：
    - A2: 截断确保代码块闭合（不截断代码块内容）
    - A3: 删除冗余 subprocess import（全局已导入）
    - A5: 入口文件过滤增强（排除 vendor/build/tests）
    - A6: 添加简单缓存（模块级字典）
    - A7: 入口文件过滤跳过 symlink（用 is_symlink 检查，3.9 兼容）
    """
    parts = []
    ws = str(ws_path)

    # v0.28.0 (M-002): 模块级缓存 + 300s TTL，过期重算
    cache_key = str(ws_path)
    cached = _get_code_context_cache.get(cache_key)
    if cached is not None:
        result, ts = cached
        if time.monotonic() - ts < _GET_CODE_CONTEXT_TTL_S:
            return result
        # 过期 → 删旧条目，重新计算
        _get_code_context_cache.pop(cache_key, None)

    # A3: 使用全局 subprocess（文件顶部已导入）

    # 1. 代码文件树（Python + TypeScript + 配置）
    try:
        tree = subprocess.run(
            [
                "find",
                ".",
                "(",
                "-name",
                "*.py",
                "-o",
                "-name",
                "*.ts",
                "-o",
                "-name",
                "*.tsx",
                "-o",
                "-name",
                "*.js",
                "-o",
                "-name",
                "*.jsx",
                "-o",
                "-name",
                "*.json",
                "-o",
                "-name",
                "*.yaml",
                "-o",
                "-name",
                "*.yml",
                ")",
                "-not",
                "-path",
                "./node_modules/*",
                "-not",
                "-path",
                "./.venv/*",
                "-not",
                "-path",
                "./__pycache__/*",
                "-not",
                "-path",
                "./.git/*",
                "-not",
                "-path",
                "./.ccc/*",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ws,
            env=_sanitized_env(),
        )
        if tree.returncode == 0:
            lines = tree.stdout.strip().split("\n")
            label = f"{len(lines)} 个源文件"
            if len(lines) > 80:
                label += "，已截断前 80 行"
            shown = lines[:80]
            parts.append(
                f"## 代码文件树（{label}）\n```\n" + "\n".join(shown) + "\n```"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("audit context tree failed for %s: %s", ws, e)
    try:
        git_log = subprocess.run(
            ["git", "log", "--oneline", "-20", "--no-decorate"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=ws,
            env=_sanitized_env(),
        )
        if git_log.returncode == 0 and git_log.stdout.strip():
            parts.append("## 近期 git 提交\n```\n" + git_log.stdout.strip() + "\n```")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("audit context git log failed for %s: %s", ws, e)
    exclude_patterns = [
        ".venv",
        "node_modules",
        ".ccc",
        "__pycache__",
        "vendor",
        "build",
        "/tests/",
    ]
    for entry_pattern in [
        "main.py",
        "app.py",
        "server.py",
        "cli.py",
        "index.ts",
        "index.js",
    ]:
        if len([p for p in parts if p.startswith("## 入口文件")]) >= 2:
            break
        # A7 兼容 3.9：rglob 不带 follow_symlinks（Python 3.13+ 才支持），用 is_symlink 过滤
        entries = sorted(p for p in ws_path.rglob(entry_pattern) if not p.is_symlink())
        for ef in entries:
            if len([p for p in parts if p.startswith("## 入口文件")]) >= 2:
                break
            try:
                rel = ef.relative_to(ws_path)
                rel_str = str(rel)
                # A5: 增强过滤（排除 tests/ 目录下的入口文件）
                if any(pattern in rel_str for pattern in exclude_patterns):
                    continue
                # 不截断，入口文件内容通常较小
                content = ef.read_text()[:2000]
                parts.append(f"## 入口文件 {rel}\n```\n{content}\n```")
            except (OSError, ValueError):
                continue

    # A6: 写入缓存
    result = "\n\n".join(parts)
    # v0.28.0 (M-002): 加 300s TTL，避免 product_role 多次调用时拿到陈旧快照
    _get_code_context_cache[str(ws_path)] = (result, time.monotonic())
    return result


def _load_plan_template(ws: Path | None = None) -> str:
    """加载 plan 模板；workspace 缺失时回退 CCC 仓库 templates/。"""
    ws = ws or get_workspace()
    candidates = [
        ws / "templates" / "plan.plan.md",
        CCC_HOME / "templates" / "plan.plan.md",
        Path(__file__).resolve().parent.parent / "templates" / "plan.plan.md",
    ]
    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"plan template not found in {[str(c) for c in candidates]}"
    )

