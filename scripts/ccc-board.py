#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.30)

7 角色都通过这个 core 操作 .ccc/board/:
- product: backlog → planned
- dev: planned → in_progress → testing
- reviewer: testing → verified (过 ruff/mypy)
- tester: testing → verified (过 pytest)
- ops: 健康检查 (不动 board)
- kb: verified → released (归档)
- regress: released → backlog (回归回测)

任务流转规则见 .ccc/board/README.md

Phase 2 架构:
- 子模块 scripts/board/{context,lock,prompt,store_ops,roles}.py
- workspace 经 board.context.set_workspace / get_workspace（无全局 get_workspace() 补丁）
- 锁协议统一 fcntl.flock（board.lock）
- 本文件保留公开 API re-export，兼容 importlib 加载
"""

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

from _config import Config, get_logger
from _executor import _claude_env, _sanitized_env
from _board_store import FileBoardStore, _atomic_write as _store_atomic_write
import phase_lint
from _utils import now_iso as _utils_now_iso
from _utils import sanitize_id as _utils_sanitize_id
from _utils import sanitize_prompt_input as _sanitize_prompt_input

from board.context import (
    get_workspace,
    set_workspace,
    clear_workspace,
    board_dir,
    events_dir,
    ccc_home,
)
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import (
    build_dev_phase_prompt,
    build_dev_phase_prompt_with_hint,
)
from board import store_ops as _store_ops

_log = get_logger("board")

# v0.28.0 (L-001): cfg / store 改为 lazy 初始化 — 避免 import 时即建 FileBoardStore
# 触发 mkdir（workspace 路径权限问题会直接挂 import）。
# get_workspace() / CCC_HOME / board_dir() / events_dir() 仍为 eager（Path() 不触发 I/O，开销可忽略）。
_cfg_instance: Config | None = None
_store_instance: FileBoardStore | None = None


def _get_cfg() -> Config:
    global _cfg_instance
    if _cfg_instance is None:
        _cfg_instance = Config()
    return _cfg_instance


def _get_store() -> FileBoardStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = FileBoardStore(_get_cfg().workspace)
    return _store_instance


def _reset_lazy() -> None:
    """重置 lazy 缓存（engine 主循环每轮切换 workspace 时调用）。"""
    global _cfg_instance, _store_instance
    _cfg_instance = None
    _store_instance = None
    _store_ops.reset_store_cache()


# 历史兼容：保留同名 module-level 名称（cfg/store）作为 lazy proxy。
# 旧代码 `cfg.max_retry` / `store.list_tasks(...)` / `cfg.default_timeout` 写法不变。
class _CfgProxy:
    """v0.28.0 (L-001): Config lazy proxy。"""

    def __getattr__(self, name: str):
        return getattr(_get_cfg(), name)


class _StoreProxy:
    """v0.28.0 (L-001): FileBoardStore lazy proxy。"""

    def __getattr__(self, name: str):
        return getattr(_get_store(), name)


cfg = _CfgProxy()
store = _StoreProxy()

# Phase 2: workspace 经 get_workspace()/board_dir()；引擎只能 set_workspace()

CCC_HOME = ccc_home()

# 容错参数（从 Config 读取）
MAX_RETRY = cfg.max_retry
MAX_STALE_HOURS = cfg.max_stale_hours
# ═══════════════════════════════════════════
# 超时配置（v0.28.0 F2-M1）
# ═══════════════════════════════════════════

_log.info("ccc-board config: exec_timeout=%ds", cfg.exec_timeout)


def sanitize_id(tid: str) -> str:
    """净化 task_id：只保留字母、数字、下划线、连字符，防止路径遍历

    v0.28.0 (H-003): 委托 _utils 统一实现。兼容既有调用方。
    """
    return _utils_sanitize_id(tid)


def now_iso() -> str:
    """北京时间 ISO 8601 时间戳（+08:00 后缀）

    v0.28.1: 从 UTC Z 回到 Asia/Shanghai +08:00（对齐用户所在地）。
    v0.28.0 (H-003): 曾统一为 UTC Z 以消除 +08:00 / Z 混用。
    """
    return _utils_now_iso()


def _backoff_seconds(retry: int) -> int:
    """指数退避：60 * 2^retry，封顶 3600s（1h）

    retry=0→60s, 1→120s, 2→240s, 3→480s, 4→960s, 5→1920s, 6+→3600s
    """
    return min(60 * (2**retry), 3600)


def _quarantine(task_id: str, reason: str) -> None:
    """将任务移入异常列（委托 FileBoardStore）"""
    store.quarantine(task_id, reason)
    try:
        from _failure_ledger import infer_role_from_reason, record_failure

        record_failure(
            get_workspace(),
            task_id=task_id,
            role=infer_role_from_reason(reason or ""),
            reason=reason or "unknown",
            from_col=None,
            to_col="abnormal",
            related_stats_event="quarantine",
        )
    except Exception as exc:
        _log.error("[failures] quarantine ledger failed for %s: %s", task_id, exc)
    # v0.32: 自动追加到 docs/lessons.md
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(get_workspace(), task_id, phase=None, error=reason)
    except Exception as exc:
        _log.warning("[lessons] auto_append failed for %s: %s", task_id, exc)



def _task_id_exists(task_id: str) -> bool:
    """检查 task_id 是否在任意列中已存在"""
    return store._task_id_exists(task_id)


def create_task(data: dict, column: str = "backlog") -> bool:
    """创建新 task（委托 FileBoardStore）"""
    return store.create_task(data, column=column)


def list_tasks(column: str) -> list[dict]:
    """读某列所有 task（委托 FileBoardStore）"""
    return store.list_tasks(column)


def move_task(task_id: str, from_col: str, to_col: str) -> bool:
    """把 task 从 from_col 挪到 to_col（委托 FileBoardStore）"""
    return store.move_task(task_id, from_col, to_col)


def update_index() -> dict:
    """更新 .ccc/board/index.json 状态总览（委托 FileBoardStore）"""
    return store.update_index()


def _load_retry_from_phases(phases: list[dict], phase_id: int) -> int:
    """从已解析的 phases 列表取指定 phase 的 retry 计数。

    避免 re-read JSONL 文件（_load_retry_count 旧版直接读文件，改为复用已解析 phases）。
    """
    for p in phases:
        p_id = p.get("phase")
        if p_id is None:
            continue
        if int(p_id) != phase_id:
            continue
        try:
            return int(p.get("retry", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _load_timeout(phases_file: Path, default: int = None) -> int:
    """从 phases.jsonl 的第一个 phase 行读 timeout（跳过 schema_version）

    v0.28.0: default 缺省走 cfg.default_timeout（默认 1800）
    v0.28.x (engine-phase-retry-config): 当 phase 有 timeout 字段时按 phase 配置；
    否则用 cfg.default_timeout（1800）。也兼容 phase 内 max_retry（默认 cfg.DEFAULT_RETRY=3）。
    """
    if default is None:
        default = cfg.default_timeout
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                phase = json.loads(line)
                if isinstance(phase, list):
                    phase = phase[0] if phase else {}
                if "schema_version" in phase:
                    continue
                to = phase.get("timeout")
                if to is None:
                    return default
                try:
                    from _config import parse_duration

                    return parse_duration(to, default)
                except Exception:
                    return default
    except (FileNotFoundError, json.JSONDecodeError) as e:
        _log.warning("load phase timeout from %s failed: %s", phases_file, e)
    return default


def _load_retry_cap(
    phases_file: Path, phase_id: int = None, default: int = None
) -> int:
    """从 phases.jsonl 读指定 phase 的 max_retry（重试上限），跳过 schema_version。

    engine-phase-retry-config: phase.max_retry 配置化重试上限，缺省走 cfg.DEFAULT_RETRY=3。
    - 传 phase_id 时定位到该 phase 行；不传则取第一个 phase。
    - 若 phase 行没有 max_retry 字段，使用 default（默认 cfg.DEFAULT_RETRY=3）。
    - max_retry 必须 ≥ 1，越界或非法时降级为 default。
    """
    default_retry = getattr(cfg, "DEFAULT_RETRY", 3) if default is None else default
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, list):
                    obj = obj[0] if obj else {}
                if not isinstance(obj, dict) or "schema_version" in obj:
                    continue
                if phase_id is not None and obj.get("phase") != phase_id:
                    continue
                mr = obj.get("max_retry")
                if mr is None:
                    return default_retry
                try:
                    n = int(mr)
                except (TypeError, ValueError):
                    return default_retry
                if n < 1:
                    return default_retry
                return n
    except (FileNotFoundError, OSError) as e:
        _log.warning("load phase max_retry from %s failed: %s", phases_file, e)
    return default_retry


# v0.24 phase 逻辑 → board.phase（Phase 2 拆包）
from board.phase import (  # noqa: E402
    PHASE_TERMINAL_OK,
    PHASE_TERMINAL_FAIL,
    PHASE_MAX_ENGINE_ITER,
    _load_phases,
    _detect_phase_cycle,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _read_engine_iter_meta,
    _write_engine_iter_meta,
    _read_engine_iter,
    _write_engine_iter,
    _move_task_to_abnormal_if_all_terminal_failed,
)

from _claude_cli import ClaudeCliMissing, resolve_claude_cli


def _claude_bin() -> str:
    """运行时解析 claude 绝对路径（禁止 import-time 冻死）。"""
    return resolve_claude_cli(require=True)


def _get_relay_url() -> str:
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


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


# v0.28.0 (M-002): 模块级缓存 = {path: (result, ts)} — 300s TTL 过期
_GET_CODE_CONTEXT_TTL_S = 300.0
_get_code_context_cache: dict[str, tuple[str, float]] = {}


def _call_claude_for_plan(task: dict) -> tuple[str, list]:
    """调 claude CLI 生成 plan.md + phases.json（通过中转站 127.0.0.1:4000）"""
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
        """注入 ccc-product skill（harness：身份来自 skill，非口头自称）。"""
        candidates = [
            CCC_HOME / "skills" / "ccc-product" / "SKILL.md",
            Path.home() / ".claude" / "skills" / "ccc-protocol" / "skills" / "ccc-product" / "SKILL.md",
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
            f"禁止写源码；每 phase 必须非空 scope；验收须含意图+可执行命令。\n\n"
            f"{skill_block}"
            f"{baseline_block}"
            f"## 项目概况\n{profile[:1500]}\n\n"
            f"## 当前代码状态（v0.23：自动注入）\n{code_ctx[:3000] if code_ctx else '（无代码上下文）'}\n\n"
            f"## 任务\n"
            f"- id: {task['id']}\n"
            f"- title: {_sanitize_prompt_input(task.get('title', ''))}\n"
            f"- description: {_sanitize_prompt_input(task.get('description', ''))}\n\n"
            f"## Plan 格式（严格按此结构）\n{template_plan}\n\n"
            f"## Phases 格式\n"
            f"每行一个 JSON object：\n"
            f'{{"phase": <int>, "status": "pending", "scope": ["改动的文件路径数组"], "subtasks": {{"1.1": "pending", ...}}, "timeout": <秒>, "commit": null, "notes": ""}}\n'
            f"scope 字段：显式列举本 phase 改动的所有文件路径（路径集，不可用 ['all'] 除非全仓改）。\n"
            f"可选字段 depends_on（list[int]）：声明 phase 依赖关系。\n"
            f"合法示例（双 phase）：\n"
            f'{{"phase": 1, "status": "pending", "scope": ["scripts/foo.py"], "subtasks": {{"1.1": "pending"}}, "timeout": 1800, "commit": null, "notes": ""}}\n'
            f'{{"phase": 2, "status": "blocked", "depends_on": [1], "scope": ["scripts/bar.py"], "subtasks": {{"2.1": "pending"}}, "timeout": 1800, "commit": null, "notes": ""}}\n\n'
            f"## Phase 数上限\n"
            f" 重要约束：每个 task 的 phase 数**最多 2 个**。\n"
            f"如果 task 复杂，应将其拆成多个子 task（每个在 backlog 中独立），\n"
            f"每个子 task 不超过 2 phases。\n\n"
            f"## Depends_on 硬约束\n"
            f" - depends_on 只能引用本 plan 内已存在的 phase_id\n"
            f" - 单 phase 任务的 depends_on 留空数组（不填此字段）\n"
            f" - 多 phase 任务必须声明正确的依赖关系，引擎据此解析执行顺序\n\n"
            f"## 参考历史 plan\n{ref}\n\n"
            f"## 输出要求\n"
            f"输出以下两部分，用分隔符包裹：\n\n"
            f"---PLAN---\n（plan.md 完整内容）\n---END_PLAN---\n"
            f"---PHASES---\n（phases JSONL，每行一个 phase JSON）\n---END_PHASES---\n"
        )

    prompt = _build_prompt(True)

    # v0.31: 注入 lessons 上下文
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

    relay_url = _get_relay_url()
    env = _claude_env(relay_url=relay_url)

    def _run_claude(prompt_text: str) -> str:
        result = subprocess.run(
            [_claude_bin(), "-p"],
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=cfg.default_timeout,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {result.returncode}: {result.stderr[:500]}"
            )
        return result.stdout

    def _parse_output(output: str) -> tuple[str, list]:
        plan_match = re.search(r"---PLAN---\n(.*?)\n---END_PLAN---", output, re.DOTALL)
        if not plan_match:
            raise RuntimeError("---PLAN--- section not found in Claude output")
        plan_content = plan_match.group(1).strip()

        phases_match = re.search(
            r"---PHASES---\n(.*?)\n---END_PHASES---", output, re.DOTALL
        )
        if not phases_match:
            raise RuntimeError("---PHASES--- section not found in Claude output")

        phases = []
        for line in phases_match.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                phases.append(json.loads(line))
        return plan_content, phases

    def _check_phase_limit(phases: list) -> None:
        max_phases = _get_cfg().max_phases
        if len(phases) > max_phases:
            raise RuntimeError(f"phase 数 {len(phases)} 超过上限 {max_phases}")

    try:
        output = _run_claude(prompt)
        try:
            result = _parse_output(output)
            _check_phase_limit(result[1])
            # v0.31/v0.42: phase_lint + plan 验收硬门 — 坏产物不许入盘
            return _gate_product_artifacts(result[0], result[1], log_prefix="[product]")
        except (json.JSONDecodeError, RuntimeError):
            _log.warning("[product] phases 解析失败，简化 prompt 重试 1 次")
            retry_prompt = _build_prompt(include_ref_plans=False)
            output = _run_claude(retry_prompt)
            try:
                result = _parse_output(output)
                _check_phase_limit(result[1])
                return _gate_product_artifacts(
                    result[0], result[1], log_prefix="[product-retry]"
                )
            except (json.JSONDecodeError, RuntimeError) as exc:
                fallback_dir = get_workspace() / ".ccc" / "product_fallback"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                fb_plan = _generate_fallback_plan(task)
                (fallback_dir / f"{task_id}.plan.md").write_text(fb_plan)
                (fallback_dir / f"{task_id}.failed").write_text(str(exc))
                raise RuntimeError(f"phases parse failed after retry: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 300s")


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
    _plan_ok, _plan_errs = phase_lint.validate_plan_acceptance(plan_content)
    if not _plan_ok:
        raise RuntimeError(f"plan_lint failed: {'; '.join(_plan_errs)}")
    if _lint_warnings:
        _log.warning("%s phase_lint warnings: %s", log_prefix, _lint_warnings)
    return _annotate_plan_git_warn(plan_content), phases


def product_role(task_id: str = "") -> dict:
    """产品经理：扫 backlog，或 --promote 调 Claude API 写 SPEC-合规 plan"""
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

        _log.info("正在拆解 %s（调 Claude API 生成 plan）...", task_id)
        plan_content = None
        phases = None
        fallback = False
        try:
            plan_content, phases = _call_claude_for_plan(task)
        except RuntimeError as e:
            err_msg = str(e)
            # v0.42: 硬门禁失败 — 不写 planned，记 ledger，留 backlog
            if "phase_lint" in err_msg or "plan_lint" in err_msg:
                _log.error("product 硬门禁失败: %s", e)
                try:
                    from _failure_ledger import record_failure

                    record_failure(
                        get_workspace(),
                        task_id=task_id,
                        role="product",
                        reason=err_msg[:500],
                        phase=0,
                        from_col="backlog",
                        to_col=None,
                        related_stats_event="product_lint_fail",
                    )
                except Exception as ledger_err:
                    _log.warning("lint fail ledger: %s", ledger_err)
                return {
                    "role": "product",
                    "error": err_msg,
                    "task_id": task_id,
                    "lint_blocked": True,
                }
            _log.error("API 调用失败: %s", e)
            _log.info("使用 fallback plan（API 不可用）")
            plan_content = _generate_fallback_plan(task)
            phases = _generate_fallback_phases()
            # v0.31 (P0.4): fallback plan 禁止空 scope → 异常隔离，不入 executor
            if not plan_content or "待补充" in plan_content or not phases:
                _log.error(
                    "fallback plan 空 scope → 异常隔离 (task=%s)", task_id
                )
                try:
                    move_task(task_id, "backlog", "abnormal")
                except Exception as mv_err:
                    _log.warning("移 abnormal 失败: %s", mv_err)
                update_index()
                try:
                    subprocess.run(
                        ["bash", str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                         "L2", f"fallback empty scope ({task_id})",
                         "planner unavailable, no scope — abnormal"],
                        capture_output=True, timeout=5,
                        env=_sanitized_env(),
                    )
                except Exception as ntfy_err:
                    _log.warning("notify 失败: %s", ntfy_err)
                return {"role": "product", "error": "fallback empty scope",
                        "task_id": task_id, "abnormal": True}
            fallback = True

        # v0.28.0 (F1-H1/H3 修): product_role 写 plan+phases 加 advisory lock
        # R-07 的 _apply_phase_status_updates 已用 fcntl.flock，这里用同一协议。
        # 锁文件: .ccc/.product_role.lock
        # F1-H2 (crash 原子性): 先写 temp 文件再 rename，保证两个文件要么都完整要么都不存在
        product_lock = get_workspace() / ".ccc" / ".product_role.lock"
        product_lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            _acquire_product_lock(product_lock)
        except Exception as exc:
            _log.error("product_role 锁获取失败: %s — 放弃写入", exc)
            return {
                "role": "product",
                "error": f"lock acquire failed: {exc}",
            }

        try:
            plan_dir = get_workspace() / ".ccc" / "plans"
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan_file = plan_dir / f"{task_id}.plan.md"

            phases_dir = get_workspace() / ".ccc" / "phases"
            phases_dir.mkdir(parents=True, exist_ok=True)
            phases_file = phases_dir / f"{task_id}.phases.json"

            # 写 phases（先，最重要的）
            schema_line = json.dumps({"schema_version": "1.0"}, ensure_ascii=False)
            phases_tmp = phases_dir / f".{task_id}.phases.tmp"
            phases_content = (
                schema_line
                + "\n"
                + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases)
                + "\n"
            )
            phases_tmp.write_text(phases_content)
            phases_tmp.rename(phases_file)
            _log.info("✓ 写入 %s (%d phases)", phases_file, len(phases))

            # 再写 plan
            plan_tmp = plan_dir / f".{task_id}.plan.tmp"
            plan_tmp.write_text(plan_content)
            plan_tmp.rename(plan_file)
            _log.info("✓ 写入 %s", plan_file)

            move_task(task_id, "backlog", "planned")

            # v0.26 Protocol v1 §5: 自动分配 color_group（首次见 task）
            # 写 phase 列表时给每个 phase 标 color_depth=1（task 自身是父 depth=0）
            try:
                from _board_store import assign_color_group

                color_group = assign_color_group(
                    get_workspace(), parent_group=task.get("color_group")
                )
                from pathlib import Path as _P

                task_file = _P(".ccc/board/planned") / f"{task_id}.jsonl"
                if task_file.exists():
                    task_data = json.loads(task_file.read_text())
                    task_data["color_group"] = color_group
                    task_data["color_depth"] = 0  # 父任务 depth=0
                    # v0.28.1: 根据 plan 内容推断 complexity
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
                        task_data["complexity"] = "small"
                    elif plan_weight <= 200:
                        task_data["complexity"] = "medium"
                    else:
                        task_data["complexity"] = "large"
                    _log.info(
                        "%s complexity=%s (weight=%d, lines=%d, files=%d, sections=%d)",
                        task_id,
                        task_data["complexity"],
                        plan_weight,
                        plan_size,
                        file_mentions,
                        section_count,
                    )
                    task_file.write_text(
                        json.dumps(task_data, ensure_ascii=False) + "\n"
                    )
                    _log.info(
                        "%s assigned color_group=%s depth=0", task_id, color_group
                    )
                if phases:
                    for p in phases:
                        p.setdefault("color_depth", 1)
                        p.setdefault("color_group", color_group)
                    phases_tmp = phases_dir / f".{task_id}.phases.tmp"
                    phases_tmp.write_text(
                        '{"schema_version": "1.1"}'
                        + "\n"
                        + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases)
                        + "\n"
                    )
                    phases_tmp.rename(phases_file)
            except Exception as e:
                _log.warning("color assign failed (non-fatal): %s", e)

            # 清理 temp 文件
            for tmp in (
                plan_dir / f".{task_id}.plan.tmp",
                phases_dir / f".{task_id}.phases.tmp",
            ):
                if tmp.exists():
                    tmp.unlink()

        finally:
            _release_product_lock(product_lock)
        # ── 锁释放 END ──

        result = {
            "role": "product",
            "promoted": task_id,
            "fallback": fallback,
            "counts": update_index(),
        }
        return result

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


# ═══════════════════════════════════════════════════════════════
# v0.33: product_role 异步化（Popen + marker 文件）
# ═══════════════════════════════════════════════════════════════


def launch_product_async(task_id: str) -> dict:
    """异步启动 product_role 子进程。

    写 prompt 文件后 Popen claude -p，不在引擎 tick 内阻塞。
    后续由 check_product_async() 在另一 tick 检查结果。

    Returns: {"ok": True, "pid": int} 或 {"error": str}
    """
    task_id = sanitize_id(task_id)
    tasks = list_tasks("backlog")
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return {"error": f"task '{task_id}' not found in backlog"}

    pids_dir = get_workspace() / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build prompt（从 _call_claude_for_plan 提取的核心逻辑）
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
        f"每行一个 JSON object：\n"
        f'{{"phase": <int>, "status": "pending", "subtasks": {{"1.1": "pending", ...}}, "timeout": <秒>, "commit": null, "notes": ""}}\n\n'
        f"## Phase 数上限\n"
        f" 重要约束：每个 task 的 phase 数**最多 2 个**。\n"
        f"如果 task 复杂，应将其拆成多个子 task（每个在 backlog 中独立），\n"
        f"每个子 task 不超过 2 phases。\n\n"
        f"## 参考历史 plan\n{ref_plans}\n\n"
        f"## 输出要求\n"
        f"输出以下两部分，用分隔符包裹：\n\n"
        f"---PLAN---\n（plan.md 完整内容）\n---END_PLAN---\n"
        f"---PHASES---\n（phases JSONL，每行一个 phase JSON）\n---END_PHASES---\n"
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

    # 5. Popen claude -p（异步）
    result_file = pids_dir / f"{task_id}.product.out"
    err_file = pids_dir / f"{task_id}.product.err"
    relay_url = _get_relay_url()
    env = _claude_env(relay_url=relay_url)

    try:
        with open(result_file, "w") as out_f, open(err_file, "w") as err_f, open(
            prompt_file, "r"
        ) as in_f:
            proc = subprocess.Popen(
                [_claude_bin(), "-p"],
                stdin=in_f,
                stdout=out_f,
                stderr=err_f,
                start_new_session=True,
                env=env,
            )
        pids_dir.joinpath(f"{task_id}.product.pid").write_text(str(proc.pid))
        _log.info("[product-async] %s launched PID=%d", task_id, proc.pid)
        return {"ok": True, "pid": proc.pid}
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
    """解析 product 输出，失败清理标记，成功写 plan+phases 并移 backlog→planned。

    抽出供 check_product_async 共用：进程退出但 output 已生成也可走此路径。
    """
    import re as _re

    plan_match = _re.search(
        r"---PLAN---\s*\n?(.*?)\n?---END_PLAN---", output, _re.DOTALL
    )
    phases_match = _re.search(
        r"---PHASES---\s*\n?(.*?)\n?---END_PHASES---", output, _re.DOTALL
    )
    if not plan_match or not phases_match:
        # 保留证据，便于排障（不再静默丢掉 output）
        _out = output or ""
        # Claude CLI 在缺 AUTH_TOKEN/API_KEY（曾被 sanitized_env 误剥）时也会吐这句，
        # 并不等于用户必须跑 interactive /login；中转站场景优先查 env allowlist。
        _auth = (
            "Not logged in" in _out
            or "Please run /login" in _out
            or "not logged in" in _out.lower()
        )
        _err = (
            "auth: claude CLI rejected request "
            "(check ANTHROPIC_AUTH_TOKEN/API_KEY reach subprocess; not interactive /login)"
            if _auth
            else "output parse failed"
        )
        try:
            fb = get_workspace() / ".ccc" / "product_fallback"
            fb.mkdir(parents=True, exist_ok=True)
            (fb / f"{task_id}.last.out").write_text(_out, encoding="utf-8")
            (fb / f"{task_id}.failed").write_text(_err + "\n", encoding="utf-8")
        except OSError:
            pass
        _log.error(
            "[product-async] %s %s (saved product_fallback), mark failed",
            task_id,
            _err,
        )
        _cleanup_async_product_markers(pids_dir, task_id)
        return {
            "status": "failed",
            "error": _err,
            "fatal": bool(_auth),
        }

    plan_content = plan_match.group(1).strip()
    phases_data = []
    for line in phases_match.group(1).strip().split("\n"):
        line = line.strip()
        if line:
            try:
                phases_data.append(json.loads(line))
            except json.JSONDecodeError as exc:
                _log.error(
                    "[product-async] %s phases JSON parse error: %s", task_id, exc
                )
                _cleanup_async_product_markers(pids_dir, task_id)
                return {"status": "failed", "error": f"phases JSON parse: {exc}"}

    if len(phases_data) > _get_cfg().max_phases:
        _log.error(
            "[product-async] %s phases %d > max %d",
            task_id,
            len(phases_data),
            _get_cfg().max_phases,
        )
        _cleanup_async_product_markers(pids_dir, task_id)
        return {"status": "failed", "error": f"phases > max {_get_cfg().max_phases}"}

    # v0.38/v0.42: 与 sync product 对齐 — phase_lint + plan 验收硬门
    try:
        plan_content, phases_data = _gate_product_artifacts(
            plan_content, phases_data, log_prefix="[product-async]"
        )
    except RuntimeError as exc:
        _cleanup_async_product_markers(pids_dir, task_id)
        return {"status": "failed", "error": str(exc)}

    # 写 plan + phases 文件 + 移 backlog → planned
    _write_async_product_result(task_id, plan_content, phases_data)

    # 清理标记
    _cleanup_async_product_markers(pids_dir, task_id)

    _log.info("[product-async] %s ✓ plan+phases written", task_id)
    return {"status": "success"}


def _cleanup_async_product_markers(pids_dir: Path, task_id: str) -> None:
    """清理 product_role 异步标记文件"""
    for sfx in [".product.out", ".product.done", ".product.pid", ".product.prompt.md"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass


def _write_pass_verdict(task_id: str, reason: str) -> None:
    """写 Engine 门禁可读的 PASS verdict（红线 11）。"""
    verdict_dir = get_workspace() / ".ccc" / "verdicts"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    (verdict_dir / f"{task_id}.verdict.md").write_text(
        f"# {task_id} Verdict\n\n"
        f"**Verdict:** PASS\n\n"
        f"{reason}\n",
        encoding="utf-8",
    )


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


# ═══════════════════════════════════════════════════════════════
# v0.33: 异步 reviewer / tester / pytest（Popen + marker 文件）
# ═══════════════════════════════════════════════════════════════


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
                stderr=subprocess.PIPE,
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


def launch_tester_async(task_id: str, ws: Path) -> dict:
    """异步启动 tester 验证子进程。

    从 plan 提取验证命令，写入 shell 脚本后 Popen bash 执行。

    Returns: {"ok": True, "pid": int, "cmds": int}
             {"error": str}
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 1. 从 plan 提取验证命令
    plan_file = ws / ".ccc" / "plans" / f"{task_id}.plan.md"
    verify_commands = []
    if plan_file.exists():
        content = plan_file.read_text()
        in_verify = False
        for line in content.split("\n"):
            if line.startswith("## 验收") or line.startswith("## 验证"):
                in_verify = True
                continue
            if in_verify and line.startswith("## "):
                break
            if (
                in_verify
                and line.strip().startswith("- ")
                and not line.strip().startswith("- 不")
            ):
                cmd = line.strip()[2:].strip()
                verify_commands.append(cmd)

    # fallback: 没有验收项，跑 pytest
    if not verify_commands:
        verify_commands = [
            f"python3 -m pytest {ws / 'tests' / 'scripts'} -q --tb=line --timeout=60"
        ]

    # 强制 baseline
    has_pyproject = (ws / "pyproject.toml").exists()
    if has_pyproject and not any("pytest" in c for c in verify_commands):
        verify_commands.append(
            "python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
        )

    if not verify_commands:
        return {"error": "no verify commands (empty plan)"}

    # 2. 写入 shell 脚本
    script_lines = ["#!/bin/bash", "set -e"]
    for cmd in verify_commands:
        script_lines.append(cmd)
    script_content = "\n".join(script_lines) + "\n"

    script_file = pids_dir / f"{task_id}.tester.sh"
    script_file.write_text(script_content)
    script_file.chmod(0o700)

    # 3. 清理残留标记
    for sfx in [".tester.done", ".tester.exitcode", ".tester.out", ".tester.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass

    # 4. Popen bash script
    result_file = pids_dir / f"{task_id}.tester.out"
    exitcode_file = pids_dir / f"{task_id}.tester.exitcode"

    try:
        with open(result_file, "w") as out_f:
            proc = subprocess.Popen(
                ["bash", str(script_file)],
                stdout=out_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=ws,
                env=_sanitized_env(),
            )
        pids_dir.joinpath(f"{task_id}.tester.pid").write_text(str(proc.pid))
        _log.info(
            "[tester-async] %s launched PID=%d, %d commands",
            task_id,
            proc.pid,
            len(verify_commands),
        )
        return {"ok": True, "pid": proc.pid, "cmds": len(verify_commands)}
    except Exception as exc:
        _log.error("[tester-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def check_tester_async(task_id: str, ws: Path) -> dict:
    """检查异步 tester 是否完成。

    Returns:
        {"status": "pass"} — 所有验证通过
        {"status": "failed", "exit_code": int, "output": str} — 验证失败
        {"status": "running"} — 仍在执行
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.tester.done"
    exitcode_file = pids_dir / f"{task_id}.tester.exitcode"
    result_file = pids_dir / f"{task_id}.tester.out"
    pid_file = pids_dir / f"{task_id}.tester.pid"

    # 检查是否完成
    is_done = done_file.exists() or exitcode_file.exists()

    if not is_done:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running"}
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
        return {"status": "failed", "exit_code": -1, "output": "process exited"}

    if exitcode_file.exists():
        try:
            exit_code = int(exitcode_file.read_text().strip())
        except (ValueError, OSError):
            exit_code = -1
    else:
        exit_code = 0

    output = result_file.read_text() if result_file.exists() else ""

    # 清理标记
    _cleanup_tester_markers(pids_dir, task_id)

    if exit_code == 0:
        return {"status": "pass"}
    return {"status": "failed", "exit_code": exit_code, "output": output[:2000]}


def _cleanup_tester_markers(pids_dir: Path, task_id: str) -> None:
    """清理 tester async 标记文件"""
    for sfx in [
        ".tester.done",
        ".tester.exitcode",
        ".tester.out",
        ".tester.pid",
        ".tester.sh",
    ]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass


def launch_pytest_async(task_id: str, ws: Path) -> dict:
    """异步启动 pytest 子进程。

    Popen pytest tests/，engine 下个 tick 用 check_pytest_async() 检查。

    Returns: {"ok": True, "pid": int}
             {"error": str}
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)

    # 判断是否有 tests/ 目录
    tests_dir = ws / "tests"
    if not tests_dir.is_dir():
        return {"error": "no tests/ directory, skipping pytest"}

    # 构建 pytest 命令
    venv_pytest = ws / ".venv" / "bin" / "pytest"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "tests/", "-q", "--tb=line"]
    else:
        cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=line"]

    # 清理残留标记
    for sfx in [".pytest.done", ".pytest.exitcode", ".pytest.out", ".pytest.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass

    # Popen pytest
    result_file = pids_dir / f"{task_id}.pytest.out"
    exitcode_file = pids_dir / f"{task_id}.pytest.exitcode"

    try:
        with open(result_file, "w") as out_f:
            proc = subprocess.Popen(
                cmd,
                stdout=out_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=ws,
                env=_sanitized_env(),
            )
        pids_dir.joinpath(f"{task_id}.pytest.pid").write_text(str(proc.pid))
        _log.info("[pytest-async] %s launched PID=%d", task_id, proc.pid)
        return {"ok": True, "pid": proc.pid}
    except Exception as exc:
        _log.error("[pytest-async] %s launch failed: %s", task_id, exc)
        return {"error": str(exc)}


def check_pytest_async(task_id: str, ws: Path) -> dict:
    """检查异步 pytest 是否完成。

    Returns:
        {"status": "pass"} — pytest 通过
        {"status": "failed", "exit_code": int, "output": str} — pytest 失败
        {"status": "running"} — 仍在执行
        {"status": "skipped", "reason": str} — 无 tests/ 目录
    """
    task_id = sanitize_id(task_id)
    pids_dir = ws / ".ccc" / "pids"
    done_file = pids_dir / f"{task_id}.pytest.done"
    exitcode_file = pids_dir / f"{task_id}.pytest.exitcode"
    result_file = pids_dir / f"{task_id}.pytest.out"
    pid_file = pids_dir / f"{task_id}.pytest.pid"

    # 判断是否有 tests/ 目录（launch 时返回的错误，check 时检查）
    tests_dir = ws / "tests"
    if not tests_dir.is_dir():
        return {"status": "skipped", "reason": "no tests/ directory"}

    is_done = done_file.exists() or exitcode_file.exists()

    if not is_done:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                return {"status": "running"}
            except (ValueError, ProcessLookupError):
                pass
            except OSError:
                pass
        return {"status": "failed", "exit_code": -1, "output": "process exited"}

    if exitcode_file.exists():
        try:
            exit_code = int(exitcode_file.read_text().strip())
        except (ValueError, OSError):
            exit_code = -1
    else:
        exit_code = 0

    output = result_file.read_text() if result_file.exists() else ""

    # 清理标记
    _cleanup_pytest_markers(pids_dir, task_id)

    if exit_code == 0:
        return {"status": "pass"}
    return {"status": "failed", "exit_code": exit_code, "output": output[:2000]}


def _cleanup_pytest_markers(pids_dir: Path, task_id: str) -> None:
    """清理 pytest async 标记文件"""
    for sfx in [".pytest.done", ".pytest.exitcode", ".pytest.out", ".pytest.pid"]:
        f = pids_dir / f"{task_id}{sfx}"
        try:
            f.unlink()
        except OSError:
            pass


def dev_role() -> dict:
    """开发工程师: 查 in_progress（重试）→ 查 planned（新的）→ opencode 执行"""
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
                phases_file.write_text("\n".join(lines))
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
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
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
            ],
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

    relay = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
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


