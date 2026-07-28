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
    p = (path or "").strip().rstrip("/")
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
    except Exception as exc:  # noqa: BLE001
        # 2026-07-24 方案 0.1.3：清理 except:pass 裸吞，统一加 log
        _log.warning("task_commit parse_result silent_ignored: %s", str(exc))
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


def _is_harness_noise_path(path: str) -> bool:
    """Probe/report leftovers that must not dirty_block hygiene / scoped DoD."""
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p == "docs" or p == "docs/" or p.startswith("docs/reports/") or p == "docs/reports":
        return True
    if p.startswith("docs/") and p.endswith("_NOTE.md"):
        return True
    # Engine / failure-learning side effects — not business deliverables
    if p == "docs/lessons.md" or p.startswith("docs/lessons/"):
        return True
    if p.startswith(".ccc/lessons/") or p.startswith(".ccc/.product-fail-counter/"):
        return True
    return False


def _hygiene_allow_ccc_meta(workspace: Path, task_id: str) -> bool:
    """允许 DoD 提交 .ccc 编排产物：仅真 board_ops/ops/hygiene pipeline，
    不含 doc_only / docs-only scope（后者若 dirty 应只 commit 业务 scope）。

    同时从 phases scope 推断：全部 scope 在 .ccc/ 下也视为卫生卡。
    """
    try:
        from _ccc_hygiene import (
            _load_phase_scopes,
            scopes_are_ccc_only,
        )
        # Try reading task from board store to check pipeline/tags
        try:
            from _board_store import FileBoardStore
            store = FileBoardStore(workspace)
            task = None
            for col in ("in_progress", "planned", "testing", "backlog", "verified", "abnormal"):
                tasks = store.list_tasks(col)
                task = next((t for t in tasks if t.get("id") == task_id), None)
                if task:
                    break
            if task:
                from _ccc_hygiene import _hygiene_is_board_ops
                if _hygiene_is_board_ops(task):
                    return True
        except Exception:
            pass
        return scopes_are_ccc_only(_load_phase_scopes(workspace, task_id))
    except Exception as exc:  # noqa: BLE001
        _log.warning("task_commit hygiene_allow_ccc_meta silent_ignored: %s", str(exc))
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
    - Hygiene cards may stage .ccc meta only；docs/reports 等探针噪声不 dirty_block。
    """
    existing = find_task_commit(workspace, task_id)

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

    # 已有 task_id commit 时：若 plan scope 仍脏，继续补 commit（防旧 PENDING 假绿）
    if existing and (not pre_head or existing != pre_head):
        scope = set(_plan_scope_paths(workspace, task_id))
        scope |= set(_result_wrote_paths(workspace, task_id))
        scope_dirty = [
            p
            for p in all_paths
            if any(
                s == p
                or s.startswith(p.rstrip("/") + "/")
                or p.startswith(s.rstrip("/") + "/")
                for s in scope
            )
        ] if scope else []
        if not scope_dirty:
            return True, "already", existing
        _log.info(
            "[DoD] %s prior commit %s but scope still dirty %s — recommit",
            task_id,
            existing[:12],
            scope_dirty[:6],
        )
    # Detect hygiene BEFORE trusting empty-product — paper report dirty would
    # otherwise keep product non-empty and skip hygiene branch (R4 qb e05).
    hygiene = _hygiene_allow_ccc_meta(workspace, task_id)
    if hygiene:
        # 卫生卡也只 add 本 task 相关的 .ccc meta，禁止扫全板 index/backlog 等无关脏。
        product = [
            p
            for p in all_paths
            if (
                # task-specific board entry files
                p.startswith(".ccc/board/")
                and task_id in p
            )
            or (
                # task-specific pids/plans/phases/reports/verdicts
                p.startswith((".ccc/pids/", ".ccc/plans/", ".ccc/phases/",
                              ".ccc/reports/", ".ccc/verdicts/"))
                and task_id in p
            )
            or (
                # essential orchestration metadata (NOT broad board index/state)
                p in (".ccc/state.md", ".ccc/warnings.json", ".ccc/profile.md",
                      ".ccc/flow-smoke.md")
            )
        ]
        # Fallback for directory-level ?? .ccc/ entries (untracked .ccc dir):
        # when product is empty but all dirty paths are .ccc/ directory dirties,
        # git add the full .ccc subdirs relevant to this task.
        if not product and all(
            _is_ccc_meta_path(p) or p.startswith(".ccc/") or _is_harness_noise_path(p)
            for p in all_paths
        ):
            for d in (".ccc/board/", ".ccc/reports/", ".ccc/plans/", ".ccc/phases/",
                      ".ccc/pids/", ".ccc/verdicts/"):
                for f in sorted((workspace / d).rglob("*")):
                    if not f.is_file():
                        continue
                    rel = str(f.relative_to(workspace))
                    if rel not in product and task_id in rel:
                        product.append(rel)
            if product:
                _log.info("[DoD] %s hygiene fallback expanded %d paths from dir dirt",
                          task_id, len(product))
    elif product:
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
                and not _is_harness_noise_path(p)
                and not _is_ccc_meta_path(p)
                and not p.startswith(".ccc/")
            ]
            if scoped:
                if outside:
                    _log.info(
                        "[DoD] %s leave unstaged outside-scope dirty: %s",
                        task_id,
                        outside[:8],
                    )
                product = scoped
            elif outside:
                sample = ", ".join(outside[:6])
                return (
                    False,
                    f"dirty_block: business dirty outside plan scope "
                    f"(no in-scope changes): {sample}",
                    existing,
                )
            else:
                # scope 已无待改；仅 harness/.ccc 噪音 → 不挡（验证-only / 已落地卡）
                if existing:
                    return True, "already_scope_clean_noise_only", existing
                product = []

    if not product:
        if dirty:
            noise_only = all(
                _is_ccc_meta_path(p)
                or p.startswith(".ccc/")
                or _is_harness_noise_path(p)
                for p in all_paths
            )
            # Hygiene with only harness noise left: no commit needed if already have one
            if hygiene and noise_only:
                if existing:
                    return True, "already_hygiene_noise_only", existing
            # 验证-only / 范围已在盘上：噪音脏不挡；无 task_id commit 时写 stamp 过门
            scope_paths = set(_plan_scope_paths(workspace, task_id)) | set(
                _result_wrote_paths(workspace, task_id)
            )
            if scope_paths and noise_only:
                if existing:
                    return True, "already_scope_on_disk_noise_only", existing
                stamp_rel = f".ccc/reports/{task_id}.verify-stamp.md"
                stamp = workspace / stamp_rel
                try:
                    stamp.parent.mkdir(parents=True, exist_ok=True)
                    stamp.write_text(
                        f"# verify-stamp\n\ntask_id={task_id}\n"
                        "scope already satisfied; harness noise only\n",
                        encoding="utf-8",
                    )
                except OSError as exc:
                    return False, f"verify_stamp_write_failed: {exc}", existing
                product = [stamp_rel]
            elif noise_only and existing:
                return True, "already_noise_only", existing
            else:
                return (
                    False,
                    "no task_id commit and only .ccc/ meta dirty — "
                    "agent did not land product changes"
                    if not hygiene
                    else "no task_id commit and hygiene tree has no .ccc changes to stage",
                    existing,
                )
        else:
            return (
                False,
                "no task_id commit and working tree clean — agent did not land changes",
                existing,
            )
        if not product:
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
        except Exception as exc:  # noqa: BLE001
            # 2026-07-24 方案 0.1.3：清理 except:pass 裸吞，统一加 log
            _log.warning("task_commit git head silent_ignored: %s", str(exc))
            h = ""
    if not h:
        return False, "auto-commit produced no hash", ""
    _log.info("[DoD] %s auto-committed %s", task_id, h[:12])
    return True, "auto-committed", h
