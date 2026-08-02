"""board.roles.audit — extracted from ccc-board.py (behavior-preserving)."""
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

def _intake_failsafe(ws: Path, category: str) -> bool:
    """检查是否应该暂停 intake。返回 True = 允许投，False = 熔断。

    同类 audit-task 在 abnormal 占比 > 60% → 源头熔断。
    """
    from _board_store import FileBoardStore

    ws_store = FileBoardStore(ws)
    prefix = f"audit-{category}"
    abnormal = ws_store.list_tasks("abnormal")
    audit_abnormal = [t for t in abnormal if t.get("id", "").startswith(prefix)]

    # 统计所有同类 task（含 backlog+planned+in_progress+testing+abnormal）
    all_audit = list(audit_abnormal)
    for col in ("backlog", "planned", "in_progress", "testing"):
        all_audit.extend(
            t for t in ws_store.list_tasks(col)
            if t.get("id", "").startswith(prefix)
        )

    if not all_audit:
        return True  # 没有同类 task，允许投

    fail_rate = len(audit_abnormal) / len(all_audit)
    if fail_rate > 0.6:
        _log.warning(
            "[intake-failsafe] %s %s: abnormal=%d total=%d rate=%.0f%% → 熔断",
            ws.name, category, len(audit_abnormal), len(all_audit), fail_rate * 100,
        )
        return False
    return True


def _classify_task_intake(task: dict) -> str:
    """决定 task 的处理路径：auto | quick | full

    纯规则决策，不调 LLM，不读 phases.json。
    在 backlog→planned 之前调用，判定后直接走对应路径。

    auto  → ruff --fix + git commit → released（跳过整个 pipeline）
    quick → dev_role(无 plan) + reviewer(small) → verified → released
    full  → product_role → dev_role → reviewer+tester → verified（现有流程）
    """
    tags = task.get("tags", [])
    title = task.get("title", "") or ""
    desc = task.get("description", "") or ""
    tid = task.get("id", "") or ""

    # auto: audit review / lint 类 — 单行修，不需要 plan
    if "audit" in tags and "review" in tags:
        return "auto"
    if "auto" in tags:
        return "auto"
    if tid.startswith("audit-review-"):
        return "auto"
    # 描述含 type/lint 特征
    _auto_keywords = ["type:", "lint:", "ruff:", "mypy:"]
    if any(kw in title.lower() for kw in _auto_keywords):
        return "auto"

    # quick: 小改动（fix/clean/typo 关键词 + 短描述）
    if len(desc) < 100 and any(kw in title.lower() for kw in ["fix", "clean", "typo"]):
        return "quick"
    if "audit" in tags and "decision" not in tags:
        return "quick"

    # full: 全链路（默认）
    return "full"


