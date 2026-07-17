"""Workspace isolation — 看板仓与 CCC 仓硬隔离。

根因（2026-07-17 实锤）：
1. ``opencode run`` 有 ``--dir``，只设进程 cwd 不够 → session 绑到 Engine
   launchd WorkingDirectory（CCC），xy/qb 任务往 CCC commit。
2. 全局 MCP filesystem 根为 ``~/program`` → ``--pure`` 关闭外部插件。
3. ``ccc-board`` 旧路径曾漏传 ``--cwd``。
4. commit-gate 只查目标仓；串仓 commit 在目标仓看不见 → 死循环 relaunch，
   同时污染 CCC。

本模块提供：要求 cwd、注册仓 HEAD 基线、phase 后跨仓审计。
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _config import get_logger

_log = get_logger("workspace.isolation")

# CCC 编排仓（脚本所在）；永远列入「禁止被业务 task 改写」的监视列表
CCC_ORCH_HOME = Path(__file__).resolve().parents[1]


def require_cwd(cwd: str | Path | None) -> Path:
    """cwd 必填且必须是已存在目录；否则 raise ValueError。"""
    if cwd is None or str(cwd).strip() in ("", ".", "./"):
        raise ValueError(
            "workspace cwd required for isolation "
            "(refuse defaulting to Engine/CCC WorkingDirectory)"
        )
    p = Path(cwd).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"workspace cwd not a directory: {p}")
    return p


def load_registered_workspaces() -> list[Path]:
    """~/.ccc/workspaces.json + CCC 编排仓。"""
    out: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        try:
            r = p.expanduser().resolve()
        except OSError:
            return
        key = str(r)
        if key in seen:
            return
        if r.is_dir() and (r / ".git").exists():
            seen.add(key)
            out.append(r)

    _add(CCC_ORCH_HOME)
    ws_file = Path.home() / ".ccc" / "workspaces.json"
    if ws_file.is_file():
        try:
            data = json.loads(ws_file.read_text(encoding="utf-8"))
            for item in data.get("workspaces") or []:
                if isinstance(item, dict) and item.get("path"):
                    _add(Path(str(item["path"])))
        except (OSError, json.JSONDecodeError) as exc:
            _log.warning("workspaces.json read failed: %s", exc)
    return out


def git_head(repo: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        _log.debug("git_head %s: %s", repo, exc)
    return ""


def git_log_grep(repo: Path, pattern: str, *, max_count: int = 5) -> list[str]:
    try:
        r = subprocess.run(
            [
                "git",
                "log",
                "--all",
                "--grep",
                pattern,
                f"--max-count={max_count}",
                "--format=%H",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError) as exc:
        _log.debug("git_log_grep %s: %s", repo, exc)
    return []


def isolation_baseline_path(ws: Path, task_id: str) -> Path:
    return ws / ".ccc" / "pids" / f"{task_id}.isolation.json"


def capture_isolation_baseline(ws: Path, task_id: str) -> dict[str, Any]:
    """Launch 前：快照所有注册仓 HEAD（含目标仓）。"""
    ws = require_cwd(ws)
    heads: dict[str, str] = {}
    for repo in load_registered_workspaces():
        heads[str(repo)] = git_head(repo)
    # 确保目标仓在内
    heads[str(ws.resolve())] = git_head(ws)
    payload = {
        "task_id": task_id,
        "target": str(ws.resolve()),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "heads": heads,
    }
    path = isolation_baseline_path(ws, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def audit_isolation_after(ws: Path, task_id: str) -> tuple[bool, list[str]]:
    """Phase/task 结束后：禁止业务 task_id 出现在非目标仓；监视仓 HEAD 异动告警。

    Returns: (ok, errors)
    """
    ws = require_cwd(ws)
    target = str(ws.resolve())
    errors: list[str] = []
    path = isolation_baseline_path(ws, task_id)
    baseline_heads: dict[str, str] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            baseline_heads = dict(data.get("heads") or {})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"isolation baseline unreadable: {exc}")

    for repo in load_registered_workspaces():
        repo_s = str(repo.resolve())
        if repo_s == target:
            continue
        # 1) 非目标仓出现本 task_id 的 commit → 硬失败
        hits = git_log_grep(repo, task_id, max_count=3)
        if hits:
            errors.append(
                f"CROSS-REPO POLLUTION: task_id={task_id} committed in "
                f"{repo_s} ({hits[0][:12]}…) — must only commit in {target}"
            )
        # 2) HEAD 相对基线变化（且非空基线）→ 硬失败（防无 task_id 的脏写）
        pre = baseline_heads.get(repo_s, "")
        now = git_head(repo)
        if pre and now and pre != now:
            # 若变化的 commit 消息不含 task_id，仍可能是并发其他任务；
            # 对编排仓 CCC 一律硬拒；对其它仓仅当 grep 命中才已在上面报错。
            if repo.resolve() == CCC_ORCH_HOME.resolve():
                errors.append(
                    f"CROSS-REPO POLLUTION: CCC orch HEAD moved "
                    f"{pre[:12]}→{now[:12]} during task {task_id}"
                )

    return (len(errors) == 0), errors


def cwd_hardgate_block(workspace: Path) -> str:
    """注入 prompt 的工作目录硬门文案。"""
    ws = str(workspace.resolve())
    orch = str(CCC_ORCH_HOME.resolve())
    return (
        f"## 工作目录硬门（违者本卡 FAIL）\n"
        f"- **唯一 cwd / git 根**：`{ws}`\n"
        f"- 所有 Read/Write/Edit/Bash/`git commit` 必须在该目录内\n"
        f"- **禁止**写到编排仓 `{orch}` 或其他仓库\n"
        f"- 相对路径一律相对上述 cwd；忽略 plan 里错误的绝对根路径\n"
        f"- commit message 必须含本 task id；只允许在本仓 commit\n\n"
    )


def isolation_enabled() -> bool:
    return os.environ.get("CCC_SKIP_WORKSPACE_ISOLATION", "").strip() not in (
        "1",
        "true",
        "yes",
    )
