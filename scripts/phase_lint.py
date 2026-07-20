#!/usr/bin/env python3
"""phase_lint.py — phases.jsonl schema 校验（v0.28.0）

功能：
1. 校验 phases.jsonl 的 schema_version（v1.1 / v1.2 兼容）
2. 校验 phase 结构（phase_id / status / subtasks / timeout / commit_message）
3. 校验流程规则（no cycle dependency / all phases addressable / no orphan subtasks）
4. 输出修复建议（已知修复按钮等）

使用：
    python3 scripts/phase_lint.py <task_id> [--fix]
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

from _config import get_logger

_log = get_logger("phase-lint")

_ACCEPTANCE_ITEM_RE = re.compile(
    r"^\s*(?:[-*]|\d+[.)])\s+\S+"
)
_ALL_SCOPE_TOKENS = {"all", "*"}


phases_schema_version = "1.2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="v0.28.0 phases.jsonl 校验工具")
    parser.add_argument("task_id", help="task_id")
    parser.add_argument("--fix", action="store_true", help="自动修复常见问题")
    return parser.parse_args()


def load_phases(task_id: str, ws: Path = Path.cwd()) -> List[dict]:
    phases_file = ws / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not phases_file.exists():
        print(f"[phase_lint] phases.jsonl 不存在: {phases_file}", file=sys.stderr)
        return []
    try:
        with open(phases_file) as f:
            phases = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict) and "schema_version" in obj:
                    continue  # 跳过 metadata 行
                phases.append(obj)
        return phases
    except json.JSONDecodeError as e:
        _log.error("phases.jsonl JSON 解析失败: %s", e)
        return []


def validate_schema_version(
    phases: List[dict], task_id: str, fix: bool = False
) -> Tuple[bool, List[str]]:
    """校验 schema_version（兼容 v1.0 / v1.1）"""
    errors = []
    phases_file = Path.cwd() / ".ccc" / "phases" / f"{task_id}.phases.json"

    for line_idx, phase in enumerate(phases, start=1):
        if "schema_version" in phase:
            errors.append(
                f"phase {phase.get('phase', '?')}: "
                "phase 返回类型混淆（schema_version 不应出现在 phase 行中）"
            )

            if fix:
                # 修复：把 schema_version 当初一个 phase 删除，并在头部写入 metadata row
                with open(phases_file, "r+") as f:
                    # v0.29: 在 try 前读取 content，使 except 分支也可用（C1）
                    content = f.readlines()
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    except (OSError, AttributeError) as e:
                        _log.warning("flock lock failed: %s", e)
                        metadata_line = (
                            json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
                            + "\n"
                        )
                        del content[line_idx - 1]
                        content.insert(0, metadata_line)
                        f.seek(0)
                        f.truncate()
                        f.writelines(content)
                    finally:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except (OSError, AttributeError) as e:
                            _log.warning("flock unlock failed: %s", e)
    return (len(errors) == 0), errors


def validate_phase_structure(phases: List[dict]) -> Tuple[bool, List[str]]:
    """校验 phase 结构字段（phase / phase_id / status / subtasks / timeout / commit_message / notes）"""
    errors = []
    allowed_fields = {
        "phase",
        "phase_id",
        "status",
        "depends_on",
        "description",
        "expected_duration",
        "estimated_minutes",
        "files_touched",
        "verification_cmd",
        "executor",
        "subtasks",
        "scope",
        "allow_all_scope",
        "commit_message",
        "commit",
        "notes",
        "timeout",
        "retry",
        "run_strategy",
        "engine_iter",
        "engine_iter_phase",
    }

    for p in phases:
        pid_val = p.get("phase")
        if pid_val is None:
            errors.append(
                f"phase 缺少 field: phase (phase_id={p.get('phase_id', '?')})"
            )
            continue

        pid_int: int = int(pid_val)

        # 检查 phase_id 是否与 phase 一致（v0.28.0 A01）
        pid_from_id = p.get("phase_id", str(pid_val))
        try:
            if pid_from_id != str(pid_val) and pid_int != int(pid_from_id):
                errors.append(
                    f"phase_id 与 phase 不一致: phase_id={pid_from_id!r} phase={pid_val}"
                )
        except (ValueError, TypeError):
            errors.append(
                f"phase 不一致（类型）: phase_id={pid_from_id!r} phase={pid_val}"
            )

        subtasks = p.get("subtasks", {})
        if not isinstance(subtasks, dict):
            errors.append(
                f"phase {pid_val}: subtasks 应为 dict，got {type(subtasks).__name__}"
            )
        elif (
            subtasks
            and "1.1" not in subtasks
            and "unknown" not in p.get("notes", "").lower()
        ):
            has_known_subtask = any(
                k not in {"1", "2", "3", "unknown"}
                for k in subtasks.keys()
                if str(k).startswith(str(pid_val))
            )
            if not has_known_subtask and p.get("status") != "pending":
                errors.append(f"phase {pid_val}: subtasks 未序列化（可能格式错误）")

        allowed_keys = set(p.keys())
        unknown = allowed_keys - allowed_fields
        if unknown:
            errors.append(f"phase {pid_val}: 未知字段 {unknown}")

    processed = 0
    last_status = None
    for p in phases:
        pid_val = p.get("phase")
        if pid_val is None:
            continue
        current = p.get("status", "pending")
        if last_status is not None and processed > 0:
            if last_status not in {
                "done",
                "verified",
                "failed",
                "skipped",
            } and current in {"done", "verified", "failed", "skipped"}:
                errors.append(
                    f"phase {pid_val}: 状态从 {last_status} 跳到 {current}（应逐步推进）"
                )
        last_status = current
        processed += 1

    return (len(errors) == 0), errors


def validate_no_cycle_dependencies(phases: List[dict]) -> Tuple[bool, List[str]]:
    """循环依赖检测（v0.25.1 原型，v0.28.0 利用）"""
    errors = []
    by_id: Dict[int, dict] = {
        p.get("phase"): p for p in phases if p.get("phase") is not None
    }
    visited: Set[int] = set()
    rec_stack: Set[int] = set()

    def dfs(pid: int, path: List[int]) -> List[int]:
        if pid in rec_stack:
            return path + [pid]
        if pid in visited:
            return []
        visited.add(pid)
        rec_stack.add(pid)
        path.append(pid)

        for dep_id in by_id.get(pid, {}).get("depends_on") or []:
            if dep_id in by_id:
                cycle = dfs(dep_id, path.copy())
                if cycle:
                    return cycle
        rec_stack.remove(pid)
        return []

    for pid in list(by_id.keys()):
        cycle = dfs(pid, [])
        if cycle:
            cycle_str = " → ".join(str(p) for p in cycle)
            errors.append(f"循环依赖: {cycle_str}")

    return (len(errors) == 0), errors


# ═══════════════════════════════════════════
# v0.28.0 新校验：executor / empty phase / schema v1.2 字段
# ═══════════════════════════════════════════

KNOWN_EXECUTORS = {"opencode", "skip", "manual", "dev", "reviewer", "tester", "kb", "ops", "product", "regress"}
"""已知 executor 白名单。phase 的 executor 字段应在此集合中。"""

EXECUTABLE_CMD_PREFIXES = ("pytest", "python -m", "python3 -m", "bash", "make", "node", "grep", "python3 -c", "python3 ", "python -c", "shellcheck", "ruff", "mypy")
"""verification_cmd 可执行命令前缀白名单。"""

VALID_SCHEMA_VERSIONS = {"1.0", "1.1", "1.2"}
"""已知 schema_version 值。"""


def validate_executor(phases: List[dict]) -> Tuple[bool, List[str]]:
    """校验每个 phase 的 executor 字段是否在白名单内。

    修复建议：
    - 未知 executor → warning（不阻断 dev 执行）
    - 空 executor → 视为默认 "opencode"
    - skip 状态但未注明原因 → warning
    """
    errors = []
    for p in phases:
        pid = p.get("phase")
        executor = p.get("executor")
        if executor is None:
            continue  # 不设 executor = 默认 opencode
        if executor not in KNOWN_EXECUTORS:
            errors.append(
                f"phase {pid}: 未知 executor={executor!r}"
                f"（已知: {', '.join(sorted(KNOWN_EXECUTORS))}）"
            )
        elif executor == "skip" and not p.get("notes", "").strip() and not p.get("description", "").strip():
            errors.append(
                f"phase {pid}: executor=skip 但无说明（description 或 notes 必须注明跳过原因）"
            )
    return (len(errors) == 0), errors


def validate_empty_phase(phases: List[dict]) -> Tuple[bool, List[str]]:
    """检测空白/空 phase。

    空白定义：
    - 没有 description 且没有 files_touched 且没有 subtasks → 空白
    - status 为 skip 但没有任何说明 → 空白/无效 skip
    - status 为 pending 但无 description 无一技之长 → 空白
    """
    errors = []
    for p in phases:
        pid = p.get("phase")
        desc = (p.get("description") or "").strip()
        ft = p.get("files_touched") or []
        subs = (p.get("subtasks") or {})
        notes = (p.get("notes") or "").strip()

        # 空白 phase
        if not desc and not ft and not subs:
            errors.append(
                f"phase {pid}: 空白 phase（缺 description、files_touched、subtasks）"
            )
        # skip 但无原因
        if p.get("status") == "skip" and not notes and not desc:
            errors.append(
                f"phase {pid}: status=skip 但无说明（请在 description 或 notes 注明跳过原因）"
            )
        # pending 但无描述
        if p.get("status") in (None, "pending") and not desc:
            errors.append(
                f"phase {pid}: status=pending 但缺 description"
            )
    return (len(errors) == 0), errors


def _allows_all_scope(phase: dict) -> bool:
    """显式全仓任务标记：allow_all_scope=true 或 notes/description 含「全仓」。"""
    if phase.get("allow_all_scope") is True:
        return True
    blob = f"{phase.get('notes') or ''} {phase.get('description') or ''}"
    return "全仓" in blob or "allow_all_scope" in blob.lower()


def validate_scope(
    phases: List[dict],
    *,
    workspace: Path | None = None,
) -> Tuple[bool, List[str], List[str]]:
    """v0.42: scope 硬门 — 非空，且禁止裸 ['all']（除非全仓标记）。

    若提供 workspace，另校验 scope 路径可被 git 跟踪（已 tracked 放行；
    被 gitignore 命中则报错，防 AGENTS.md 等假绿）。

    返回 (is_valid, errors, warnings)。
    """
    errors: List[str] = []
    warnings: List[str] = []
    for p in phases:
        pid = p.get("phase")
        scope = p.get("scope")
        if scope is None:
            errors.append(f"phase {pid}: empty scope（必须列出文件路径）")
            continue
        if not isinstance(scope, list):
            errors.append(f"phase {pid}: scope 须为 list[str]")
            continue
        normalized = [str(s).strip() for s in scope if str(s).strip()]
        if not normalized:
            errors.append(f"phase {pid}: empty scope（必须列出文件路径）")
            continue
        tokens = {s.lower() for s in normalized}
        if tokens <= _ALL_SCOPE_TOKENS and not _allows_all_scope(p):
            errors.append(
                f"phase {pid}: scope=['all'] 禁止（除非 allow_all_scope/全仓标记）"
            )
        if workspace is not None and not (
            tokens <= _ALL_SCOPE_TOKENS and _allows_all_scope(p)
        ):
            try:
                from _git_trackable import untrackable_scope_paths

                for bad in untrackable_scope_paths(workspace, normalized):
                    errors.append(
                        f"phase {pid}: scope path ignored by gitignore: {bad}"
                    )
            except Exception as exc:  # pragma: no cover
                warnings.append(f"phase {pid}: git trackable check skipped: {exc}")
        notes = (p.get("notes") or "").strip()
        if notes and len(notes) < 3:
            warnings.append(f"phase {pid}: notes 过短")
        vc = p.get("verification_cmd")
        if vc is not None and len(str(vc).strip()) < 3:
            warnings.append(f"phase {pid}: verification_cmd 过短")
    return (len(errors) == 0), errors, warnings


def normalize_plan_acceptance_headers(plan_text: str) -> str:
    """若缺 ``## 验收/## 验证`` 但有 ``### 验收/### 验证``，升级为 H2。

    模型常跟模板里的「改动 N → ### 验收」写成三级标题，导致 plan_lint 误杀。
    """
    text = plan_text or ""
    lines = text.splitlines()
    has_h2 = any(
        ln.strip().startswith("## 验收") or ln.strip().startswith("## 验证")
        for ln in lines
    )
    if has_h2:
        return text
    out: List[str] = []
    upgraded = False
    for ln in lines:
        s = ln.strip()
        if not upgraded and (s.startswith("### 验收") or s.startswith("### 验证")):
            # 保留原行其余文案（如「### 验收清单」→「## 验收清单」）
            out.append("## " + s[4:])
            upgraded = True
        else:
            out.append(ln)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def validate_plan_acceptance(plan_text: str) -> Tuple[bool, List[str]]:
    """v0.42: plan 必须含 ## 验收/## 验证，且 ≥1 条可执行意图/命令。"""
    errors: List[str] = []
    if not (plan_text or "").strip():
        return False, ["plan is empty"]

    plan_text = normalize_plan_acceptance_headers(plan_text)

    has_section = False
    items: List[str] = []
    in_section = False
    for line in plan_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## 验收") or stripped.startswith("## 验证"):
            has_section = True
            in_section = True
            continue
        if in_section:
            if stripped.startswith("## "):
                break
            if _ACCEPTANCE_ITEM_RE.match(line):
                items.append(stripped)

    if not has_section:
        errors.append("plan missing ## 验收 or ## 验证 section")
    elif not items:
        errors.append("plan acceptance section has no executable items")
    return (len(errors) == 0), errors