# v0.24.1: reviewer 按变更量分级阈值
REVIEW_SIZE_SMALL_MAX = 10  # ≤10 行 → small（跳过 LLM）
REVIEW_SIZE_MEDIUM_MAX = 50  # 11-50 行 → medium（标准 LLM）
# >50 行 → large（LLM + impact 分析）


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


def reviewer_role() -> dict:
    """代码审查员: 扫 testing → LLM 审查 git diff + plan 验收清单 → 通过则挪 verified

    v0.24.1: 按变更量分级
      - small (≤10 行): 跳过 LLM，仅 py_compile 静态检查
      - medium (10-50 行): 标准 LLM 审查
      - large (>50 行): LLM + impact 分析（影响面/风险等级）

    v0.24.5: 加 per-task advisory lock（A24-01 防并发 reviewer 实例写同 task 的 review.md）
    v0.24.5: medium/large fallback 路径强制 quarantine（A24-03/A24-04 防 v0.23 G2 bypass 复发）
    """
    moved = []
    lock_dir = get_workspace() / ".ccc" / "review-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
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

    # small 类：跳过 LLM，走 py_compile 静态检查（保留原逻辑）
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

        if py_files and _py_compile_fallback(task_id, py_files):
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
        elif not py_files:
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


def tester_role() -> dict:
    """测试工程师: 扫 testing → 按 plan 跑验证 → 通过则挪 verified"""
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        plan_file = get_workspace() / ".ccc" / "plans" / f"{task_id}.plan.md"
        verify_commands = []
        if plan_file.exists():
            content = plan_file.read_text()
            in_verify = False
            for line in content.split("\n"):
                if line.startswith("## 验收") or line.startswith("## 验证"):
                    in_verify = True
                    continue
                if in_verify and line.startswith("## "):
                    break
                if (
                    in_verify
                    and line.strip().startswith("- ")
                    and not line.strip().startswith("- 不")
                ):
                    cmd = line.strip()[2:].strip()
                    verify_commands.append(cmd)

        # fallback: 如果没有验收项，跑 pytest
        if not verify_commands:
            verify_commands = [
                f"python3 -m pytest {get_workspace() / 'tests' / 'scripts'} -q --tb=line --timeout=60"
            ]

        # 强制 baseline（v0.21.3）：项目有 tests/ 时追加 pytest + 覆盖率门槛
        has_pyproject = (get_workspace() / "pyproject.toml").exists()
        if has_pyproject and not any("pytest" in c for c in verify_commands):
            verify_commands.append(
                "python3 -m pytest tests/ -q --tb=line --timeout=60 --cov=src --cov-fail-under=80"
            )

        all_ok = True
        for cmd in verify_commands:
            if not all_ok:
                break
            r = sp.run(
                shlex.split(cmd),
                shell=False,
                capture_output=True,
                text=True,
                timeout=cfg.exec_timeout,
                cwd=get_workspace(),
            )
            if r.returncode != 0:
                all_ok = False
                _out = r.stdout[-300:] if isinstance(r.stdout, str) else r.stdout.decode("utf-8", errors="replace")[-300:] if r.stdout else ""
                _log.error(
                    "[tester] %s FAIL: %s... → %s",
                    task_id,
                    cmd[:80],
                    _out,
                )

        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            _log.info("[tester] %s ✓（验证 {len(verify_commands)} 项）", task_id)
    return {"role": "tester", "moved": moved, "counts": update_index()}


