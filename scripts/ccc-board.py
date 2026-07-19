#!/usr/bin/env python3
"""ccc-board.py — 看板 CLI + 兼容再导出（角色实现已下沉）

角色实现：scripts/board/roles/{product,dev,reviewer,tester,ops,kb,audit,regress}.py
调度：scripts/ccc-engine.py + scripts/engine/
文档：docs/architecture-core.md

本文件保留公开 API re-export（CLI / 旧 importlib 加载），勿新增长角色逻辑。
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
    ccc_home,
)
from board.lock import (
    acquire_named_lock as _acquire_product_lock,
    release_named_lock as _release_product_lock,
)
from board.prompt import (
    build_dev_phase_prompt,
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
    _load_phases,
    _resolve_phase_dependencies,
    _apply_phase_status_updates,
    _current_running_phase,
    _mark_phase_done,
    _mark_phase_failed,
    _check_phase_failures,
    _move_task_to_abnormal_if_all_terminal_failed,
)

from _claude_cli import ClaudeCliMissing, resolve_claude_cli

# ── Role implementations live in board.roles.* (re-export for CLI / importlib) ──
from board.roles.common import (  # noqa: E402,F401
    cfg,
    store,
    CCC_HOME,
    MAX_RETRY,
    MAX_STALE_HOURS,
    WORKSPACES,
    sanitize_id,
    now_iso,
    _quarantine,
    _task_id_exists,
    create_task,
    list_tasks,
    move_task,
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
)
from board.roles.common import _write_pass_verdict  # noqa: E402,F401
from board.roles.product import (  # noqa: E402,F401
    product_role,
    launch_product_async,
    check_product_async,
    _get_code_context,
    _load_plan_template,
    _parse_and_finalize_product,
)
from board.roles.dev import (  # noqa: E402,F401
    dev_role,
    dev_role_launch,
    dev_role_relaunch,
    dev_role_check_complete,
    _compose_dev_prompt,
)
from board.roles.reviewer import (  # noqa: E402,F401
    reviewer_role,
    launch_reviewer_async,
    check_reviewer_async,
    clear_stale_review_locks,
    _parse_diff_size,
    _classify_review_size,
    _review_one_task,
)
from board.roles.tester import (  # noqa: E402,F401
    tester_role,
    launch_tester_async,
    check_tester_async,
    launch_pytest_async,
    check_pytest_async,
)
from board.roles.ops import ops_role  # noqa: E402,F401
from board.roles.kb import kb_role, _extract_agents_suggestions  # noqa: E402,F401
from board.roles.audit import (  # noqa: E402,F401
    audit_role,
    _audit_post_backlog,
    _audit_classify,
    _audit_recent_commits,
)
from board.roles.regress import regress_role  # noqa: E402,F401


def _claude_bin() -> str:
    """运行时解析 claude 绝对路径（禁止 import-time 冻死）。"""
    return resolve_claude_cli(require=True)


def _get_relay_url() -> str:
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


# v0.28.0 (M-002): 模块级缓存 = {path: (result, ts)} — 300s TTL 过期
_GET_CODE_CONTEXT_TTL_S = 300.0
_get_code_context_cache: dict[str, tuple[str, float]] = {}


# ═══════════════════════════════════════════════════════════════
# v0.33: product_role 异步化（Popen + marker 文件）
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# v0.33: 异步 reviewer / tester / pytest（Popen + marker 文件）
# ═══════════════════════════════════════════════════════════════


# v0.24.1: reviewer 按变更量分级阈值
REVIEW_SIZE_SMALL_MAX = 10  # ≤10 行 → small（跳过 LLM）
REVIEW_SIZE_MEDIUM_MAX = 50  # 11-50 行 → medium（标准 LLM）
# >50 行 → large（LLM + impact 分析）


# ═══════════════════════════════════════════
# audit 角色 (v0.22)
# ═══════════════════════════════════════════


WORKSPACES = cfg.audit_workspaces  # 复用 Config（v0.22 M7）


# ═══════════════════════════════════════════════════════════════
# v0.35 分级架构：任务分类 + auto/quick 路径 + intake failsafe
# ═══════════════════════════════════════════════════════════════


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
        _store_atomic_write(
            cooldown_file,
            _json.dumps(cooldown, indent=2, ensure_ascii=False, sort_keys=True),
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
        _store_atomic_write(
            agents_file, existing_text + "\n" + "\n".join(new_entries) + "\n"
        )
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