def validate_v12_fields(phases: List[dict]) -> Tuple[bool, List[str]]:
    """校验 schema v1.2 的新增字段（软警告）。

    - estimated_minutes: int, 1–30
    - files_touched: list[str], ≤3 项
    - verification_cmd: str, 可执行命令
    """
    warnings = []
    for p in phases:
        pid = p.get("phase")
        em = p.get("estimated_minutes")
        if em is not None and not (isinstance(em, int) and 1 <= em <= 30):
            warnings.append(
                f"phase {pid}: estimated_minutes={em} 需为 int 1–30"
            )
        ft = p.get("files_touched")
        if ft is not None:
            if not isinstance(ft, list):
                warnings.append(f"phase {pid}: files_touched 需为 list")
            elif len(ft) > 3:
                warnings.append(
                    f"phase {pid}: files_touched {len(ft)} 项超过 3（建议拆 phase）"
                )
        vc = p.get("verification_cmd")
        if vc is not None:
            if not isinstance(vc, str) or not vc.strip():
                warnings.append(f"phase {pid}: verification_cmd 需为非空字符串")
            elif not vc.strip().startswith(EXECUTABLE_CMD_PREFIXES):
                warnings.append(
                    f"phase {pid}: verification_cmd={vc[:60]!r} 不可执行"
                    f"（应以 {EXECUTABLE_CMD_PREFIXES[0]} 等开头）"
                )
    return (len(warnings) == 0), warnings