def ops_role() -> dict:
    """运维监控: 健康检查 + stale 检测 + 孤儿 PID 清理 + 告警"""
    health = {
        "opencode_pids": len(
            list((Path.home() / ".ccc" / "opencode-pids").glob("*.pid"))
        ),
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "git_ahead": 0,
        "stale_detected": 0,
        "orphan_pids_cleaned": 0,
    }

    # 1. Stale 检测：全非终态列（in_progress + testing + planned）→ 异常列
    # v0.31 (P4.1): 从仅 in_progress 扩大到全非终态，堵 testing/planned 静默死状态
    from datetime import datetime as _dt

    _STALE_COLUMNS = ["in_progress", "testing", "planned"]
    now = _dt.now(timezone.utc)
    for col in _STALE_COLUMNS:
        for task in list_tasks(col):
            # v0.34 (P4): 优先用 phase_last_advanced_ts（phase 粒度）, 其次 updated_at
            updated_str = task.get("phase_last_advanced_ts", task.get("updated_at", task.get("created_at", "")))
            if not updated_str:
                continue
            try:
                updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
                hours_stale = (now - updated).total_seconds() / 3600
                if hours_stale > MAX_STALE_HOURS:
                    _quarantine(
                        task["id"],
                        f"{col} 滞留 {hours_stale:.1f}h（阈值 {MAX_STALE_HOURS}h），自动隔离",
                    )
                    health["stale_detected"] += 1
                    _log.info(
                        f"[ops] stale: {task['id']} {col} 滞留 {hours_stale:.1f}h → abnormal"
                    )
            except (ValueError, TypeError) as e:
                _log.warning(
                    "ops stale timestamp parse failed for %s: %s", task.get("id"), e
                )
    pid_dir = get_workspace() / ".ccc" / "pids"
    if pid_dir.exists():
        for f in pid_dir.glob("*.pid"):
            try:
                pid = int(f.read_text().strip())
                os.kill(pid, 0)  # 检查进程是否存在
            except (ValueError, OSError, ProcessLookupError):
                stem = f.stem
                f.unlink()
                for suffix in [".done", ".exitcode", ".report.md", ".result.json"]:
                    extra = pid_dir.parent / "reports" / f"{stem}{suffix}"
                    if extra.exists():
                        extra.unlink(missing_ok=True)
                health["orphan_pids_cleaned"] += 1
                _log.info("[ops] 清理孤儿 PID: %s", stem)

    # 3. 检查 abnormal 列任务（上报 + v0.34 P6 自动归因）
    abnormal_tasks = list_tasks("abnormal")
    if abnormal_tasks:
        _log.info(f"[ops] ⚠ abnormal 列有 {len(abnormal_tasks)} 个任务需处理:")
        for t in abnormal_tasks:
            _log.info(f"  • {t['id']}: {t.get('note', '?')[:120]}")
            # v0.34 (P6.1): abnormal > 24h → 自动归因
            _ts_str = t.get("updated_at", t.get("created_at", ""))
            if _ts_str:
                try:
                    from datetime import datetime as _dt2, timezone as _tz2
                    _ts = _dt2.fromisoformat(_ts_str.replace("Z", "+00:00"))
                    if (now - _ts).total_seconds() > 86400:
                        _note = t.get("note", "")
                        try:
                            from _capability_evolver import analyze_failure
                            _rca = analyze_failure(t["id"], _note)
                            if _rca:
                                _log.info(
                                    f"[ops] auto-heal: {t['id']} → {_rca.get('pattern', '?')}"
                                )
                                # 追加分析建议到 note
                                t["note"] = _note + (
                                    f"\n[自动归因] pattern={_rca.get('pattern', '?')}"
                                    f"\n建议: {_rca.get('fix', '需人工')}"
                                )
                                # 原地重写 abnormal 列 task
                                _tp = get_workspace() / ".ccc" / "board" / "abnormal" / f"{t['id']}.jsonl"
                                if _tp.exists():
                                    _tp.write_text(
                                        json.dumps(t, ensure_ascii=False) + "\n"
                                    )
                                health["auto_healed"] = health.get("auto_healed", 0) + 1
                        except ImportError:
                            pass
                except (ValueError, TypeError):
                    pass
        health["abnormal_count"] = len(abnormal_tasks)

    # 4. git ahead check
    import subprocess as sp

    for proj in [
        get_workspace(),
        get_workspace().parent / "qx-observer",
        get_workspace().parent / "xianyu",
        get_workspace().parent / "projects" / "qx",
    ]:
        if (proj / ".git").exists():
            r = sp.run(
                ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                cwd=proj,
                timeout=10,
            )
            if r.returncode == 0:
                ahead = r.stdout.strip().split()[-1] if r.stdout.strip() else "0"
                health[f"ahead_{proj.name}"] = int(ahead)

    # 6. v0.34 (P6.3): 看板自平衡 — backlog 空 → audit 自动补；planned 堆积 > 5 → 限流
    _backlog_count = len(list_tasks("backlog"))
    _planned_count = len(list_tasks("planned"))
    if _backlog_count == 0:
        _log.info("[ops] backlog 空，自动触发 audit 补充")
        try:
            from _audit import run_audit
            run_audit(get_workspace())
            health["audit_refill"] = 1
        except ImportError:
            pass
    if _planned_count > 5:
        _log.info(f"[ops] planned 堆积（{_planned_count}），报告不阻塞")
        health["planned_pileup"] = _planned_count
    health["backlog_count"] = _backlog_count
    health["planned_count"] = _planned_count

    # 5. launchd 自检：检查 7 角色 plist 是否存活
    roles_check = ["product", "dev", "reviewer", "tester", "ops", "kb", "regress"]
    launchd_up = []
    for role in roles_check:
        r = sp.run(
            ["launchctl", "list", f"com.ccc.{role}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and "PID" in r.stdout:
            launchd_up.append(role)
        else:
            _log.info("[ops] ⚠ com.ccc.%s 未运行", role)
    health["launchd_up"] = launchd_up
    health["launchd_missing"] = [r for r in roles_check if r not in launchd_up]

    # 4.5 日志清理：删除 >30 天的 role 日志
    if (Path.home() / ".ccc" / "logs").exists():
        _now_ts = time.time()
        _cutoff = _now_ts - 30 * 86400
        for _lf in (Path.home() / ".ccc" / "logs").glob("role-*.log"):
            if _lf.stat().st_mtime < _cutoff:
                _lf.unlink(missing_ok=True)

    # 6. 指标收集 → .ccc/metrics.json
    pid_dir = get_workspace() / ".ccc" / "pids"
    metrics = {
        "updated_at": now_iso(),
        "tasks_in_flight": len(list_tasks("in_progress")) + len(list_tasks("testing")),
        "abnormal_count": len(list_tasks("abnormal")),
        "pids_count": len(list(pid_dir.glob("*.pid"))) if pid_dir.exists() else 0,
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "launchd_missing": health["launchd_missing"],
    }
    metrics_file = get_workspace() / ".ccc" / "metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")

    return {"role": "ops", "health": health}


def _extract_agents_suggestions(
    filepath: Path, task_id: str, source: str
) -> list[dict]:
    """从 report/verdict 文件中提取 AGENTS.md 建议"""
    import re

    suggestions = []
    if not filepath.exists():
        return suggestions
    content = filepath.read_text()
    # tempered dot: match content until blank line, ---, next marker, or end
    pattern = re.compile(
        r"> \*\*AGENTS\.md 建议:\*\*\s*((?:(?!> \*\*AGENTS\.md 建议:|\n\n|\n---).)*)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        text = match.group(1).strip()
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        if text:
            suggestions.append({"task_id": task_id, "source": source, "content": text})
    return suggestions


def kb_role() -> dict:
    """知识管理员: 扫 verified → 归档 + git tag → 挪 released → 收集 AGENTS.md 建议"""
    import subprocess as sp

    moved = []
    all_suggestions: list[dict] = []
    for task in list_tasks("verified"):
        task_id = task["id"]

        # ── Step 1: 版本 bump + CHANGELOG ──
        try:
            new_ver = _bump_version(get_workspace())
            _append_changelog(get_workspace(), task_id, new_ver)
        except Exception as exc:
            _log.warning("version bump failed, skipping tag: %s", exc)
            new_ver = "unknown"

        # ── Step 2: git tag v{version} ──
        if new_ver != "unknown":
            sp.run(
                [
                    "git",
                    "tag",
                    "-a",
                    new_ver,
                    "-m",
                    f"{new_ver}: {task_id} 发布",
                ],
                cwd=get_workspace(),
                capture_output=True,
                timeout=10,
            )
            push_r = sp.run(
                ["git", "push", "origin", new_ver],
                cwd=get_workspace(),
                capture_output=True,
                timeout=30,
            )
            if push_r.returncode != 0:
                # v0.38: push 失败不阻断本地 released（避免永久卡 verified）
                _log.error(
                    "[kb] %s push tag 失败 rc=%s（仍挪 released，本地 tag 已建）",
                    task_id,
                    push_r.returncode,
                )
                fail_log = (
                    get_workspace() / ".ccc" / "reports" / f"{task_id}.push-fail.md"
                )
                fail_log.write_text(
                    f"# {task_id} push tag 失败\n\n"
                    f"rc={push_r.returncode}\n"
                    f"{(push_r.stderr or b'').decode('utf-8', errors='replace')[:500]}\n"
                )

        # ── Step 3: 收集 AGENTS.md 建议 ──
        report_file = get_workspace() / ".ccc" / "reports" / f"{task_id}.report.md"
        all_suggestions.extend(
            _extract_agents_suggestions(report_file, task_id, source="dev")
        )
        verdict_file = get_workspace() / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
        all_suggestions.extend(
            _extract_agents_suggestions(verdict_file, task_id, source="reviewer")
        )

        # ── Step 4: 挪 released ──
        move_task(task_id, "verified", "released")
        moved.append(task_id)

    # 去重 → 写 pending-agents-suggestions.md
    if all_suggestions:
        seen: set[str] = set()
        unique: list[dict] = []
        for s in all_suggestions:
            key = s["content"].strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        pending_file = get_workspace() / ".ccc" / "pending-agents-suggestions.md"
        template_file = get_workspace() / "templates" / "pending-agents-suggestions.md"

        new_blocks: list[str] = []
        now_str = now_iso()[:10]
        for s in unique:
            block = (
                f"## 来源 task: {s['task_id']}\n\n"
                f"归档日期: {now_str}\n\n"
                f"### 来自 {s['source']}\n\n"
                f"{s['content']}\n\n"
                f"---\n"
            )
            new_blocks.append(block)

        new_content = "\n".join(new_blocks)
        if pending_file.exists():
            existing = pending_file.read_text().rstrip()
            pending_file.write_text(existing + "\n" + new_content + "\n")
        else:
            header = (
                template_file.read_text()
                if template_file.exists()
                else "# Pending AGENTS.md Suggestions\n\n"
            )
            pending_file.write_text(header + "\n" + new_content + "\n")
        _log.info("[kb] ✓ 收集 {len(unique)} 条 AGENTS.md 建议到 %s", pending_file)

    return {
        "role": "kb",
        "moved": moved,
        "suggestions_collected": len(all_suggestions),
        "counts": update_index(),
    }


# ═══════════════════════════════════════════
# audit 角色 (v0.22)
# ═══════════════════════════════════════════


WORKSPACES = cfg.audit_workspaces  # 复用 Config（v0.22 M7）


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


# ═══════════════════════════════════════════════════════════════
# v0.35 分级架构：任务分类 + auto/quick 路径 + intake failsafe
# ═══════════════════════════════════════════════════════════════

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


def _intake_failsafe(ws: Path, category: str) -> bool:
    """检查是否应该暂停 intake。返回 True = 允许投，False = 熔断。

    同类 audit-task 在 abnormal 占比 > 60% → 源头熔断。
    """
    from _board_store import FileBoardStore

    store = FileBoardStore(ws)
    prefix = f"audit-{category}"
    abnormal = store.list_tasks("abnormal")
    audit_abnormal = [t for t in abnormal if t.get("id", "").startswith(prefix)]

    # 统计所有同类 task（含 backlog+planned+in_progress+testing+abnormal）
    all_audit = list(audit_abnormal)
    for col in ("backlog", "planned", "in_progress", "testing"):
        all_audit.extend(
            t for t in store.list_tasks(col)
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


def _audit_post_backlog(workspace: str, items: list, category: str) -> int:
    """把 review/decision 类问题投到对应项目的 backlog。返回投出数。

    v0.40: 仅 control=invent 才允许投 backlog（enabled 为纯队列消费）。
    """
    from datetime import datetime as _dt

    try:
        from _ccc_control import may_invent

        if not may_invent():
            _log.info(
                "[audit] skip post backlog (%s×%d) — control≠invent",
                category,
                len(items),
            )
            return 0
    except ImportError:
        pass

    store = FileBoardStore(Path(workspace))
    date_str = _dt.now(timezone.utc).strftime("%Y%m%d-%H%M")
    now_iso_str = now_iso()
    posted = 0
    for i, item in enumerate(items):
        tid = sanitize_id(f"audit-{category}-{date_str}-{uuid.uuid4().hex[:8]}")
        title = item[:80]
        store.create_task(
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

    # v0.36/v0.37: evolve — 默认关闭（CCC_EVOLVE_ON_AUDIT=1 开启）
    # v0.40: 另需 control=invent
    evolve_results = []
    _invent_ok = False
    try:
        from _ccc_control import may_invent as _may_invent_fn

        _invent_ok = _may_invent_fn()
    except ImportError:
        _invent_ok = False
    if _invent_ok and getattr(cfg, "evolve_on_audit", False):
        for ws_target in targets:
            try:
                ev_result = _evolve_run_one(ws_target)
                evolve_results.append({"workspace": ws_target, **ev_result})
                if ev_result.get("posted", 0) > 0:
                    _log.info(
                        "[evolve] %s: posted %d findings to backlog",
                        Path(ws_target).name,
                        ev_result["posted"],
                    )
            except Exception as exc:
                _log.warning("[evolve] %s 异常: %s", ws_target, exc)
                evolve_results.append({"workspace": ws_target, "error": str(exc)})

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


def regress_role() -> dict:
    """回测工程师: 每日扫 released → py_compile + git diff → 发现回归→建 bug"""
    import subprocess as sp
    from datetime import date

    results = {"checked": 0, "passed": 0, "failed": 0, "regressions": []}
    tasks = list_tasks("released")
    if not tasks:
        return {"role": "regress", "info": "无已发布任务", "results": results}

    today = date.today().isoformat()
    scripts_dir = get_workspace() / "scripts"
    # v0.28.0 (N-004): scripts_dir 不存在时 rglob 返回空（不抛错）→ py_ok=True 假阳性。
    # 显式检查目录存在，缺失则降级：跳过 py_compile 标记 unknown，循环内按 unknown 处理。
    py_files: list[Path] = []
    py_check_available = False
    if scripts_dir.is_dir():
        py_files = list(scripts_dir.rglob("*.py"))
        py_check_available = True
    else:
        _log.warning(
            "regress: scripts_dir 不存在 (%s) — 跳过 py_compile 检查",
            scripts_dir,
        )

    # v0.28.0 (M-004): py_compile 是项目级检查，所有 .py 文件语法问题与 task 无关。
    # 提到循环外，只跑一次，结果在循环内复用。
    py_ok = True
    failed_py: list[Path] = []
    for py in py_files:
        r = sp.run(
            ["python3", "-m", "py_compile", str(py)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            py_ok = False
            failed_py.append(py)
    if not py_ok:
        _log.warning(
            "regress: 项目级 py_compile 失败 %d 个文件: %s",
            len(failed_py),
            [p.name for p in failed_py[:5]],
        )

    for task in tasks:
        tid = task["id"]
        results["checked"] += 1

        # 1. py_compile — 复用上面的项目级结果
        # v0.28.0 (N-004): scripts_dir 不存在时 py_check_available=False，
        # 跳过 py_compile 检查（task_py_ok=True 不归咎 task，但记 skipped_py_check）。
        task_py_ok = py_ok
        if not py_check_available:
            results.setdefault("skipped_py_check", 0)
            results["skipped_py_check"] += 1

        # 2. git diff 检查是否代码被意外改过
        diff_ok = True
        r = sp.run(
            ["git", "diff", "HEAD", "--stat"],
            cwd=get_workspace(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.stdout.strip():
            diff_ok = False

        if task_py_ok and diff_ok:
            results["passed"] += 1
            _log.info("[regress] ✓ %s", tid)
        else:
            results["failed"] += 1
            today_compact = date.today().strftime("%Y%m%d")
            bug_id = f"regression-{tid}-{today_compact}-{results['failed']}"
            bug_title = f"回归: {task.get('title', tid)} ({today})"
            bug_desc = f"原任务 {tid} 在 {today} 回测失败\n"
            if not task_py_ok:
                bug_desc += "- py_compile 失败：代码有语法错误\n"
            if not diff_ok:
                bug_desc += "- git diff 非空：代码有意外改动\n"
            create_task({"id": bug_id, "title": bug_title, "description": bug_desc})
            results["regressions"].append(bug_id)
            _log.info("[regress] ✗ %s → %s", tid, bug_id)
            # 把原任务移回 backlog 并加 regression 标签
            src_path = board_dir() / "released" / f"{tid}.jsonl"
            if src_path.exists():
                _lines = src_path.read_text().split("\n")
                for _i, _line in enumerate(_lines):
                    _ls = _line.strip()
                    if not _ls:
                        continue
                    try:
                        _obj = json.loads(_ls)
                        _tags = _obj.get("tags", [])
                        if "regression" not in _tags:
                            _tags.append("regression")
                        _obj["tags"] = _tags
                        _obj["updated_at"] = now_iso()
                        _lines[_i] = json.dumps(_obj, ensure_ascii=False)
                        break
                    except json.JSONDecodeError as e:
                        _log.warning(
                            "regress tag update JSON failed for %s: %s", tid, e
                        )
            move_task(tid, "released", "backlog")
            # macOS 桌面通知
            subprocess.run(
                [
                    "bash",
                    str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                    "L2",
                    bug_title,
                    bug_desc[:200],
                ],
                capture_output=True,
                timeout=10,
                env=_sanitized_env(),
            )

    # 写回测日报
    report_dir = get_workspace() / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"regression-{today}.md"
    report.write_text(
        f"# 回测日报 {today}\n\n"
        f"- 检查任务: {results['checked']}\n"
        f"- 通过: {results['passed']}\n"
        f"- 失败: {results['failed']}\n"
        f"- 新建回归 bug: {len(results['regressions'])}\n"
    )
    return {"role": "regress", "results": results, "report": str(report)}


def get_timeline(task_id: Optional[str] = None) -> list[dict]:
    """读取 timeline 事件（委托 FileBoardStore）"""
    return store.get_timeline(task_id)


def approve_agents() -> dict:
    """人类审批: 读 pending-agents-suggestions.md → 追加到 .ccc/AGENTS.md"""
    import re

    pending_file = get_workspace() / ".ccc" / "pending-agents-suggestions.md"
    if not pending_file.exists():
        msg = f"[approve-agents] 无待审批建议文件: {pending_file}"
        _log.info(msg)
        return {"role": "approve-agents", "approved": 0, "error": "no pending file"}

    content = pending_file.read_text()

    # 分割：migration_idx 之前是建议块，之后是迁移记录
    migration_idx = content.find("\n## 迁移记录")
    suggestions_text = content[:migration_idx] if migration_idx != -1 else content

    # 按 ## 来源 task: 分割每个建议块
    raw_blocks = re.split(r"\n(?=## 来源 task:)", suggestions_text)
    suggestions = []
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith("# Pending") or block.startswith("> "):
            continue

        task_m = re.search(r"## 来源 task:\s*(\S+)", block)
        source_m = re.search(r"### 来自\s+(\w+)", block)
        if not task_m or not source_m:
            continue
        task_id = task_m.group(1)
        source = source_m.group(1)

        # 提取 ### 来自 <source> 之后到 --- 之前的内容
        after_source = block.split(f"### 来自 {source}")[-1].strip()
        content_text = re.split(r"\n---|\n## ", after_source)[0].strip()
        if content_text:
            suggestions.append(
                {
                    "task_id": task_id,
                    "source": source,
                    "content": content_text,
                }
            )

    if not suggestions:
        _log.info("[approve-agents] 无新建议需审批")
        return {"role": "approve-agents", "approved": 0, "info": "nothing new"}

    # 写入/追加 .ccc/AGENTS.md
    agents_file = get_workspace() / ".ccc" / "AGENTS.md"
    if not agents_file.exists():
        template_file = get_workspace() / "templates" / "AGENTS.md"
        if template_file.exists():
            agents_content = template_file.read_text()
            profile_file = get_workspace() / ".ccc" / "profile.md"
            if profile_file.exists():
                pf = profile_file.read_text()
                name_m = re.search(r"项目名[：:]\s*(.+)", pf)
                if name_m:
                    agents_content = agents_content.replace(
                        "{{PROJECT_NAME}}", name_m.group(1).strip()
                    )
            agents_content = agents_content.replace("{{PROJECT_PATH}}", str(get_workspace()))
            agents_content = agents_content.replace(
                "{{PRIMARY_LANGUAGE}}", "Python+Bash"
            )
            agents_content = agents_content.replace("{{DATE}}", now_iso()[:10])
        else:
            agents_content = "# CCC Agent Guide\n"
        agents_file.write_text(agents_content + "\n\n## AGENTS.md 建议积累\n\n")
        _log.info("[approve-agents] 创建 %s", agents_file)

    existing = agents_file.read_text().rstrip()
    new_entries = []
    for s in suggestions:
        entry = f"### 来自 {s['source']} ({s['task_id']})\n\n{s['content']}\n"
        new_entries.append(entry)
    agents_file.write_text(existing + "\n" + "\n".join(new_entries) + "\n")

    # 从 pending 文件中移除已审批的建议块（保留 header + 迁移记录）
    now = now_iso()[:10]
    n = len(suggestions)
    # 提取 header（截止到第一个建议块之前）
    header_lines = []
    for line in content.split("\n"):
        if line.strip().startswith("## 来源 task:") or line.strip().startswith("---"):
            break
        header_lines.append(line)
    header = "\n".join(header_lines).rstrip()

    migration_line = f"| {now} | approve-agents | ✅ (已写入 {n} 条) | 自动审批 |\n"
    if migration_idx != -1:
        existing_migration = content[migration_idx:].rstrip()
        pending_file.write_text(
            header + "\n\n" + existing_migration + "\n" + migration_line
        )
    else:
        pending_file.write_text(
            header
            + "\n\n## 迁移记录\n\n"
            + "| 日期 | 迁移人 | 写入 AGENTS.md? | 备注 |\n"
            + "|------|--------|----------------|------|\n"
            + migration_line
        )

    _log.info("[approve-agents] ✓ %s 条建议已写入 %s", n, agents_file)
    return {"role": "approve-agents", "approved": n, "file": str(agents_file)}


# v0.28.0 (F-4): 自动 approve-agents — 7 天冷却 + 重复检测 + 自动合入 .ccc/AGENTS.md
# 与原 approve_agents 区别：
# - 不需要人工触发（engine 自动调）
# - 7 天冷却：同一 task_id 7 天内已合入过 → 跳过
# - 重复检测：同一 source 的同一句建议已存在 → 跳过
# - 安全门：单次最多合入 10 条（防止 backlog 爆炸时一次写太多）
_AUTO_APPROVE_COOLDOWN_FILE = ".ccc/.auto-approve-cooldown.json"
_AUTO_APPROVE_COOLDOWN_DAYS = 7
_AUTO_APPROVE_MAX_PER_RUN = 10


def auto_approve_agents() -> dict:
    """v0.28.0 (F-4): engine idle 时自动跑 approve-agents。

    与原 approve_agents() 的差异：
    - 不需要人工触发（engine kb_role 完成后自动调）
    - 7 天冷却：同 task_id 7 天内已合入 → 跳过（防重复）
    - 重复检测：AGENTS.md 内已有同 source 的同一句建议 → 跳过
    - 单次最多 10 条（防 backlog 爆炸时一次写太多）
    - 不替代人工 approve-agents：原函数保留（红线 18 风格）
    """
    import re
    import json as _json

    pending_file = get_workspace() / ".ccc" / "pending-agents-suggestions.md"
    if not pending_file.exists():
        return {"role": "auto-approve-agents", "approved": 0, "info": "no pending file"}

    # 读冷却文件
    cooldown_file = get_workspace() / _AUTO_APPROVE_COOLDOWN_FILE
    cooldown: dict[str, str] = {}  # task_id → last_approved_date
    if cooldown_file.exists():
        try:
            cooldown = _json.loads(cooldown_file.read_text())
        except (OSError, _json.JSONDecodeError):
            cooldown = {}

    # 当前日期（ISO 短）
    today = now_iso()[:10]

    # 读 AGENTS.md 用于重复检测
    agents_file = get_workspace() / ".ccc" / "AGENTS.md"
    existing_text = agents_file.read_text() if agents_file.exists() else ""

    content = pending_file.read_text()
    migration_idx = content.find("\n## 迁移记录")
    suggestions_text = content[:migration_idx] if migration_idx != -1 else content

    raw_blocks = re.split(r"\n(?=## 来源 task:)", suggestions_text)
    candidates = []
    skipped_cooldown = 0
    skipped_dup = 0
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith("# Pending") or block.startswith("> "):
            continue
        task_m = re.search(r"## 来源 task:\s*(\S+)", block)
        source_m = re.search(r"### 来自\s+(\w+)", block)
        if not task_m or not source_m:
            continue
        task_id = task_m.group(1)
        source = source_m.group(1)
        # 7 天冷却检查
        last = cooldown.get(task_id)
        if last:
            try:
                from datetime import datetime as _dt

                last_d = _dt.fromisoformat(last)
                today_d = _dt.fromisoformat(today)
                if (today_d - last_d).days < _AUTO_APPROVE_COOLDOWN_DAYS:
                    skipped_cooldown += 1
                    continue
            except ValueError as e:
                _log.warning(
                    "auto_approve cooldown parse failed for %s: %s", task_id, e
                )
        after_source = block.split(f"### 来自 {source}")[-1].strip()
        content_text = re.split(r"\n---|\n## ", after_source)[0].strip()
        if not content_text:
            continue
        # v0.28.0 (F4-H1 修): 用 sha256(content) 指纹做重复检测
        # 旧实现 "sig = '### 来自 {source}' + content[:100]" 有 false-negative：
        # AGENTS.md 实际写为 "### 来自 {source} ({task_id})" 跟 sig 字面不同
        # → 即使内容 100% 重复也检测不到
        import hashlib

        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
        # 标记已写入过的 hash 进 AGENTS.md 时同时写 <!-- @hash:xxx --> 注释
        # 这里反向检查：现有 AGENTS.md 里是否含此 hash 标记
        hash_marker = f"<!-- @hash:{content_hash} -->"
        if hash_marker in existing_text:
            skipped_dup += 1
            continue
        # v0.28.0 (F4-M3 修): hash 注释被手动编辑破坏时的 fallback
        # 用 content 前 100 字符做子串检查，避免重复合入
        if content_text[:100] in existing_text:
            skipped_dup += 1
            continue
        candidates.append(
            {
                "task_id": task_id,
                "source": source,
                "content": content_text,
                "content_hash": content_hash,
            }
        )
        if len(candidates) >= cfg.auto_approve_max_per_run:
            break

    if not candidates:
        _log.info(
            "[auto-approve-agents] 无新建议（cooldown=%d, dup=%d）",
            skipped_cooldown,
            skipped_dup,
        )
        return {
            "role": "auto-approve-agents",
            "approved": 0,
            "skipped_cooldown": skipped_cooldown,
            "skipped_dup": skipped_dup,
        }

    # 创建 AGENTS.md（如不存在）
    if not agents_file.exists():
        template_file = get_workspace() / "templates" / "AGENTS.md"
        agents_content = (
            template_file.read_text()
            if template_file.exists()
            else "# CCC Agent Guide\n"
        )
        agents_file.write_text(agents_content + "\n\n## AGENTS.md 建议积累\n\n")
        _log.info("[auto-approve-agents] 创建 %s", agents_file)

    # v0.28.0 (F4-H3 修): 事务顺序倒过来
    # 1) 先写 cooldown（防 AGENTS.md 已写但 cooldown 漏写导致下轮重复合入）
    # 2) 再写 AGENTS.md
    # 3) 任何中间步失败 → 抛错外层（exit），cooldown 仍在
    new_entries = []
    approved_tasks: list[str] = []
    for s in candidates:
        # v0.28.0 (F4-H1 修): entry 末尾加 sha256 注释，供下次重复检测
        entry = (
            f"### 来自 {s['source']} ({s['task_id']})\n\n"
            f"{s['content']}\n"
            f"<!-- @hash:{s['content_hash']} -->\n"
        )
        new_entries.append(entry)
        approved_tasks.append(s["task_id"])

    # Step 1: 写 cooldown（先）
    for tid in approved_tasks:
        cooldown[tid] = today
    try:
        cooldown_file.write_text(
            _json.dumps(cooldown, indent=2, ensure_ascii=False, sort_keys=True)
        )
    except OSError as exc:
        # cooldown 写失败 → 不能继续写 AGENTS.md（下轮会重复合入）
        _log.error(
            "cooldown 写入失败: %s — 不写 AGENTS.md，下次重试",
            exc,
        )
        return {
            "role": "auto-approve-agents",
            "approved": 0,
            "error": f"cooldown write failed: {exc}",
        }

    # Step 2: 写 AGENTS.md
    try:
        existing_text = agents_file.read_text().rstrip()
        agents_file.write_text(existing_text + "\n" + "\n".join(new_entries) + "\n")
    except OSError as exc:
        _log.error("AGENTS.md 写入失败: %s — 已写 cooldown，下次重试会跳过", exc)
        return {
            "role": "auto-approve-agents",
            "approved": 0,
            "approved_task_ids": approved_tasks,
            "error": f"AGENTS.md write failed: {exc}",
        }

    # 写 pending-agents-suggestions.md 迁移记录
    n = len(candidates)
    header_lines = []
    for line in content.split("\n"):
        if line.strip().startswith("## 来源 task:") or line.strip().startswith("---"):
            break
        header_lines.append(line)
    header = "\n".join(header_lines).rstrip()
    migration_line = (
        f"| {today} | auto-approve-agents | ✅ (已写入 {n} 条, "
        f"cooldown={skipped_cooldown}, dup={skipped_dup}) | 7 天冷却 |\n"
    )
    if migration_idx != -1:
        existing_migration = content[migration_idx:].rstrip()
        pending_file.write_text(
            header + "\n\n" + existing_migration + "\n" + migration_line
        )
    else:
        pending_file.write_text(
            header
            + "\n\n## 迁移记录\n\n"
            + "| 日期 | 迁移人 | 写入 AGENTS.md? | 备注 |\n"
            + "|------|--------|----------------|------|\n"
            + migration_line
        )

    _log.info(
        "[auto-approve-agents] ✓ %s 条建议已写入 %s (cooldown=%d, dup=%d)",
        n,
        agents_file,
        skipped_cooldown,
        skipped_dup,
    )
    return {
        "role": "auto-approve-agents",
        "approved": n,
        "skipped_cooldown": skipped_cooldown,
        "skipped_dup": skipped_dup,
        "file": str(agents_file),
    }


# ═══════════════════════════════════════════
# 引擎辅助函数 (v0.20.1)
# ═══════════════════════════════════════════


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
    """统一 launch/relaunch 的 OpenCode prompt（scope + pytest 回灌）。"""
    return build_dev_phase_prompt(
        task_id,
        phase_num,
        plan_content,
        scope=_phase_scope(task_id, phase_num),
        pytest_failure=_read_pytest_failure_feedback(task_id),
        skill_hints=_task_skill_hints_block(task_id),
    )



def _task_pre_head_path(task_id: str) -> Path:
    return get_workspace() / ".ccc" / "pids" / f"{task_id}.pre_head"


def _capture_task_pre_head(task_id: str) -> str:
    """Launch 时记录 HEAD，供过 testing 前对比（H1）。"""
    import subprocess as _sp

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
    return head


def _find_task_commit_hash(task_id: str) -> str:
    """仅认 git log --grep=task_id；禁止 HEAD 降级（H1）。"""
    import subprocess as _sp

    try:
        r = _sp.run(
            [
                "git",
                "log",
                "--all",
                "--grep",
                task_id,
                "--format=%H",
                "--max-count=1",
            ],
            cwd=get_workspace(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            h = (r.stdout or "").strip().splitlines()
            if h and len(h[0]) == 40:
                return h[0]
    except Exception as exc:
        _log.warning("[commit-gate] %s git log grep failed: %s", task_id, exc)
    return ""


def _require_task_commit_for_testing(task_id: str) -> tuple[bool, str, str]:
    """过 testing 前必须有含 task_id 的新 commit。

    Returns: (ok, reason, commit_hash)
    """
    if (os.environ.get("CCC_SKIP_COMMIT_GATE") or "").strip() in ("1", "true", "yes"):
        return True, "skip", ""
    commit = _find_task_commit_hash(task_id)
    if not commit:
        return (
            False,
            "no git commit whose message contains task_id "
            f"(refuse HEAD fallback; task={task_id})",
            "",
        )
    pre_path = _task_pre_head_path(task_id)
    pre = ""
    if pre_path.is_file():
        try:
            pre = pre_path.read_text(encoding="utf-8").strip()
        except OSError:
            pre = ""
    if pre and commit == pre:
        return (
            False,
            f"task commit {commit[:12]} equals pre_head — no new commit for {task_id}",
            commit,
        )
    return True, "ok", commit



def dev_role_launch(task_id: str) -> dict:
    """引擎用：启 opencode 执行 task，返回启动结果

    1. 确认 task 在 planned，有 plan+phases
    2. 挪 planned → in_progress
    3. 启 opencode-runner.sh（后台进程）
    4. 不等待，立即返回
    """

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

        # v0.37: SELF-CHECKS 门禁 — 保留 agent report；无 report 时写 stub 并标记通过
        # （exit_code=0 + result.json≥50 已验证）
        if _existing_report:
            _report_body = _existing_report
            if "ALL SELF-CHECKS PASSED" not in _report_body:
                _log.warning(
                    "[gate] %s report.md 缺少 'ALL SELF-CHECKS PASSED'，"
                    "但 exit_code=0 且 result 充足 → 放行并补记",
                    task_id,
                )
                report_path.write_text(
                    _report_body.rstrip() + "\n\nALL SELF-CHECKS PASSED\n"
                )
        else:
            report_path.write_text(
                f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
                f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n\n"
                f"ALL SELF-CHECKS PASSED\n"
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


ROLES = {
    "product": product_role,
    "dev": dev_role,
    "reviewer": reviewer_role,
    "tester": tester_role,
    "ops": ops_role,
    "kb": kb_role,
    "regress": regress_role,
    "approve-agents": approve_agents,
}


def batch_process(lines: list[dict]) -> dict:
    """批量处理 create/move 操作

    每行格式:
      {"action":"create","id":"...","title":"...","column":"backlog",...}
      {"action":"move","id":"...","from":"backlog","to":"planned"}
    """
    results: dict = {"created": [], "moved": [], "errors": []}
    for i, op in enumerate(lines):
        action = op.get("action", "")
        task_id = op.get("id", "")
        try:
            if action == "create":
                column = op.get("column", "backlog")
                ok = create_task(op, column=column)
                if ok:
                    results["created"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "create failed"}
                    )
            elif action == "move":
                from_col = op.get("from", "")
                to_col = op.get("to", "")
                if not from_col or not to_col:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "missing from/to"}
                    )
                    continue
                ok = move_task(task_id, from_col, to_col)
                if ok:
                    results["moved"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "move failed"}
                    )
            else:
                results["errors"].append(
                    {"line": i, "id": task_id, "error": f"unknown action '{action}'"}
                )
        except Exception as e:  # debug
            results["errors"].append({"line": i, "id": task_id, "error": str(e)})
    results["counts"] = update_index()
    return results


def main():
    ap = argparse.ArgumentParser(description="CCC 任务看板 7 角色核心")
    ap.add_argument(
        "role",
        nargs="?",
        choices=list(ROLES.keys()) + ["index", "audit"],
        help="角色名 或 'index'",
    )
    ap.add_argument(
        "--batch", action="store_true", help="批量模式（从 stdin 读 JSONL）"
    )
    ap.add_argument("--file", type=str, help="批量模式输入文件（替代 stdin）")
    ap.add_argument(
        "--promote",
        type=str,
        help="product: 处理指定 backlog task → 写 plan/phases → 挪 planned",
    )
    ap.add_argument("--json", action="store_true", help="JSON 输出（角色模式下）")
    args = ap.parse_args()

    if args.batch:
        fp = open(args.file) if args.file else sys.stdin
        lines = []
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError as e:
                _log.error("[board] batch skip invalid JSON: %s", e)
        if args.file:
            fp.close()
        result = batch_process(lines)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.role == "index":
        print(json.dumps(update_index(), indent=2, ensure_ascii=False))
        return

    if args.role == "audit":
        result = audit_role()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.role:
        ap.print_help()
        sys.exit(1)

    if args.promote:
        if args.role != "product":
            _log.error("[board] --promote 仅适用于 product 角色")
            sys.exit(1)
        result = product_role(task_id=args.promote)
    else:
        result = ROLES[args.role]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _bump_version(ws_path: Path) -> str:
    """读取 VERSION 文件，bump patch version，写回。返回新版本号。"""
    version_file = ws_path / "VERSION"
    if not version_file.exists():
        new_version = "v0.0.1"
        version_file.write_text(new_version)
        return new_version
    current = version_file.read_text().strip()
    m = re.match(r"^(v?)(\d+)\.(\d+)\.(\d+)$", current, re.IGNORECASE)
    if not m:
        return current
    prefix = m.group(1) or "v"
    major, minor, patch = int(m.group(2)), int(m.group(3)), int(m.group(4))
    new_version = f"{prefix}{major}.{minor}.{patch + 1}"
    version_file.write_text(new_version)
    return new_version


def _append_changelog(ws_path: Path, tid: str, new_version: str) -> None:
    """在 CHANGELOG.md 最旧版本条目之上插入新条目。"""
    changelog_path = ws_path / "CHANGELOG.md"
    today_str = now_iso()[:10]
    entry = f"\n## [{new_version}] — {today_str}\n\n- {tid}: 看板发布\n"
    if changelog_path.exists():
        text = changelog_path.read_text()
    else:
        text = "# Changelog — CCC\n\n"
    # 在最旧 ## [v...] 条目之上插入（第一个版本标题之后）
    m = re.search(r"\n## \[v", text)
    if m:
        insert_at = m.start()
        new_text = text[:insert_at] + entry + text[insert_at:]
    else:
        new_text = text.rstrip() + entry + "\n"
    if tid in new_text and new_version in text:
        return
    changelog_path.write_text(new_text)
    # git commit VERSION + CHANGELOG（仅有改动时）
    try:
        check = subprocess.run(
            ["git", "diff", "--quiet", "VERSION", "CHANGELOG.md"],
            cwd=ws_path,
            capture_output=True,
            env=_sanitized_env(),
        )
        if check.returncode != 0:
            subprocess.run(
                ["git", "add", "VERSION", "CHANGELOG.md"],
                cwd=ws_path,
                capture_output=True,
                timeout=10,
                env=_sanitized_env(),
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"chore: bump {new_version} ({tid})",
                ],
                cwd=ws_path,
                capture_output=True,
                timeout=30,
                env=_sanitized_env(),
            )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("changelog git commit failed (non-blocking): %s", exc)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