def _audit_recent_commits(workspace: str, since: str = "2 hours ago") -> str:
    """取 git log 短输出"""
    import subprocess as sp

    try:
        r = sp.run(
            ["git", "log", f"--since={since}", "--oneline", "--no-merges"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout or ""
    except (sp.TimeoutExpired, OSError):
        return ""


def _audit_lint(workspace: str) -> tuple[str, str]:
    """跑 ruff + mypy 门禁。返回 (lint_output, mypy_output)。"""
    import subprocess as sp

    lint_out = ""
    mypy_out = ""
    pyproject = Path(workspace) / "pyproject.toml"
    if not pyproject.exists():
        return "", ""

    try:
        r = sp.run(
            ["ruff", "check", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        lint_out = (r.stdout or "") + (r.stderr or "")
    except (sp.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("audit ruff failed for %s: %s", workspace, e)

    # 动态检测 mypy 目标目录：src/ → app/ → . (项目根)
    ws_path = Path(workspace)
    mypy_targets = []
    for candidate in ("src", "app"):
        if (ws_path / candidate).is_dir():
            mypy_targets.append(candidate)
    if not mypy_targets:
        # 兜底：检测根目录是否有 .py 文件，有则用 "."，否则跳过 mypy
        if list(ws_path.glob("*.py")):
            mypy_targets.append(".")
        else:
            mypy_targets = []  # 无 Python 文件，跳过 mypy

    if mypy_targets:
        try:
            r = sp.run(
                ["mypy"] + mypy_targets,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )
            mypy_out = (r.stdout or "") + (r.stderr or "")
        except (sp.TimeoutExpired, FileNotFoundError, OSError) as e:
            _log.warning("audit mypy failed for %s: %s", workspace, e)

    return lint_out, mypy_out


def _audit_classify(
    workspace: str, recent_commits: str, lint_out: str, mypy_out: str
) -> dict:
    """启发式分类（v0.22 临时方案，v0.23 计划接入 Claude API）。

    返回 {"auto": [...], "review": [...], "decision": [...]}。

    v0.22 实现是字符串 contains 匹配，**非真正 AI**：
    - lint warning（无 "error" 字符串）→ auto
    - mypy "error:" → review
    - 暂无 decision 分类（保留字段给 v0.23 扩展）

    已知局限：可能误判某些 fixable 安全 warning 为 auto。v0.23 升级。
    """
    findings = {"auto": [], "review": [], "decision": []}

    # lint 问题 → auto（ruff --fix 可自动修）
    if lint_out and "error" not in lint_out.lower():
        for line in lint_out.split("\n"):
            line = line.strip()
            if line and not line.startswith("Found"):
                findings["auto"].append(f"lint: {line[:120]}")

    # mypy 错误 → review（需要类型注解修改）
    if mypy_out and "error:" in mypy_out:
        for line in mypy_out.split("\n")[:5]:
            line = line.strip()
            if line and "error:" in line:
                findings["review"].append(f"type: {line[:120]}")

    # 没有 commit → 无发现
    return findings


def _run_auto_fix(task: dict) -> dict:
    """自动修路径：ruff --fix → git commit → released

    Returns:
        {"ok": bool, "commit": str|None, "error": str|None}
    """
    import subprocess as sp_sub

    ws = get_workspace()
    _log.info("[auto-fix] %s 开始 ruff --fix", task.get("id", "?"))

    # ruff --fix（含 src/，因类型标注在源码）
    try:
        sp_sub.run(
            ["ruff", "check", "--fix", "."],
            cwd=ws, capture_output=True, text=True, timeout=60,
        )
    except (sp_sub.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("[auto-fix] ruff failed for %s: %s", task.get("id", "?"), e)
        return {"ok": False, "commit": None, "error": f"ruff 失败: {e}"}

    # 检查工作树
    diff = sp_sub.run(
        ["git", "diff", "--name-only"], cwd=ws, capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    untracked = sp_sub.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ws, capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    if not diff and not untracked:
        _log.info("[auto-fix] %s ruff 无改动", task.get("id", "?"))
        return {"ok": False, "commit": None, "error": "ruff 无改动"}

    # git commit
    sp_sub.run(["git", "add", "-A"], cwd=ws, capture_output=True, timeout=5)
    msg = f"chore(audit): auto-fix {task.get('id', '?')}"
    r = sp_sub.run(
        ["git", "commit", "-m", msg],
        cwd=ws, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        return {"ok": False, "commit": None, "error": f"commit 失败: {r.stderr[:100]}"}

    commit_hash = sp_sub.run(
        ["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    _log.info("[auto-fix] %s ✓ committed %s", task.get("id", "?"), commit_hash[:12])
    return {"ok": True, "commit": commit_hash, "error": None}


def _run_quick_fix(task: dict, timeout: int = 300) -> dict:
    """快修路径：直接调用 opencode executor（不经过 product_role 写 plan）

    task 的 title/description 直接作为 executor prompt。
    执行后继 standard reviewer+tester 路径（在 testing 列）。
    """
    import subprocess as sp_sub

    ws = get_workspace()
    tid = task.get("id", "?")
    prompt = task.get("description", task.get("title", ""))
    _log.info("[quick-fix] %s 开始 exec（无 plan）", tid)

    # 写临时 prompt 文件
    prompt_dir = ws / ".ccc" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = prompt_dir / f"quick-{tid}.md"
    prompt_file.write_text(
        f"## 任务\n{prompt}\n\n"
        f"## 约束\n"
        f"1. 只改必要的文件\n"
        f"2. 改完后 git commit（不要 push）\n"
        f"3. 不改动 scope 外的文件\n"
    )

    # 调 opencode runner
    script_dir = Path(__file__).parent
    launcher = script_dir / "ccc-exec-launcher.sh"
    try:
        if launcher.exists():
            r = sp_sub.run(
                ["bash", str(launcher), str(ws), tid, "--phase", "1"],
                capture_output=True, text=True, timeout=timeout,
            )
            ok = r.returncode == 0
        else:
            # fallback: 直接调 opencode-exec.py
            r = sp_sub.run(
                ["python3", str(script_dir / "opencode-exec.py"),
                 "--phase", tid, "--prompt", str(prompt_file),
                 "--timeout", str(timeout)],
                capture_output=True, text=True, timeout=timeout + 30,
            )
            ok = r.returncode == 0
    except sp_sub.TimeoutExpired:
        _log.warning("[quick-fix] %s 超时 %ds", tid, timeout)
        return {"ok": False, "error": "timeout"}
    finally:
        if prompt_file.exists():
            prompt_file.unlink()

    if ok:
        _log.info("[quick-fix] %s ✓ 完成", tid)
        return {"ok": True, "exit_code": r.returncode, "error": None}
    else:
        _log.warning("[quick-fix] %s ✗ 失败 (exit=%d)", tid, r.returncode if 'r' in dir() else -1)
        return {"ok": False, "error": f"exit={r.returncode if 'r' in dir() else -1}"}


def _audit_post_backlog(workspace: str, items: list, category: str) -> int:
    """把 review/decision 类问题投到对应项目的 backlog。返回投出数。

    v0.42.4: **永久禁用**自动投入（may_auto_inject_tasks=False）。
    """
    try:
        from _ccc_control import may_auto_inject_tasks, may_invent

        if not may_auto_inject_tasks() or not may_invent():
            _log.info(
                "[audit] skip post backlog (%s×%d) — auto-inject hard-disabled",
                category,
                len(items),
            )
            return 0
    except ImportError:
        _log.info(
            "[audit] skip post backlog (%s×%d) — control import failed, refuse",
            category,
            len(items),
        )
        return 0

    from datetime import datetime as _dt

    ws_store = FileBoardStore(Path(workspace))
    date_str = _dt.now(timezone.utc).strftime("%Y%m%d-%H%M")
    now_iso_str = now_iso()
    posted = 0
    for i, item in enumerate(items):
        tid = sanitize_id(f"audit-{category}-{date_str}-{uuid.uuid4().hex[:8]}")
        title = item[:80]
        ws_store.create_task(
            {
                "id": tid,
                "title": title,
                "description": f"[audit] {category} 类问题：\n\n{item}",
                "tags": ["audit", category],
                "status": "backlog",
                "created_at": now_iso_str,
                "updated_at": now_iso_str,
            },
            column="backlog",
        )
        posted += 1
    return posted


def _audit_write_report(
    workspace: str,
    findings: dict,
    commit_log: str,
    auto_fixed: list | None = None,
    mypy_raw: str = "",
    duration_seconds: float = 0.0,
) -> Path:
    """写审计报表到 {workspace}/.ccc/audit-reports/{date}.md"""
    from datetime import datetime as _dt

    name = Path(workspace).name
    date_str = _dt.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    report_dir = Path(workspace) / ".ccc" / "audit-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date_str}.md"

    n_auto = len(findings.get("auto", []))
    n_review = len(findings.get("review", []))

    lines = [
        f"# Audit Report — {name} — {date_str}",
        "",
        "## Recent Commits (2h)",
        "```",
        commit_log or "(无变更)",
        "```",
        "",
        f"## Auto (可自动修) — {n_auto} 条",
    ]
    for item in findings.get("auto", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Auto-Fixed — {len(auto_fixed)} 条")
    for item in auto_fixed:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Review (需审查) — {n_review} 条")
    for item in findings.get("review", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Decision (需决策) — {len(findings.get('decision', []))} 条")
    for item in findings.get("decision", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Build Gate")
    lines.append(f"- ruff: {n_auto} auto / {n_review} review")
    lines.append("- mypy: 详见上方 review 段")
    if duration_seconds:
        lines.append(f"- 实测耗时: {duration_seconds:.1f}s")

    # mypy 原始输出附录（v0.22 N3：review 段只取前 5 行前 120 字符，完整输出在附录）
    if mypy_raw:
        lines.append("")
        lines.append("## 附录：mypy 原始输出")
        lines.append("```")
        lines.append(mypy_raw[:5000])  # 截断 5KB 防巨型输出
        lines.append("```")

    report_path.write_text("\n".join(lines))
    return report_path


def _audit_run_one(ws: str, since: str) -> dict:
    """单 workspace 审计流程：git log → lint/mypy → AI 分类 → auto fix → 投 backlog → 写报表

    v0.24.2: 抽出来作为可并发执行的单元，audit_role 用 ThreadPoolExecutor 并行调度。

    每个 ws 的写入路径（backlog / audit-reports）都是 per-workspace 文件名，
    多 ws 并发互不冲突；auto fix ruff 的 cwd 也是 ws 局部，无共享状态。
    """
    import subprocess as sp
    import time as _time

    _t_ws = _time.time()
    ws_path = Path(ws)
    if not (ws_path / ".git").exists():
        return {"workspace": ws, "status": "no_git", "findings": {}}

    # 1. git log
    commits = _audit_recent_commits(ws, since)
    if not commits.strip():
        return {"workspace": ws, "status": "no_changes", "findings": {}}

    # 2. lint + mypy 门禁
    lint_out, mypy_out = _audit_lint(ws)

    # 3. AI 分类（简化启发式）
    findings = _audit_classify(ws, commits, lint_out, mypy_out)

    # 4. auto 直接修 + review 类直修（不走 CCC pipeline）
    # v0.22 旧逻辑：只对 tests/ + 配置/文档/杂项改（--exclude src）
    # v0.34 扩展：review 类（mypy type error）也尝试 ruff --fix，不走 pipeline
    auto_fixed = []
    try:
        if findings.get("auto"):
            sp.run(
                ["ruff", "check", "--fix", "--exclude", "src", "."],
                cwd=ws, capture_output=True, text=True, timeout=60,
            )
            auto_fixed.extend(findings["auto"])
            findings["auto"] = []
        if findings.get("review"):
            # review 类也 ruff --fix（含 src/，因为类型标注在源码里）
            sp.run(
                ["ruff", "check", "--fix", "."],
                cwd=ws, capture_output=True, text=True, timeout=60,
            )
            # 修完后重跑 lint 看还剩什么
            _lint2, _mypy2 = _audit_lint(ws)
            _remaining = _audit_classify(ws, "", _lint2, _mypy2)
            _fixed_now = [i for i in findings["review"] if i not in _remaining.get("review", [])]
            auto_fixed.extend(_fixed_now)
            findings["review"] = [i for i in findings["review"] if i not in _fixed_now]
            if auto_fixed:
                # 有改动 → git commit
                sp.run(["git", "add", "-A"], cwd=ws, capture_output=True, timeout=10)
                sp.run(
                    ["git", "commit", "-m", f"chore(audit): auto-fix {len(auto_fixed)} issues"],
                    cwd=ws, capture_output=True, timeout=15,
                )
    except (sp.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log.warning("audit auto-fix failed for %s: %s", ws, e)
    # decision 类（架构/配置决策）受 intake failsafe 保护
    posted_decision = 0
    _decision_items = findings.get("decision", [])
    if _decision_items:
        if _intake_failsafe(Path(ws), "decision"):
            posted_decision = _audit_post_backlog(ws, _decision_items, "decision")
        else:
            _log.warning("[audit] %s decision intake 熔断", ws)

    # 6. 写报表
    _elapsed_ws = _time.time() - _t_ws
    report_path = _audit_write_report(
        ws,
        findings,
        commits,
        auto_fixed=auto_fixed,
        mypy_raw=mypy_out,
        duration_seconds=_elapsed_ws,
    )

    return {
        "workspace": ws,
        "status": "audited",
        "auto_fixed": auto_fixed,
        "decision_posted": posted_decision,
        "report": str(report_path),
        "duration_seconds": round(_elapsed_ws, 1),
    }


def audit_role(workspace: str | None = None, since: str = "2 hours ago") -> dict:
    """审计角色 (v0.22) — 跨 workspace 全项目扫描

    不同于 dev/reviewer/tester 等单 workspace 角色，audit 跨多个 workspace 调度
    （依赖 cfg.audit_workspaces）。调用方式：
    - CLI：python3 ccc-board.py audit
    - engine：_audit_should_run() 自动触发
    - main dispatch：单独分支（不在 ROLES 字典中）

    流程: 全项目扫描 → AI 分类 → auto 直接修 / review/decision 投 backlog → 写报表

    v0.24.2: 多 workspace 并行化
      - 单 workspace（指定 ws）：串行执行（原行为）
      - 多 workspace：ThreadPoolExecutor 并发跑，单 ws 处理抽到 _audit_run_one
      - 并发度：min(len(WORKSPACES), 4)，避免 ruff/mypy 进程爆栈

    Args:
        workspace: 指定 workspace；None = 扫所有 WORKSPACES
        since: git log 时间窗口（默认 2h）
    """
    import time as _time
    from concurrent.futures import (
        ThreadPoolExecutor,
        TimeoutError as FuturesTimeoutError,
    )

    _t0 = _time.time()
    targets = [workspace] if workspace else list(WORKSPACES)
    results = []

    if len(targets) <= 1:
        # 单 ws：保持原串行路径，无线程开销
        if targets:
            results.append(_audit_run_one(targets[0], since))
    else:
        # v0.24.2: 多 ws 并发
        # v0.24.3: OOM 防护 — max_workers=2 避免 4×(ruff+mypy) 同时跑爆内存
        max_workers = min(len(targets), 2)
        # v0.24.3: 单 ws timeout — 单卡死不能阻塞整个 audit 角色
        ws_timeout = 120
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_audit_run_one, ws, since): ws for ws in targets}
            for fut, ws in futures.items():
                try:
                    results.append(fut.result(timeout=ws_timeout))
                except FuturesTimeoutError:
                    results.append(
                        {
                            "workspace": ws,
                            "status": "timeout",
                            "error": f"timeout after {ws_timeout}s",
                        }
                    )
                except Exception as exc:
                    results.append(
                        {"workspace": ws, "status": "error", "error": str(exc)}
                    )

    # 记录运行时间
    _elapsed = _time.time() - _t0
    from datetime import datetime as _dt

    ws_slug = Path(str(workspace)).name if workspace else "CCC"
    last_run = Path.home() / ".ccc" / f"audit-last-run.{ws_slug}.json"
    last_run.parent.mkdir(parents=True, exist_ok=True)
    last_run.write_text(
        json.dumps(
            {
                "workspace": str(workspace) if workspace else "CCC",
                "last_run": _dt.now(timezone.utc).isoformat(),
                "results_count": len(results),
                "duration_seconds": round(_elapsed, 1),
            },
            ensure_ascii=False,
        )
        + "\n"
    )

    # v0.51.0 P2-1: 删除 _may_invent() 守护的 evolve-on-audit 块（INVENT_HARD_DISABLED 后永不触发）
    # evolve_results 保留空列表占位以维持 audit_role 返回 dict 的 schema 兼容性
    # _evolve_run_one 函数本身保留（test_evolve.py 通过 monkeypatch may_invent=True 测其逻辑）
    evolve_results = []

    return {
        "role": "audit",
        "results": results,
        "duration_seconds": round(_elapsed, 1),
        "evolve": evolve_results,
    }


def _evolve_run_one(ws: str) -> dict:
    """单 workspace evolve 扫描：健康+安全 → 去重/排序 → 投 backlog"""
    try:
        from _evolve import evolve_run

        return evolve_run(ws)
    except Exception as e:
        _log.warning("[evolve] %s evolve 异常: %s", ws, e)
        return {"error": str(e), "posted": 0, "total": 0, "filtered": 0}