def validate_phases_dict(
    phases: List[dict],
    *,
    workspace: Path | None = None,
) -> Tuple[bool, List[str], List[str]]:
    """统一的 phase dict 列表校验入口。

    返回 (is_valid: bool, errors: list[str], warnings: list[str])。
    集成所有必要校验 + v0.28.0 新增校验。
    workspace 非空时启用 scope gitignore 硬门。
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not phases:
        errors.append("missing phase data")
        return (False, errors, warnings)

    seen_ids = set()

    for p in phases:
        pid = p.get("phase")
        if pid is None:
            errors.append("missing required field 'phase'")
            continue

        if not isinstance(pid, int):
            errors.append(f"'phase' must be int, got {type(pid).__name__}")
            continue

        if pid in seen_ids:
            warnings.append(f"duplicate phase id={pid}")
        seen_ids.add(pid)

        # status validation
        status = p.get("status")
        valid_statuses = {"pending", "blocked", "in_progress", "done", "verified", "failed", "skipped", "skip"}
        if status is not None and status not in valid_statuses:
            errors.append(f"'status'='{status}' is not valid")

        # subtasks validation
        subs = p.get("subtasks")
        if subs is not None and not isinstance(subs, dict):
            errors.append("'subtasks' must be dict")

        # timeout validation
        to = p.get("timeout")
        if to is not None:
            if not isinstance(to, int):
                errors.append("'timeout' must be int")
            elif to <= 0:
                errors.append("timeout must be > 0")

        # depends_on validation
        dep = p.get("depends_on")
        if dep is not None and not isinstance(dep, list):
            errors.append("'depends_on' must be list[int]")

        # run_strategy validation
        rs = p.get("run_strategy")
        valid_run_strategies = {"sequential", "parallel", "manual", "auto", ""}
        if rs is not None and rs not in valid_run_strategies:
            errors.append(f"'run_strategy'='{rs}' is not valid")

    # warnings for minimal phases (no specific fields beyond required)
    for p in phases:
        pid = p.get("phase")
        if pid is None:
            continue
        if "status" not in p:
            warnings.append(f"phase {pid}: missing 'status', assuming 'pending'")
        if "subtasks" not in p:
            warnings.append(f"phase {pid}: missing 'subtasks'")
        if "timeout" not in p:
            warnings.append(f"phase {pid}: missing 'timeout', using default")

    # v0.28.0 new checks
    _, exec_errors = validate_executor(phases)
    errors.extend(exec_errors)

    _, empty_errors = validate_empty_phase(phases)
    errors.extend(empty_errors)

    _, scope_errors, scope_warnings = validate_scope(phases, workspace=workspace)
    errors.extend(scope_errors)
    warnings.extend(scope_warnings)

    _, v12_warnings = validate_v12_fields(phases)
    warnings.extend(v12_warnings)

    return (len(errors) == 0), errors, warnings


def validate_phases_jsonl(path: Path, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
    """校验 phases.jsonl 文件（含 schema_version 元数据行）。

    返回 (is_valid: bool, errors: list[str], warnings: list[str])。
    strict=True 时对缺失字段报 error 而非 warning。
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not path.exists():
        errors.append(f"file not found: {path}")
        return (False, errors, warnings)

    if path.stat().st_size == 0:
        errors.append("file is empty")
        return (False, errors, warnings)

    phase_rows = []
    schema_version = None

    try:
        content = path.read_text()
    except Exception as e:
        errors.append(f"read error: {e}")
        return (False, errors, warnings)

    for line_no, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"L{line_no}: JSON parse error: {e}")
            continue

        if isinstance(obj, dict) and "schema_version" in obj:
            sv = obj["schema_version"]
            if schema_version is not None:
                warnings.append(f"L{line_no}: 多重 schema_version（已见 {schema_version}）")
            schema_version = sv
            # schema_version 行不是 phase row，不加入 phase_rows
            continue

        phase_rows.append(obj)

    # schema_version 校验
    if schema_version is None:
        warnings.append("缺 schema_version 元数据行（默认视为 1.0）")
        schema_version = "1.0"
    elif schema_version not in VALID_SCHEMA_VERSIONS:
        warnings.append(f"未知 schema_version={schema_version!r}（仅 {VALID_SCHEMA_VERSIONS}）")

    # phase rows 校验
    if not phase_rows:
        errors.append("no phase rows")
        return (False, errors, warnings)

    # strict 模式：缺新字段报 error
    if strict:
        for row in phase_rows:
            pid = row.get("phase")
            for field in ("estimated_minutes", "files_touched", "verification_cmd"):
                if field not in row:
                    errors.append(f"phase {pid}: missing required field '{field}' (strict mode)")

    is_valid, dict_errors, dict_warnings = validate_phases_dict(phase_rows)
    errors.extend(dict_errors)
    warnings.extend(dict_warnings)

    return (len(errors) == 0), errors, warnings


