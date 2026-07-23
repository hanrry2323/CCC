"""_task_commit.py — Dev DoD: ensure commit message contains task_id before gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from _config import get_logger

_log = get_logger("task.commit")

# 编排噪音：不得当作 DoD 产品落地。其余路径（含 .ccc/flow-smoke.md）可 stage。
_CCC_META_EXACT = frozenset(
    {
        ".ccc/engine-heartbeat.json",
        ".ccc/state.md",
        ".ccc/warnings.json",
        ".ccc/profile.md",
    }
)
_CCC_META_PREFIXES = (
    ".ccc/board/",
    ".ccc/stats/",
    ".ccc/pids/",
    ".ccc/quarantines/",
    ".ccc/review-locks/",
    ".ccc/plans/",
    ".ccc/phases/",
    ".ccc/reports/",
    ".ccc/verdicts/",
)


def _is_ccc_meta_path(path: str) -> bool:
    p = (path or "").strip()
    while p.startswith("./"):
        p = p[2:]
    if p in _CCC_META_EXACT or p == ".ccc":
        return True
    return any(p.startswith(pref) for pref in _CCC_META_PREFIXES)


def porcelain_product_paths(porcelain: str) -> list[str]:
    """Parse ``git status --porcelain``; drop known ``.ccc/`` orchestration noise.

    Board/state/pids/stats/plans/phases/reports churn must not satisfy DoD.
    Deliverables such as ``.ccc/flow-smoke.md`` (and normal source files) still count.
    """
    out: list[str] = []
    for raw in (porcelain or "").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        # status is 2 chars + space; path may be quoted or ``a -> b``
        path = line[3:] if len(line) >= 4 else line
        path = path.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip().strip('"')
        if _is_ccc_meta_path(path):
            continue
        out.append(path)
    return out


def _commit_grep_needles(task_id: str) -> list[str]:
    """Work cards may commit with epic id only; accept parent id as DoD needle."""
    tid = (task_id or "").strip()
    needles = [tid] if tid else []
    # flow-green-xxx-w1 → also accept flow-green-xxx
    if tid and "-w" in tid:
        parent = tid.rsplit("-w", 1)[0]
        if parent and parent not in needles:
            needles.append(parent)
    return needles


def find_task_commit(workspace: Path, task_id: str) -> str:
    for needle in _commit_grep_needles(task_id):
        try:
            r = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--grep",
                    needle,
                    "--format=%H",
                    "--max-count=1",
                ],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0:
                lines = (r.stdout or "").strip().splitlines()
                if lines and len(lines[0]) >= 40:
                    return lines[0][:40]
        except Exception as exc:
            _log.warning("find_task_commit failed needle=%s: %s", needle, exc)
    return ""


def _porcelain_paths(porcelain: str) -> list[str]:
    """Parse all paths from ``git status --porcelain`` (no meta filter)."""
    out: list[str] = []
    for raw in (porcelain or "").splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        path = line[3:] if len(line) >= 4 else line
        path = path.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip().strip('"')
        if path:
            out.append(path)
    return out


def _plan_scope_paths(workspace: Path, task_id: str) -> list[str]:
    """Best-effort plan scope file list (no board.context dependency)."""
    plan = Path(workspace) / ".ccc" / "plans" / f"{task_id}.plan.md"
    if not plan.is_file():
        return []
    try:
        content = plan.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    files: list[str] = []
    in_scope = False
    for line in content.splitlines():
        if line.startswith("## 范围") or line.startswith("## 文件白名单") or line.startswith(
            "## 文件"
        ):
            in_scope = True
            continue
        if in_scope and line.startswith("## "):
            break
        if not in_scope:
            continue
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip().strip("`\"'*")
        if "只改" in item or item.startswith("**"):
            continue
        # drop trailing commentary
        for sep in ("（", "(", " —", " - "):
            idx = item.find(sep)
            if idx > 0:
                item = item[:idx]
        item = item.strip().rstrip(".").strip("`\"'")
        if item and not item.startswith("#") and (
            "/" in item
            or item.endswith(
                (".py", ".md", ".json", ".ts", ".js", ".sh", ".toml", ".yml", ".yaml")
            )
        ):
            files.append(item)
        elif item and " " not in item and not item.startswith("http"):
            files.append(item)
    return files


def _result_wrote_paths(workspace: Path, task_id: str) -> list[str]:
    """Paths claimed in ``.ccc/reports/<tid>.result.json`` wrote[] / files[]."""
    p = Path(workspace) / ".ccc" / "reports" / f"{task_id}.result.json"
    if not p.is_file():
        return []
    try:
        from _result_json import parse_result_file

        parsed, _ = parse_result_file(p)
    except Exception:
        return []
    if not isinstance(parsed, dict):
        return []
    out: list[str] = []
    for key in ("wrote", "files", "paths"):
        val = parsed.get(key)
        if isinstance(val, list):
            out.extend(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, str) and val.strip():
            out.append(val.strip())
    return out


def _hygiene_allow_ccc_meta(workspace: Path, task_id: str) -> bool:
    """ops / .ccc-only 卫生卡允许 DoD 提交编排产物。"""
    try:
        from _ccc_hygiene import task_skips_forced_pytest

        return task_skips_forced_pytest(workspace, task_id, None)
    except Exception:
        return False


def ensure_task_commit(
    workspace: Path,
    task_id: str,
    *,
    phase_num: int | None = None,
    pre_head: str = "",
) -> tuple[bool, str, str]:
    """If no task_id commit exists but there are local changes, create one.

    Returns (ok, reason, commit_hash).
    Does NOT invent empty commits when the tree is clean — that means the
    agent produced no diffs and must fail the gate.

    KPI commit_gate_hygiene_vs_business_dirty:
    - Prefer plan-scope / result.wrote paths over unrelated dirty business files.
    - Unrelated business dirty is left unstaged（不挡白名单任务提交）.
    - Hygiene cards may stage .ccc meta only.
    """
    existing = find_task_commit(workspace, task_id)
    if existing and (not pre_head or existing != pre_head):
        return True, "already", existing

    try:
        st = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, f"git status failed: {exc}", ""

    dirty = (st.stdout or "").rstrip("\n")
    all_paths = _porcelain_paths(dirty)
    product = porcelain_product_paths(dirty)
    hygiene = False
    if not product and dirty:
        hygiene = _hygiene_allow_ccc_meta(workspace, task_id)
        if hygiene:
            # 卫生卡：允许 stage 全部 .ccc/ 脏路径（仍拒绝业务树）
            product = [
                p
                for p in all_paths
                if _is_ccc_meta_path(p)
                or p.startswith(".ccc/")
                or p in (".ccc/state.md", ".ccc/agent-mind/decided.json")
                or p.startswith(".ccc/agent-mind/")
                or p.startswith(".ccc/lessons/")
            ]

    if product and not hygiene:
        # Scope-aware: only stage plan / result paths when known
        scope = set(_plan_scope_paths(workspace, task_id))
        scope |= set(_result_wrote_paths(workspace, task_id))
        if scope:
            scoped: list[str] = []
            for s in sorted(scope):
                sp = Path(workspace) / s
                if not sp.exists():
                    continue
                # Match exact porcelain path, or untracked parent dir (?? scripts/)
                for p in all_paths:
                    pn = p.rstrip("/")
                    if s == p or s == pn or s.startswith(pn + "/") or p.startswith(
                        s.rstrip("/") + "/"
                    ):
                        if s not in scoped:
                            scoped.append(s)
                        break
            outside = [
                p
                for p in product
                if p not in scoped
                and not any(
                    s == p
                    or s.startswith(p.rstrip("/") + "/")
                    or p.startswith(s.rstrip("/") + "/")
                    for s in scope
                )
            ]
            if scoped:
                if outside:
                    _log.info(
                        "[DoD] %s leave unstaged outside-scope dirty: %s",
                        task_id,
                        outside[:8],
                    )
                product = scoped
            elif outside or product:
                sample = ", ".join((outside or product)[:6])
                return (
                    False,
                    f"dirty_block: business dirty outside plan scope "
                    f"(no in-scope changes): {sample}",
                    existing,
                )

    if not product:
        if dirty:
            return (
                False,
                "no task_id commit and only .ccc/ meta dirty — "
                "agent did not land product changes",
                existing,
            )
        return (
            False,
            "no task_id commit and working tree clean — agent did not land changes",
            existing,
        )

    try:
        # Stage product paths only — never auto-commit board/state noise as DoD
        #（卫生卡例外：上面已把 .ccc meta 纳入 product）。
        add_cmd = ["git", "add", "--", *product]
        subprocess.run(
            add_cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        phase_bit = f" phase={phase_num}" if phase_num is not None else ""
        kind = " hygiene" if hygiene else ""
        msg = f"{task_id}{phase_bit}: auto-commit by CCC DoD gate{kind}"
        r = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            err = ((r.stderr or "") + (r.stdout or "")).strip()[:400]
            return False, f"auto-commit failed: {err}", ""
    except Exception as exc:
        return False, f"auto-commit exception: {exc}", ""

    h = find_task_commit(workspace, task_id)
    if not h:
        # commit succeeded but grep miss — resolve HEAD
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            h = (r.stdout or "").strip()[:40]
        except Exception:
            h = ""
    if not h:
        return False, "auto-commit produced no hash", ""
    _log.info("[DoD] %s auto-committed %s", task_id, h[:12])
    return True, "auto-committed", h
