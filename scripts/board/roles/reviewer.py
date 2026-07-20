"""board.roles.reviewer — extracted from ccc-board.py (behavior-preserving)."""
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
    _write_pass_verdict,
)



REVIEW_SIZE_SMALL_MAX = 10
REVIEW_SIZE_MEDIUM_MAX = 50

def _reviewer_fallback_mode() -> str:
    """CCC_REVIEWER_FALLBACK=quarantine|stay|static（默认 quarantine）。

    quarantine: Verdict=FALLBACK → abnormal（默认；禁止假 PASS）
    stay: Verdict=FALLBACK，留 testing（不进 verified）
    static: 已废弃别名 → 等同 stay（绝不写 PASS / 绝不挪 verified）
    """
    mode = (os.environ.get("CCC_REVIEWER_FALLBACK") or "quarantine").strip().lower()
    if mode == "static":
        return "stay"
    return mode if mode in ("quarantine", "stay") else "quarantine"


def _apply_reviewer_llm_fallback(
    task_id: str,
    size_class: str,
    reason_detail: str,
    *,
    verdict_path: Path,
    review_md: Path | None = None,
) -> bool:
    """处理 medium/large LLM fallback。

    返回 True 仅表示「已移 verified」——当前策略下永远为 False
    （FALLBACK 禁止写成 PASS，禁止静默过门）。
    """
    mode = _reviewer_fallback_mode()
    detail = reason_detail or "unknown"
    warn = (
        f"FALLBACK/{size_class}: LLM unavailable ({detail}); "
        f"mode={mode} (CCC_REVIEWER_FALLBACK)"
    )
    verdict_path.write_text(
        f"# {task_id} Verdict\n\n"
        f"**Verdict:** FALLBACK\n\n"
        f"**Warn:** {warn}\n\n"
        f"{detail}\n",
        encoding="utf-8",
    )
    if review_md is not None:
        review_md.write_text(
            f"# {task_id} Review\n\n"
            f"## Verdict: **FALLBACK**\n\n"
            f"## Size Class: **{size_class}**\n\n"
            f"{warn}\n",
            encoding="utf-8",
        )

    if mode == "stay":
        try:
            from _failure_ledger import record_failure

            record_failure(
                get_workspace(),
                task_id=task_id,
                role="reviewer",
                reason=f"fallback_stay: {detail}",
                from_col="testing",
                to_col="testing",
                related_stats_event="reviewer_fallback_stay",
            )
        except Exception:
            pass
        _log.warning(
            "[reviewer] %s ⚠ %s-class fallback → stay testing: %s",
            task_id,
            size_class,
            detail,
        )
        return False

    reason = (
        f"v0.40.1 fallback quarantine: {size_class}-class LLM 不可用，"
        f"reason={detail}；FALLBACK≠PASS，强制人工介入"
    )
    _quarantine(task_id, reason=reason)
    _log.error(
        "[reviewer] %s ✗ %s-class fallback quarantine: %s",
        task_id,
        size_class,
        detail,
    )
    try:
        from _failure_ledger import record_failure

        record_failure(
            get_workspace(),
            task_id=task_id,
            role="reviewer",
            reason=f"fallback_quarantine: {detail}",
            from_col="testing",
            to_col="abnormal",
            related_stats_event="reviewer_fallback_quarantine",
        )
    except Exception:
        pass
    try:
        subprocess.run(
            [
                "bash",
                str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                "L2",
                f"reviewer fallback quarantine: {task_id} ({size_class})",
                reason[:200],
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass
    return False


def _get_git_diff_for_task(ws: Path, task_id: str) -> tuple[str, str]:
    """获取 task 的 git diff stat 和 full diff。

    Returns: (diff_stat, full_diff)
    """
    import subprocess as _sp

    try:
        stat_r = _sp.run(
            [
                "git",
                "log",
                "--all",
                "--oneline",
                "--grep",
                task_id,
                "--format=%H",
                "--max-count=1",
            ],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
        )
        merge_base = stat_r.stdout.strip()
        if not merge_base:
            # fallback: 从头查
            merge_base = "HEAD"
        # diff stat
        ds = _sp.run(
            ["git", "diff", f"{merge_base}..HEAD", "--stat"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=10,
        )
        fd = _sp.run(
            ["git", "diff", f"{merge_base}..HEAD"],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (ds.stdout.strip(), fd.stdout.strip())
    except Exception:
        return ("", "")


def launch_reviewer_async(task_id: str, ws: Path) -> dict:
    """异步启动 reviewer LLM 子进程。

    写 prompt 后 Popen claude -p，引擎下个 tick 用 check_reviewer_async() 检查。

    Returns: {"ok": True, "pid": int}
             {"status": "skip_small", "msg": "..."} — small 类直接 py_compile 通过
             {"error": str}
    """
    from _role_lock import assert_role_executor

    assert_role_executor("reviewer", "claude-code")
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取 task 信息
    tasks = list_tasks("testing")
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return {"error": f"task '{task_id}' not found in testing"}

    plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
    plan_text = plan_file.read_text() if plan_file.exists() else ""

    # 2. 获取 git diff
    diff_stat, full_diff = _get_git_diff_for_task(ws, task_id)

    # 3. 分类变更大小
    size_class, total_lines = _classify_review_size(diff_stat)
    if size_class == "unknown":
        return {"error": "diff stat 缺 summary 行，无法分级"}

    # small 类：跳过 LLM，直接 py_compile 静态检查（快速，不阻塞）
    if size_class == "small":
        files = _parse_plan_scope(task_id)
        if not files:
            files = [str(p) for p in (ws / "scripts").rglob("*.py")]
        import glob as _glob

        py_files = []
        for f in files:
            matched = _glob.glob(str(ws / f)) if "*" in f else [str(ws / f)]
            matched = [m for m in matched if _is_path_in_root(Path(m))]
            py_files.extend(matched)
        py_files = [f for f in py_files if f.endswith(".py") and Path(f).exists()]

        py_ok = True
        if py_files:
            py_ok = _py_compile_fallback(task_id, py_files)
        elif not full_diff.strip():
            return {"error": "small-class: 空 diff"}
        # small 类直接返回 pass（py_compile 已检查或无可检查项）
        # 写 review 报告
        report_dir = ws / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        review_md = report_dir / f"{task_id}.review.md"
        review_md.write_text(
            f"# {task_id} Review\n\n"
            f"## Verdict: **PASS**\n\n"
            f"## Size Class: **small** ({total_lines} 行)\n\n"
            f"v0.24.1: small 类变更跳过 LLM，仅 py_compile 静态检查通过。\n\n"
            f"## Files Checked ({len(py_files)} 条)\n\n"
            + "\n".join(f"- {Path(f).name}" for f in py_files)
        )
        # 写 verdict
        verdict_dir = ws / ".ccc" / "verdicts"
        verdict_dir.mkdir(parents=True, exist_ok=True)
        verdict_path = verdict_dir / f"{task_id}.verdict.md"
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n"
            f"**Verdict:** PASS\n\n"
            f"**Size Class:** small\n\n"
            f"py_compile static check passed\n"
        )
        return {"ok": True, "pid": 0, "status": "small_skip"}

    # 4. medium/large: 构建 LLM prompt
    impact_section = ""
    if size_class == "large":
        impact_section = (
            "## 重点检查（large 类变更，>50 行）\n"
            "6. **影响面分析**：列出本次改动触及的模块 + 上下游调用方 + 是否可能影响其他 task\n"
            "7. **风险等级**：评估本次改动风险（high/medium/low）并说明理由\n"
            "8. **回归路径**：列出需要复测的关键功能点（必须包含 plan 验收清单之外的隐性影响）\n\n"
        )

    skill_text = _load_reviewer_skill()
    skill_block = (
        f"## 角色 Skill（必须遵守）\n{skill_text}\n\n" if skill_text else ""
    )
    prompt = (
        "你是 CCC 资深代码审查员（reviewer 步骤）。按 skill + plan 验收清单逐条核对。\n\n"
        f"{skill_block}"
        "## Plan 验收清单\n"
        f"{plan_text[:12000]}\n\n"
        "## 改动概览 (git diff --stat)\n"
        f"```\n{diff_stat[:4000]}\n```\n\n"
        "## 改动详情 (git diff)\n"
        f"```\n{full_diff[:24000]}\n```\n\n"
        "## 审查清单（逐条核对）\n"
        "1. 数据流正确性（输入/输出/边界）\n"
        "2. 错误处理（异常/边界/资源泄漏）\n"
        "3. 安全（SQL 注入/路径遍历/凭据泄漏/危险函数）\n"
        "4. 命名与可读性\n"
        "5. 是否与 plan 验收清单一致\n\n"
        f"{impact_section}"
        "## 输出要求\n"
        "只输出 JSON，不要 markdown 代码块，不要附加解释。verdict 必须是小写字符串：\n"
        '{"verdict": "pass", '
        '"findings": [{"severity": "high", "file": "...", "line": 0, '
        '"issue": "...", "suggestion": "..."}], '
        '"summary": "..."}\n'
        '或 {"verdict": "fail", "findings": [...], "summary": "..."}\n'
        "即使缺少 findings 也必须有 verdict 字段。\n"
    )

    # 5. 写 prompt 文件
    prompt_file = pids_dir / f"{task_id}.reviewer.prompt.md"
    prompt_file.write_text(prompt)

    # 6. 清理残留标记
    for sfx in [".reviewer.out", ".reviewer.done", ".reviewer.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass

    # 7. Popen claude -p
    result_file = pids_dir / f"{task_id}.reviewer.out"
    relay_url = _get_relay_url()
    env = _claude_env(relay_url=relay_url)
    env["CLAUDE_CODE_NONINTERACTIVE"] = "1"

    try:
        with open(result_file, "w") as out_f, open(prompt_file, "r") as in_f:
            proc = subprocess.Popen(
                [_claude_bin(), "-p"],
                stdin=in_f,
                stdout=out_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=env,
            )
        pids_dir.joinpath(f"{task_id}.reviewer.pid").write_text(str(proc.pid))
        _log.info(
            "[reviewer-async] %s launched PID=%d size=%s", task_id, proc.pid, size_class
        )
        return {"ok": True, "pid": proc.pid, "size_class": size_class}
    except ClaudeCliMissing as exc:
        _log.error("[reviewer-async] %s claude missing: %s", task_id, exc)
        return {"error": str(exc)}
    except Exception as exc:
        _log.error("[reviewer-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def _parse_reviewer_output(task_id: str, output: str) -> dict:
    """解析 reviewer LLM 输出为 verdict 数据。"""
    import re as _re

    trimmed = output.strip()
    # 优先：直接 JSON
    if trimmed.startswith("{"):
        try:
            data = json.loads(trimmed)
            if data.get("verdict") in ("pass", "fail"):
                return data
        except json.JSONDecodeError:
            pass

    # 次优：markdown 代码块
    m = _re.search(r"```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```", output, _re.IGNORECASE)
    if not m:
        m = _re.search(r"(\{.*\})", output, _re.DOTALL)
    if not m:
        return {"verdict": "fallback", "reason": "no JSON in Claude output"}
    try:
        json_str = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
        json_str = json_str.strip()
        data = None
        for candidate in (
            json_str,
            _re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_str),
        ):
            try:
                data = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if data is None:
            return {"verdict": "fallback", "reason": "JSON parse failed"}
        verdict_raw = data.get("verdict")
        if isinstance(verdict_raw, str):
            verdict_norm = verdict_raw.strip().lower()
            if verdict_norm in ("pass", "fail"):
                data["verdict"] = verdict_norm
                return data
        # 容错：boolean true/false 或大写
        if verdict_raw is True:
            data["verdict"] = "pass"
            return data
        if verdict_raw is False:
            data["verdict"] = "fail"
            return data
        return {
            "verdict": "fallback",
            "reason": f"unexpected verdict: {repr(verdict_raw)[:100]}",
        }
    except json.JSONDecodeError as exc:
        return {"verdict": "fallback", "reason": f"JSON parse failed: {exc}"}


def check_reviewer_async(task_id: str, ws: Path) -> dict:
    """检查异步 reviewer 是否完成。

    Returns:
        {"status": "pass"} — verdict PASS，已写 review 报告
        {"status": "TIMEOUT"} — LLM timeout，engine 可重试
        {"status": "running"} — 仍在执行
        {"status": "failed", "reason": str} — 失败/quarantine
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.reviewer.done"
    result_file = pids_dir / f"{task_id}.reviewer.out"
    pid_file = pids_dir / f"{task_id}.reviewer.pid"

    # 检查是否完成
    is_done = done_file.exists()

    # 如果没 done 标记，检查进程是否还在跑
    if not is_done:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # 0 = 只检查存活
                return {"status": "running"}
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
        # 进程不在，判断为进程提前退出
        return {"status": "failed", "reason": "process exited before writing verdict"}

    # 读取输出
    output = result_file.read_text() if result_file.exists() else ""
    if not output.strip():
        return {"status": "failed", "reason": "empty reviewer output"}

    try:
        from _cost_telemetry import estimate_tokens, record_call

        record_call(
            role="reviewer",
            provider_or_model="claude",
            prompt_tokens=0,
            completion_tokens=estimate_tokens(output),
            latency_ms=0,
            ok=True,
            task_id=task_id,
            phase_id="reviewer",
        )
    except Exception:
        pass

    # 解析 verdict
    verdict_data = _parse_reviewer_output(task_id, output)
    verdict = verdict_data.get("verdict", "fallback")
    summary = verdict_data.get("summary", "")
    size_class = "unknown"

    # 写 review 报告
    report_dir = ws / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    review_md = report_dir / f"{task_id}.review.md"
    review_md.write_text(
        f"# {task_id} Review\n\n"
        f"## Verdict: **{verdict.upper()}**\n\n"
        f"{summary}\n\n"
        f"## Findings ({len(verdict_data.get('findings', []))} 条)\n\n"
        f"```json\n{json.dumps(verdict_data, ensure_ascii=False, indent=2)}\n```\n"
    )

    # 写 verdict 文件
    verdict_dir = ws / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = verdict_dir / f"{task_id}.verdict.md"

    fallback_reason = verdict_data.get("reason", "").lower()
    if "timeout" in fallback_reason:
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n"
            f"**Verdict:** TIMEOUT\n\n"
            f"**Reason:** {verdict_data.get('reason', 'unknown')}\n"
        )
        # 清理标记，让 engine 决定是否重试
        _cleanup_reviewer_markers(pids_dir, task_id)
        return {"status": "TIMEOUT", "reason": verdict_data.get("reason", "timeout")}

    if verdict == "pass":
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n**Verdict:** PASS\n\n{summary}\n"
        )
        _cleanup_reviewer_markers(pids_dir, task_id)
        return {"status": "pass"}

    if verdict == "fail":
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n**Verdict:** FAIL\n\n{summary}\n"
        )
        _cleanup_reviewer_markers(pids_dir, task_id)
        return {"status": "failed", "reason": "LLM verdict: fail"}

    # fallback：默认 quarantine；CCC_REVIEWER_FALLBACK=stay 则留 testing（绝不 PASS）
    size_hint = size_class if size_class != "unknown" else "medium"
    moved = _apply_reviewer_llm_fallback(
        task_id,
        size_hint,
        str(verdict_data.get("reason", "unknown")),
        verdict_path=verdict_path,
        review_md=review_md,
    )
    _cleanup_reviewer_markers(pids_dir, task_id)
    if moved:
        return {"status": "pass", "reason": "static_fallback"}
    return {
        "status": "failed",
        "reason": f"fallback quarantine: {verdict_data.get('reason', 'unknown')}",
    }


def _cleanup_reviewer_markers(pids_dir: Path, task_id: str) -> None:
    """清理 reviewer async 标记文件"""
    for sfx in [
        ".reviewer.out",
        ".reviewer.done",
        ".reviewer.pid",
        ".reviewer.prompt.md",
    ]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass


def _is_path_in_root(p: Path) -> bool:
    """检查解析后的路径是否在 get_workspace() 范围内，防止路径穿越 (CWE-22)"""
    try:
        resolved = p.resolve()
        root_resolved = get_workspace().resolve()
        return root_resolved in resolved.parents or resolved == root_resolved
    except (OSError, RuntimeError):
        return False


def _parse_plan_scope(task_id: str) -> list[str]:
    """从 plan.md 读文件白名单

    兼容两种格式：
       新模板：## 范围 → - **只改文件**： → 后续 - file 行
       旧格式：## 文件白名单 → 直接 - file 行

    安全：返回的路径均已校验在 get_workspace() 范围内，防止路径穿越 (CWE-22/94)。
    """
    plan = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
    if not plan.exists():
        return []
    content = plan.read_text()

    def _clean(f: str) -> str:
        """提取纯文件路径（去掉尾部注释/说明）"""
        f = f.strip().strip("`\"'*")
        # 去掉尾部中文/括号说明（product_role 增强 → 空）
        m = re.match(r"^([\w./~@+\-\[\]]+)", f)
        if m:
            f = m.group(1)
        # 如果还多出来尾缀（如括号前有空格）
        for sep in ("（", "(", "`（", "`("):
            idx = f.find(sep)
            if idx > 0:
                f = f[:idx]
        return f.strip().rstrip(".")

    in_scope = False
    collecting_only = False
    old_format = False
    files = []
    for line in content.split("\n"):
        if line.startswith("## 范围"):
            in_scope = True
            old_format = False
            continue
        if line.startswith("## 文件白名单") or line.startswith("## 文件"):
            in_scope = True
            old_format = True
            continue
        if in_scope and line.startswith("## "):
            break
        if not in_scope:
            continue
        stripped = line.strip()

        if not old_format:
            # 新模板格式
            if "**只改文件" in stripped and (
                stripped.startswith("- ") or stripped.startswith("* ")
            ):
                collecting_only = True
                after_label = stripped.split("**")[-1].lstrip("：:").strip()
                if after_label:
                    for f in after_label.split():
                        f_clean = _clean(f)
                        if f_clean:
                            files.append(f_clean)
                continue
            if "**不改文件" in stripped and (
                stripped.startswith("- ") or stripped.startswith("* ")
            ):
                break
            if collecting_only:
                if stripped.startswith("- ") or stripped.startswith("* "):
                    f = _clean(stripped[2:])
                    if (
                        f
                        and not f.startswith("(")
                        and not f.startswith("不")
                        and f not in ("只改文件", "不改文件")
                    ):
                        files.append(f)
        else:
            # 旧格式：直接收集 - 条目
            if stripped.startswith("- ") or stripped.startswith("* "):
                f = _clean(stripped[2:])
                if f and not f.startswith("不"):
                    files.append(f)
    # 安全校验：过滤掉穿越 get_workspace() 的路径 (CWE-22)
    validated = []
    for f in files:
        candidate = get_workspace() / f
        if _is_path_in_root(candidate):
            validated.append(f)
    return validated


def _get_git_diff(
    workspace: Path, since: str = "HEAD~1", task_id: str = ""
) -> tuple[str, str]:
    """取 git diff 改动，返回 (stat, full_diff)。

    若 task_id 提供，优先按 task 关联 commit 取 diff（G1 修复：reviewer 只审单个 task 的改动）。
    否则按 since ref。

    Args:
        workspace: 项目根目录
        since: git diff 的 ref（默认 HEAD~1 = 最近一次 commit，task_id 提供时忽略）
        task_id: 任务 ID，用于过滤 git log --grep

    Returns:
        (stat_output, diff_output)，git 不可用时都为空字符串
    """
    import subprocess as sp

    try:
        # G1: 优先按 task_id 找关联 commit
        # v0.24.6 (A24-08): 优先 phases.json 里记录的 commit（防 task_id grep 复用导致
        # 拿到历史 commit 的 diff，而非当前本次的 diff）；phases.json 缺失再 fallback 到 grep
        commit = ""
        if task_id:
            phases_file = workspace / ".ccc" / "phases" / f"{task_id}.phases.json"
            if phases_file.exists():
                for line in phases_file.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        phase = json.loads(line)
                        if phase.get("commit"):
                            commit = phase["commit"]
                            break
                    except json.JSONDecodeError:
                        continue
            # fallback: git log --grep task_id（仅在 phases.json 无记录时用）
            if not commit:
                log_r = sp.run(
                    [
                        "git",
                        "log",
                        "--all",
                        "--oneline",
                        "--grep",
                        task_id,
                        "--format=%H",
                        "--max-count=1",
                    ],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                commit = log_r.stdout.strip() if log_r.returncode == 0 else ""

        if commit:
            # task 级别的 diff
            stat_r = sp.run(
                ["git", "diff", f"{commit}^..{commit}", "--stat"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            diff_r = sp.run(
                ["git", "diff", f"{commit}^..{commit}"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # 若父 commit 不存在（首次 commit），用 --root
            if stat_r.returncode != 0:
                stat_r = sp.run(
                    ["git", "diff", "--root", commit, "--stat"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                diff_r = sp.run(
                    ["git", "diff", "--root", commit],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            return stat_r.stdout or "", diff_r.stdout or ""

        # 无 task_id / 没找到 commit：按 since 走（原逻辑 + HEAD~1 不存在降级）
        rev_r = sp.run(
            ["git", "rev-parse", "--verify", since],
            cwd=workspace,
            capture_output=True,
            timeout=5,
        )
        ref = since if rev_r.returncode == 0 else "--root"

        stat_r = sp.run(
            ["git", "diff", ref, "--stat"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        diff_r = sp.run(
            ["git", "diff", ref],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # v0.28.0 (M-008): diff 为空时显式 warning（无 commit 或初次启动场景）
        if not stat_r.stdout and not diff_r.stdout:
            _log.warning(
                "git diff 为空 (ref=%s) — 仓库可能无 commit 或 since 指向了初始", ref
            )
        return stat_r.stdout or "", diff_r.stdout or ""
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.error("[reviewer] git diff 失败: %s", exc)
        return "", ""


def _load_reviewer_skill() -> str:
    """注入 ccc-reviewer skill（对称 product）。"""
    candidates = [
        CCC_HOME / "skills" / "ccc-reviewer" / "SKILL.md",
        Path.home()
        / ".claude"
        / "skills"
        / "ccc-protocol"
        / "skills"
        / "ccc-reviewer"
        / "SKILL.md",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")[:6000]
        except OSError:
            continue
    return ""


def _review_with_llm(
    task_id: str,
    diff_stat: str,
    full_diff: str,
    plan_text: str,
    size_class: str = "medium",
) -> dict:
    """调 Claude API 审查代码。返回 {"verdict": "pass"|"fail", "findings": [...], "summary": "..."}。

    fallback: API 不可用或解析失败 → 返回 {"verdict": "fallback", "reason": "..."}

    v0.24.1: size_class="large" 时追加 impact 分析指令（影响面/风险等级）。
    """
    import os
    import re as _re
    import subprocess as _sp

    if not full_diff and not diff_stat:
        return {"verdict": "fallback", "reason": "no git diff"}

    impact_section = ""
    if size_class == "large":
        impact_section = (
            "## 重点检查（large 类变更，>50 行）\n"
            "6. **影响面分析**：列出本次改动触及的模块 + 上下游调用方 + 是否可能影响其他 task\n"
            "7. **风险等级**：评估本次改动风险（high/medium/low）并说明理由\n"
            "8. **回归路径**：列出需要复测的关键功能点（必须包含 plan 验收清单之外的隐性影响）\n\n"
        )

    skill_text = _load_reviewer_skill()
    skill_block = (
        f"## 角色 Skill（必须遵守）\n{skill_text}\n\n" if skill_text else ""
    )

    prompt = (
        "你是 CCC 资深代码审查员（reviewer 步骤）。按 skill + plan 验收清单逐条核对。\n\n"
        f"{skill_block}"
        "## Plan 验收清单\n"
        f"{plan_text[:12000]}\n\n"
        "## 改动概览 (git diff --stat)\n"
        f"```\n{diff_stat[:4000]}\n```\n\n"
        "## 改动详情 (git diff)\n"
        f"```\n{full_diff[:24000]}\n```\n\n"
        "## 审查清单（逐条核对）\n"
        "1. 数据流正确性（输入/输出/边界）\n"
        "2. 错误处理（异常/边界/资源泄漏）\n"
        "3. 安全（SQL 注入/路径遍历/凭据泄漏/危险函数）\n"
        "4. 命名与可读性\n"
        "5. 是否与 plan 验收清单一致\n\n"
        f"{impact_section}"
        "## 输出要求\n"
        "只输出 JSON，不要 markdown 代码块，不要附加解释。verdict 必须是小写字符串：\n"
        '{"verdict": "pass", '
        '"findings": [{"severity": "high", "file": "...", "line": 0, '
        '"issue": "...", "suggestion": "..."}], '
        '"summary": "..."}\n'
        '或 {"verdict": "fail", "findings": [...], "summary": "..."}\n'
        "即使缺少 findings 也必须有 verdict 字段。\n"
    )

    relay = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    env = _claude_env(relay_url=relay)
    env["CLAUDE_CODE_NONINTERACTIVE"] = "1"  # 禁止任何交互询问
    try:
        # prompt 可能很大（>1MB），写临时文件并 shell 重定向，避免 subprocess.PIPE buffer 截断
        # v0.24.7 (A24-24): 写到 ~/.ccc/prompts/ 私有目录 + mode 0o600，
        # 防 /tmp 下被同用户其他进程读取（review prompt 可能含 plan 描述）
        import tempfile as _tempfile

        _review_prompt_dir = Path.home() / ".ccc" / "prompts"
        _review_prompt_dir.mkdir(parents=True, exist_ok=True)
        _prompt_fd, _prompt_file = _tempfile.mkstemp(
            suffix=".md", prefix="review-prompt-", dir=str(_review_prompt_dir)
        )
        try:
            os.write(_prompt_fd, prompt.encode("utf-8"))
            os.chmod(_prompt_file, 0o600)
        finally:
            os.close(_prompt_fd)
        try:
            with open(_prompt_file, "rb") as f:
                data = f.read()
            # v0.31: flash tier 不稳定，重试 2 次（第 3 次仍失败再 fallback）
            _r = None
            _last_review_err = ""
            for _attempt in range(1, 4):
                try:
                    _cli = _claude_bin()
                    _r = _sp.run(
                        [_cli, "-p", "--model", "flash"],
                        input=data,
                        capture_output=True,
                        text=False,
                        timeout=cfg.reviewer_timeout,
                        env=env,
                    )
                    if _r.returncode == 0:
                        _last_review_err = ""
                        break
                    _last_review_err = f"claude rc={_r.returncode}"
                except ClaudeCliMissing as _e:
                    return {"verdict": "fallback", "reason": str(_e)}
                except _sp.TimeoutExpired:
                    _last_review_err = "timeout(300s)"
                except Exception as _e:
                    _last_review_err = str(_e)[:200]
                if _attempt < 3:
                    _log.warning(
                        "[reviewer] flash tier attempt %d/3: %s",
                        _attempt,
                        _last_review_err,
                    )
                    time.sleep(10)
            r = _r
            if _last_review_err:
                return {"verdict": "fallback", "reason": _last_review_err}
        finally:
            try:
                os.unlink(_prompt_file)
            except OSError as e:
                _log.warning("reviewer prompt temp file unlink failed: %s", e)
        if r.returncode != 0:
            stderr = (
                r.stderr.decode("utf-8", errors="replace")
                if isinstance(r.stderr, bytes)
                else r.stderr
            )
            return {
                "verdict": "fallback",
                "reason": f"claude rc={r.returncode}: {stderr[:200]}",
            }
        output = (
            r.stdout.decode("utf-8", errors="replace")
            if isinstance(r.stdout, bytes)
            else r.stdout
        )
        trimmed = output.strip()
        # 优先：直接尝试解析整个输出（Claude 按指示只返回 JSON）
        if trimmed.startswith("{"):
            try:
                data = json.loads(trimmed)
                if data.get("verdict") in ("pass", "fail"):
                    return data
            except json.JSONDecodeError:
                pass  # 继续 fallback 解析

        # 次优：从 markdown 代码块提取 JSON（匹配首 { 到末 }）
        m = _re.search(
            r"```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```", output, _re.IGNORECASE
        )
        if not m:
            # 最后：裸 JSON 对象，匹配首 { 到末 }（greedy，适应嵌套对象）
            m = _re.search(r"(\{.*\})", output, _re.DOTALL)
        if not m:
            _log.warning("reviewer no JSON in Claude output. output=[%s]", output[:500])
            return {"verdict": "fallback", "reason": "no JSON in Claude output"}
        try:
            json_str = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
            json_str = json_str.strip()
            data = None
            for candidate in (
                json_str,
                _re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_str),
            ):
                try:
                    data = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    continue
            if data is None:
                _log.warning(
                    "reviewer JSON parse failed. output=[%s] json_str=[%s]",
                    output[:500],
                    json_str[:300],
                )
                raise json.JSONDecodeError("all candidates failed", json_str, 0)
            if data.get("verdict") in ("pass", "fail"):
                return data
            return {
                "verdict": "fallback",
                "reason": f"unexpected verdict: {data.get('verdict')}",
            }
        except json.JSONDecodeError as exc:
            return {"verdict": "fallback", "reason": f"JSON parse failed: {exc}"}
    except _sp.TimeoutExpired:
        return {"verdict": "fallback", "reason": "claude timeout (300s)"}
    except NameError:
        return {
            "verdict": "fallback",
            "reason": "r undefined (subprocess crash before assignment)",
        }


def _py_compile_fallback(task_id: str, files: list[str]) -> bool:
    """reviewer LLM 失败时的 fallback：py_compile 静态语法检查。"""
    import subprocess as sp

    for f in files:
        if not f.endswith(".py") or not Path(f).exists():
            continue
        r = sp.run(
            ["python3", "-m", "py_compile", str(f)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            _log.error(
                "[reviewer-fallback] %s py_compile %s FAIL: %s",
                task_id,
                Path(f).name,
                r.stderr[:200],
            )
            return False
    return True


def _parse_diff_size(stat_output: str) -> int | None:
    """解析 git diff --stat 输出，统计总变更行数（insertions + deletions）。

    stat 行格式如: "scripts/ccc-board.py | 42 +++++++++++++--------"
    最后一行格式: "3 files changed, 120 insertions(+), 45 deletions(-)"

    v0.24.3: 返回 None 表示无法解析（缺 summary 行 / diff 为空），
    调用方应 fail-fast 而不是把缺失当成 0 行变更静默通过。
    """
    import re

    insertions = 0
    deletions = 0
    found_summary = False
    for line in stat_output.splitlines():
        line = line.strip()
        if not line:
            continue
        # summary 行优先：无 `|` 但含 insertion/deletion
        if "insertion" in line or "deletion" in line:
            ins_m = re.search(r"(\d+)\s+insertion", line)
            del_m = re.search(r"(\d+)\s+deletion", line)
            if ins_m:
                insertions += int(ins_m.group(1))
                found_summary = True
            if del_m:
                deletions += int(del_m.group(1))
                found_summary = True
            continue
        # file 行（带 `|`）：跳过 —— 计数靠 summary 行
        if "|" not in line:
            continue
    if not found_summary:
        return None
    return insertions + deletions


def _classify_review_size(stat_output: str) -> tuple[str, int | None]:
    """v0.24.1: 按变更量分级。

    Returns:
        ("small" | "medium" | "large", total_changed_lines)
        total=None 表示无法解析（diff 缺 summary 行），调用方应 fail-fast
    """
    total = _parse_diff_size(stat_output)
    if total is None:
        return ("unknown", None)
    if total <= REVIEW_SIZE_SMALL_MAX:
        return ("small", total)
    if total <= REVIEW_SIZE_MEDIUM_MAX:
        return ("medium", total)
    return ("large", total)


def clear_stale_review_locks(
    lock_dir: Path | None = None, *, stale_sec: int | None = None
) -> list[str]:
    """清除超龄 review O_EXCL 僵尸锁。返回被删的文件名列表。

    进程崩溃后锁文件残留会导致 reviewer 永久「持锁中，跳过」。
    """
    if lock_dir is None:
        lock_dir = get_workspace() / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    if stale_sec is None:
        stale_sec = int(os.environ.get("CCC_REVIEW_LOCK_STALE_SEC", "600"))
    cleared: list[str] = []
    now = time.time()
    for lp in lock_dir.glob("*.lock"):
        try:
            age = now - lp.stat().st_mtime
            if age >= stale_sec:
                lp.unlink(missing_ok=True)
                cleared.append(lp.name)
                _log.warning(
                    "[reviewer] 清除僵尸锁 %s (age=%.0fs ≥ %ss)",
                    lp.name,
                    age,
                    stale_sec,
                )
        except OSError as exc:
            _log.warning("[reviewer] 清僵尸锁失败 %s: %s", lp.name, exc)
    return cleared


def reviewer_role() -> dict:
    """代码审查员: 扫 testing → LLM 审查 git diff + plan 验收清单 → 通过则挪 verified

    v0.24.1: 按变更量分级
      - small (≤10 行): 跳过 LLM，仅 py_compile 静态检查
      - medium (10-50 行): 标准 LLM 审查
      - large (>50 行): LLM + impact 分析（影响面/风险等级）

    v0.24.5: 加 per-task advisory lock（A24-01 防并发 reviewer 实例写同 task 的 review.md）
    v0.24.5: medium/large fallback 路径强制 quarantine（A24-03/A24-04 防 v0.23 G2 bypass 复发）
    """
    from _role_lock import assert_role_executor

    assert_role_executor("reviewer", "claude-code")
    moved = []
    lock_dir = get_workspace() / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    clear_stale_review_locks(lock_dir)
    for task in list_tasks("testing"):
        task_id = task["id"]
        # v0.24.5 (A24-01): per-task advisory lock 防并发 reviewer 写 review.md
        # macOS 不支持 O_WRLOCK，用 O_EXCL 创建 + 0o600 模拟 advisory lock
        lock_path = lock_dir / f"{task_id}.lock"
        try:
            _lock_fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
            )
        except FileExistsError:
            # 另一个 reviewer 实例正在审本 task → 跳过本轮，避免文件竞态覆盖
            _log.error("[reviewer] %s ⏸ 持锁中，跳过本轮", task_id)
            continue
        try:
            result = _review_one_task(task_id)
            if result:
                moved.append(task_id)
        finally:
            try:
                os.close(_lock_fd)
                os.unlink(lock_path)
            except OSError as e:
                _log.warning("reviewer lock cleanup failed for %s: %s", task_id, e)
    return {"role": "reviewer", "moved": moved, "counts": update_index()}


def _review_one_task(task_id: str) -> bool:
    """单个 task 的 reviewer 处理（v0.24.5 抽取，便于 advisory lock 包住）。返回是否移 verified。

    v0.24.5 (A24-03/A24-04): medium/large 类 LLM fallback 一律 quarantine + L2 告警，
    禁止仅凭 py_compile 或 plan 验收清单静默 verified（v0.23 G2 bypass 复发红线）。
    small 类仍走原 py_compile / plan-only 路径。
    """
    task = next((t for t in list_tasks("testing") if t["id"] == task_id), None)
    if task is None:
        return False
    plan_file = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
    plan_text = plan_file.read_text() if plan_file.exists() else ""

    # 1. 取 git diff（G1: 按 task_id 过滤，只审本 task 的改动）
    diff_stat, full_diff = _get_git_diff(get_workspace(), task_id=task_id)

    # v0.24.1: 按变更量分级，决定是否需要 LLM
    size_class, total_lines = _classify_review_size(diff_stat)
    # v0.24.3: diff 无法解析（缺 summary 行）→ quarantine，不能静默放行
    if size_class == "unknown":
        _quarantine(
            task_id, reason="v0.24.3 reviewer: diff stat 缺 summary 行，无法分级"
        )
        _log.error(
            "[reviewer] %s ✗ diff stat 解析失败（缺 summary），quarantine",
            task_id,
        )
        return False
    _log.info("[reviewer] %s size=%s lines=%s", task_id, size_class, total_lines)

    # 写审查报告（共用目录）
    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    review_md = report_dir / f"{task_id}.review.md"

    # small 类：仅 py_compile；涉安全路径强制走 LLM
    if size_class == "small":
        files = _parse_plan_scope(task_id)
        if not files:
            files = [str(p) for p in (get_workspace() / "scripts").rglob("*.py")]
        import glob as _glob

        py_files = []
        for f in files:
            matched = _glob.glob(str(get_workspace() / f)) if "*" in f else [str(get_workspace() / f)]
            matched = [m for m in matched if _is_path_in_root(Path(m))]
            py_files.extend(matched)
        py_files = [f for f in py_files if f.endswith(".py") and Path(f).exists()]

        _sensitive = (
            "auth", "password", "secret", "credential", "token",
            "session_store", "executor", "sidecar", "control",
        )
        needs_llm = any(
            any(s in Path(f).name.lower() or s in f.lower() for s in _sensitive)
            for f in py_files
        )
        if needs_llm:
            _log.info(
                "[reviewer] %s small but sensitive paths → LLM review",
                task_id,
            )
            size_class = "medium"
            # 落入下方 LLM 路径
        elif py_files and _py_compile_fallback(task_id, py_files):
            review_md.write_text(
                f"# {task_id} Review\n\n"
                f"## Verdict: **PASS**\n\n"
                f"## Size Class: **small** ({total_lines} 行)\n\n"
                f"v0.24.1: small 类变更跳过 LLM，仅 py_compile 静态检查通过。\n\n"
                f"## Files Checked ({len(py_files)} 条)\n\n"
                + "\n".join(f"- {Path(f).name}" for f in py_files)
            )
            # v0.38: Engine 门禁读 .ccc/verdicts/{id}.verdict.md（红线 11）
            _write_pass_verdict(
                task_id,
                f"small-class py_compile pass ({total_lines} lines)",
            )
            move_task(task_id, "testing", "verified")
            _log.info(
                "[reviewer] %s ✓ small-class static pass (%s 行)", task_id, total_lines
            )
            return True
        elif not needs_llm and not py_files:
            if not full_diff.strip():
                _quarantine(
                    task_id, reason="v0.24.3 small-class: 无 py 文件 + diff 为空"
                )
                _log.error(
                    "[reviewer] %s ✗ small-class quarantine: 空 diff",
                    task_id,
                )
                return False
            if "## 验收" in plan_text or "## 验证" in plan_text:
                review_md.write_text(
                    f"# {task_id} Review\n\n"
                    f"## Verdict: **PASS**\n\n"
                    f"## Size Class: **small** ({total_lines} 行)\n\n"
                    f"v0.24.1: small 类变更无 py 文件，信任 plan 验收清单（diff 非空已校验）。\n"
                )
                _write_pass_verdict(
                    task_id,
                    f"small-class plan-only pass ({total_lines} lines)",
                )
                move_task(task_id, "testing", "verified")
                _log.info("[reviewer] %s ✓ small-class plan-only pass", task_id)
                return True
            _quarantine(task_id, reason="v0.24.1 small-class: 无 py 文件 + 无验收清单")
            _log.error(
                "[reviewer] %s ✗ small-class quarantine: 无静态可检查项", task_id
            )
            return False
        else:
            _log.error(
                "[reviewer] %s ✗ small-class py_compile 失败，留在 testing",
                task_id,
            )
            return False

    # medium / large：走 LLM，large 加 impact 分析提示
    verdict_data = _review_with_llm(
        task_id, diff_stat, full_diff, plan_text, size_class=size_class
    )
    verdict = verdict_data.get("verdict", "fallback")
    summary = verdict_data.get("summary", "")
    findings = verdict_data.get("findings", [])

    # v0.34 (P5): 数学化评分 rubric（用于 reviewer/shadow 对比）
    _score = 10  # 基础分 10
    # JSON 格式（5 分）
    _score += 5  # LLM 返回了有效 JSON
    # scope 合规（5 分）
    _scope_violations = [f for f in findings if "scope" in (f.get("issue", "") or "").lower()]
    if not _scope_violations:
        _score += 5
    # 测试通过（5 分）
    _test_failures = [f for f in findings if "test" in (f.get("issue", "") or "").lower()]
    if not _test_failures:
        _score += 5
    # 幻觉（-10 分）
    _hallucinations = [f for f in findings if "hallucinat" in (f.get("issue", "") or "").lower()]
    _score -= len(_hallucinations) * 10
    # 越界（-10 分）
    _boundary = [f for f in findings if any(kw in (f.get("issue", "") or "").lower() for kw in ("越界", "scope 外", "outside scope"))]
    _score -= len(_boundary) * 10
    _score = max(0, min(25, _score))
    rubric = {
        "score": _score,
        "score_breakdown": {
            "json_format": 5,
            "scope_compliance": 5 if not _scope_violations else 0,
            "tests_pass": 5 if not _test_failures else 0,
            "hallucination": -len(_hallucinations) * 10,
            "scope_violation": -len(_boundary) * 10,
        },
        "threshold": 15,
    }

    review_md.write_text(
        f"# {task_id} Review\n\n"
        f"## Verdict: **{verdict.upper()}** | Score: **{_score}/25**\n\n"
        f"## Size Class: **{size_class}** ({total_lines} 行)\n\n"
        f"{summary}\n\n"
        f"## Findings ({len(findings)} 条)\n\n"
        f"```json\n{json.dumps(verdict_data, ensure_ascii=False, indent=2)}\n```\n"
        f"\n## Score Rubric\n"
        f"```json\n{json.dumps(rubric, ensure_ascii=False, indent=2)}\n```\n"
    )

    # 写 verdict 文件（Engine _verdict_is_valid 检查此文件）
    verdict_dir = get_workspace() / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = verdict_dir / f"{task_id}.verdict.md"
    verdict_path.write_text(
        f"# {task_id} Verdict\n\n"
        f"**Verdict:** {verdict.upper()}\n\n"
        f"**Score:** {_score}/25\n\n"
        f"**Size Class:** {size_class}\n\n"
        f"{summary}\n"
        f"\n## Score Rubric\n"
        f"```json\n{json.dumps(rubric, ensure_ascii=False, indent=2)}\n```\n"
    )

    if verdict == "pass":
        move_task(task_id, "testing", "verified")
        _log.info("[reviewer] %s ✓ LLM pass", task_id)
        return True
    if verdict == "fail":
        _log.error(
            "[reviewer] %s ✗ LLM fail（%d issues），留在 testing",
            task_id,
            len(verdict_data.get("findings", [])),
        )
        return False

    # ── fallback / timeout 分类处理（v0.31+）──
    fallback_reason = verdict_data.get("reason", "").lower()
    if "timeout" in fallback_reason:
        # 超时情形：不 quarantine，写 "TIMEOUT" verdict 让 engine 层重试
        _log.warning(
            "[reviewer] %s ✗ %s-class timeout（reason=%s），留在 testing 等待 engine 重试",
            task_id,
            size_class,
            verdict_data.get("reason", "unknown"),
        )
        verdict_path.write_text(
            f"# {task_id} Verdict\n\n"
            f"**Verdict:** TIMEOUT\n\n"
            f"**Size Class:** {size_class}\n\n"
            f"**Reason:** {verdict_data.get('reason', 'unknown')}\n"
        )
        return False

    # v0.42+: 默认 quarantine；FALLBACK≠PASS，绝不静默 verified
    return _apply_reviewer_llm_fallback(
        task_id,
        size_class,
        str(verdict_data.get("reason", "unknown")),
        verdict_path=verdict_path,
        review_md=review_md,
    )