def suggest_fix_no_missing_dependencies(phases: List[dict]) -> Tuple[bool, List[str]]:
    """依赖引用是否指向存在的 phase"""
    errors = []
    by_id: Dict[int, dict] = {
        p.get("phase"): p for p in phases if p.get("phase") is not None
    }
    orphan_refs: List[str] = []

    for pid, p in by_id.items():
        for dep_id in p.get("depends_on") or []:
            dep_int: int
            try:
                dep_int = int(dep_id)
            except ValueError:
                dep_int = 0
            if dep_int not in by_id:
                orphan_refs.append(f"{pid} → {dep_id}")

    if orphan_refs:
        errors.append(f"依赖引用不存在: {orphan_refs}")

    return (len(errors) == 0), errors


def validate_status_transitions(phases: List[dict]) -> Tuple[bool, List[str]]:
    """校验单个 phase 的 status 是否合法。

    单 phase 默认 status=pending，瞬时到 done 等终态算推进过快（warning）。
    跨 phase 独立：phase A 状态不影响 phase B。
    """
    errors = []
    valid_statuses = {"pending", "blocked", "in_progress", "done", "verified", "failed", "skipped"}
    for p in phases:
        pid = p.get("phase")
        status = p.get("status", "pending")
        if status not in valid_statuses:
            errors.append(f"phase {pid}: 'status'='{status}' is not valid")
        elif status in {"done", "verified", "failed", "skipped"}:
            # 单 phase 默认状态应该是 pending，瞬时到终态报错
            # 但多 phase 时第 N 个 phase 是 done 合法（前面的已完成）
            if len(phases) == 1 and "subtasks" not in p:
                errors.append(f"phase {pid}: 状态从 lenient 跳到 {status}（应逐步推进）")
    return (len(errors) == 0), errors


def run_lint(task_id: str, fix: bool = False) -> int:
    ws = Path.cwd()
    phases_dir = ws / ".ccc" / "phases"

    # v0.28.0: 兼容多种命名约定，包括剥 _task 后缀
    base_ids = [task_id]
    if task_id.endswith("_task"):
        base_ids.append(task_id[:-5])

    candidates = []
    for tid in base_ids:
        candidates.extend([
            phases_dir / f"{tid}.phases.json",
            phases_dir / f"{tid}.phases",
            phases_dir / f"{tid}.json",
            phases_dir / tid,
        ])

    phases_file = None
    for c in candidates:
        if c.exists():
            phases_file = c
            break

    if phases_file is None:
        _log.error("phases.jsonl 不存在: %s", candidates[0])
        return 1

    actual_task_id = phases_file.stem
    if actual_task_id.endswith(".phases"):
        actual_task_id = actual_task_id[:-7]
    phases = load_phases(actual_task_id, ws)

    if not phases:
        # 区分：文件存在但空 → 报错；文件不存在 → 之前已返回 1
        if phases_file.stat().st_size == 0:
            _log.error("phases.jsonl 为空: %s", phases_file)
            return 1
        print("[phase_lint] 无 phases 数据")
        return 0

    results = []

    results.append(
        ("schema_version 校验", *validate_schema_version(phases, actual_task_id, fix))
    )
    results.append(("phase 结构", *validate_phase_structure(phases)))
    results.append(("状态流转", *validate_status_transitions(phases)))
    results.append(("循环依赖", *validate_no_cycle_dependencies(phases)))
    results.append(("依赖引用", *suggest_fix_no_missing_dependencies(phases)))
    # v0.42: scope 硬门（与 validate_phases_dict / product 门禁对齐）
    scope_ok, scope_errors, scope_warnings = validate_scope(phases, workspace=ws)
    results.append(("scope 硬门", scope_ok, scope_errors))
    for w in scope_warnings:
        print(f"[phase_lint] warning: {w}")

    all_ok = True
    for name, is_valid, errors in results:
        if not is_valid:
            all_ok = False
            print(f"[phase_lint] {name}:")
            for e in errors:
                print(f"    • {e}")

    if all_ok:
        print(f"[phase_lint] ✓ {actual_task_id} 校验通过")
        return 0
    else:
        print(f"[phase_lint] ✗ {actual_task_id} 校验失败")
        return 1


if __name__ == "__main__":
    try:
        args = parse_args()
        sys.exit(run_lint(args.task_id, args.fix))
    except KeyboardInterrupt:
        sys.exit(130)
