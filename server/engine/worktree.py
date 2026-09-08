"""server/engine/worktree.py — 业务 worktree 生命周期 + 机审分支证据（自 main.py 抽出）。

2026-09-05 深扫加固 R2 第一刀：worktree 是 main.py 最大内聚域（22 函数 + 3 常量，
约 800 行），对簇外仅依赖 3 个伴生 helper（一并迁入）。main.py 顶部全量 re-export，
外部（web/tests/scripts）引用路径不变。行为零变更——纯文本搬移。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.engine.card_state_store import CardStateError, CardStateStore

if TYPE_CHECKING:
    from server.engine.dispatch import ExecutorRegistry
    from server.engine.store import BoardStore
    from server.engine.task import Work

logger = logging.getLogger("ccc.engine.worktree")

_GIT_DEFAULT_TIMEOUT = 30  # 默认值（git 命令通常 <30s）

_SEED_HARDFAIL_MARKER = "种子盲区硬失败"

_WORKTREE_FAILURES_LOCK = threading.Lock()
# 计数器状态归本模块持有（原 main 全局）；main 经 count/failures/reset 三函数读写，
# 拆分后仍可跨模块共享同一计数（bump 在 worktree、消费在 main，同进程单例）。
_WORKTREE_FAILURES = 0


def _bump_worktree_failures() -> None:
    global _WORKTREE_FAILURES
    with _WORKTREE_FAILURES_LOCK:
        _WORKTREE_FAILURES += 1


def worktree_failure_count() -> int:
    """worktree 派发失败累计（供 main 统计摘要用）。"""
    with _WORKTREE_FAILURES_LOCK:
        return _WORKTREE_FAILURES


def reset_worktree_failure_count() -> None:
    """清零 worktree 派发失败计数（main 每次轮询摘要后归零）。"""
    global _WORKTREE_FAILURES
    with _WORKTREE_FAILURES_LOCK:
        _WORKTREE_FAILURES = 0

def _business_worktree_path(project, work_id: str) -> Path:
    """业务仓每卡 worktree 路径：`<隔离根>/<work_id>`。"""
    return Path(project.isolation_worktree_root).expanduser() / work_id.lower()

def _worktree_branch_seed(repo: Path, branch: str) -> str:
    """worktree 新分支的种子 ref。

    远端同名分支存在 → 从其恢复（保留执行体已 push 的产物与卡回写）；
    否则从 origin/main 新建。2026-08-12：强重建若一律从 main 新建，
    会丢掉执行体回写视图 → 机审读占位卡 → 空回写误打回（mx030 根因）。
    """
    res = subprocess.run(
        ["git", "-C", str(repo), "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
        capture_output=True,
        check=False,
    )
    if res.returncode == 0:
        return f"origin/{branch}"
    return "origin/main"

def _mount_business_worktree_venv(worktree: Path, repo: Path) -> None:
    """将业务仓根现成的 ``.venv`` 以符号链接挂入 worktree（不复制环境）。"""
    source = repo / ".venv"
    target = worktree / ".venv"
    if os.path.lexists(target):
        return
    if not source.is_dir():
        logger.warning("WARN worktree venv unavailable: business_repo=%s", repo)
        return
    try:
        target.symlink_to(source, target_is_directory=True)
        logger.info("业务仓 worktree 已挂载 .venv 符号链接: %s -> %s", target, source)
    except OSError as exc:
        logger.warning("worktree .venv 符号链接创建失败（不阻断 worktree）: %s (%s)", target, exc)

def _remove_business_worktree_venv(worktree: Path) -> None:
    """删除业务 worktree 内的 .venv 符号链接，绝不删除实体环境或链接目标。"""
    target = worktree / ".venv"
    if not target.is_symlink():
        return
    try:
        target.unlink()
        logger.info("业务仓 worktree .venv 符号链接已清理: %s", target)
    except OSError as exc:
        logger.warning("业务仓 worktree .venv 符号链接清理失败: %s (%s)", target, exc)

def _ensure_business_worktree(work: Work, project, log_dir: Path) -> tuple[str | None, str | None]:
    """确保业务仓每卡 worktree 存在；返回 (worktree_path | None, error | None)。

    生命周期对齐 CCC worktree：成功收单复用 / 未收单重置 / 脏或分叉强重建。
    失败返回错误（调用方记 infra 冷却，禁止回退业务仓主目录）。
    P3（env-manifest）：worktree 挂载 .venv 符号链接后，按项目 env-manifest.json
    校验 python/pytest/ruff 相对路径（symlink 展开后）真实存在；缺失 = 派发前
    拒绝（FAIL_FAST，不拉起执行体，试行体不现场修复）。manifest 文件不存在 → 默认回退。
    """
    repo = Path(project.path_mac2017).expanduser()
    if not repo.is_dir():
        return None, f"业务仓不存在: {repo}"
    target = _business_worktree_path(project, work.id)
    card_id_slug = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
    branch = f"codex/{card_id_slug}"

    # P3：env-manifest 路径与预载（CCC 仓根固定 = docs/projects/<prefix>/env-manifest.json）
    from server.engine.env_manifest import load_manifest, manifest_path, validate_manifest  # noqa: PLC0415

    ccc_root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(manifest_path(ccc_root, project.prefix or "")) if (project.prefix or "") else None

    def _validated(target: Path) -> tuple[str, None] | tuple[None, str]:
        """挂载 venv 后按 manifest 校验；缺失 → FAIL_FAST 拒绝（派发前拦截）。"""
        from server.engine.env_manifest import ENV_MANIFEST_MISSING_MARKER  # noqa: PLC0415

        ok, problems = validate_manifest(manifest, target, prefix=project.prefix or "")
        if not ok:
            _bump_worktree_failures()
            try:
                from server.board.audit_ledger import record_action  # noqa: PLC0415

                record_action(
                    ENV_MANIFEST_MISSING_MARKER,
                    work.id,
                    source="engine",
                    detail="; ".join(problems),
                    failure_class="infra",
                )
            except Exception:
                logger.exception("env-manifest 缺失 ledger 告警写入失败（不阻断拒绝）: work=%s", work.id)
            return None, f"{ENV_MANIFEST_MISSING_MARKER}：{problems[0] if problems else 'env-manifest 校验失败'}"
        return str(target), None

    try:
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception as exc:
        logger.warning("业务仓 fetch 失败（继续尝试）: %s (%s)", repo, exc)

    def _try_add(new_branch: bool) -> tuple[int, str]:
        if new_branch:
            cmd = [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                str(target),
                "-b",
                branch,
                _worktree_branch_seed(repo, branch),
            ]
        else:
            cmd = ["git", "-C", str(repo), "worktree", "add", str(target), branch]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        return res.returncode, res.stderr.strip()

    if target.exists():
        # 上次执行是否成功收单（sidecar 契约：只信日志 ok:true）
        success = False
        log_file = log_dir / f"{work.id}.log"
        if log_file.is_file():
            try:
                for line in reversed(log_file.read_text(encoding="utf-8", errors="replace").splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(data, dict) and data.get("ok") is True:
                        success = True
                        break
            except Exception:
                pass
        if success:
            _mount_business_worktree_venv(target, repo)
            return _validated(target)
        # 未成功收单：重置
        subprocess.run(["git", "checkout", "--", "."], cwd=target, capture_output=True, check=False, timeout=30)
        subprocess.run(["git", "clean", "-fd", "-e", ".venv"], cwd=target, capture_output=True, check=False, timeout=60)
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":(exclude).venv"],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
        )
        is_clean = status.returncode == 0 and not status.stdout.strip()
        if is_clean:
            merge_base = subprocess.run(
                ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
                cwd=target,
                capture_output=True,
                check=False,
            )
            if merge_base.returncode != 0:
                is_clean = False
        if is_clean:
            _mount_business_worktree_venv(target, repo)
            return _validated(target)

        # 强重建前先移除本次 worktree 自己创建的 .venv 链接；目标业务仓环境不受影响。
        _remove_business_worktree_venv(target)
        # 脏或分叉：强重建
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "remove", "--force", str(target)],
            capture_output=True,
            check=False,
            timeout=60,
        )
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], capture_output=True, check=False, timeout=30)
        subprocess.run(["git", "-C", str(repo), "branch", "-D", branch], capture_output=True, check=False, timeout=30)
        rc, err = _try_add(new_branch=True)
        if rc != 0:
            rc2, err2 = _try_add(new_branch=False)
            if rc2 != 0:
                return None, f"业务仓 worktree 重建失败: {err or err2}"
        _mount_business_worktree_venv(target, repo)
        return _validated(target)
    else:
        rc, err = _try_add(new_branch=True)
        if rc != 0:
            rc2, err2 = _try_add(new_branch=False)
            if rc2 != 0:
                return None, f"业务仓 worktree 创建失败: {err or err2}"
        _mount_business_worktree_venv(target, repo)
        return _validated(target)

def _worktree_hint_for(work: Work, registry: ExecutorRegistry) -> str:
    """按注册表 worktree_base 计算该卡 worktree 路径（无则空串）。"""
    entry = None
    if work.executor:
        entry = registry.cli_entry_for_binding(work.executor, project=work.project)
    if entry is None:
        entry = registry.cli_entry_for_role(work.role, project=work.project)
    wt_base = getattr(entry, "worktree_base", "") or "" if entry else ""
    if not wt_base:
        return ""
    return get_worktree_path(wt_base, work.id)

def _worktree_branch_tip(worktree_hint: str, branch: str) -> str | None:
    """读 worktree 分支远端 tip（机审启动前记录 = 被审 commit）。"""
    if not worktree_hint:
        return None
    try:
        res = subprocess.run(
            ["git", "-C", worktree_hint, "rev-parse", f"origin/{branch}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip() or None
    except Exception:
        return None
    return None

def _remote_branch_audit_evidence(worktree_path: str, card_rel: str, branch: str) -> bool:
    """push 空转疑云的远端事实双重校验（ccc093 目标② · ccc088「空转」假 infra 行根修）。

    以 origin 分支事实为准核实「机审证据已达远端」，两关全过才算核实：
      1) ``git ls-remote origin <branch>`` 非空 —— 远端分支事实存在；
      2) fetch 后远端跟踪分支上的卡文含 ``## 机审区`` 通过结论。
    任一环节失败 → False：调用方仍走原 infra 续审路径（不放宽）。
    """
    try:
        ls = subprocess.run(
            ["git", "-C", worktree_path, "ls-remote", "origin", branch],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if ls.returncode != 0 or not ls.stdout.strip():
            return False
        fetch = subprocess.run(
            [
                "git",
                "-C",
                worktree_path,
                "fetch",
                "-q",
                "origin",
                f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if fetch.returncode != 0:
            return False
        show = subprocess.run(
            ["git", "-C", worktree_path, "show", f"origin/{branch}:{card_rel}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if show.returncode != 0:
            return False
        from server.board.models import machine_audit_passed_text

        return machine_audit_passed_text(show.stdout)
    except (OSError, subprocess.SubprocessError):
        return False

def _commit_and_push_worktree_card(
    worktree_path: str,
    card_path: str,
    work_id: str,
) -> bool:
    """把 worktree 卡（含机审区）commit+push 到分支（信封证据进 git）。

    仅适用于 ``--audit`` 手动侧链；主链 phase2 已退出 worktree 机审。
    """
    wt_card = _worktree_card_candidate(worktree_path, card_path)
    if wt_card is None:
        logger.warning("worktree 卡不存在，无法提交机审证据: work=%s", work_id)
        return False
    try:
        # ccc093：双侧 resolve。worktree 路径常经符号链接（如 macOS /tmp → /private/tmp），
        # 单侧 resolve 会让 relative_to 必败而退化成裸文件名 → add/show 全走错路径，
        # 把「实际已成功」的 commit/push 误判成空转（ccc088 假 infra 行机制之一）。
        rel = wt_card.resolve().relative_to(Path(worktree_path).expanduser().resolve()).as_posix()
    except (ValueError, OSError):
        rel = wt_card.name
    try:
        state_store = CardStateStore(worktree_path, dispatch_dir="docs/dispatch", data_dir=Path(worktree_path) / ".ccc-state")
        state_store.commit_card_changes(wt_card, message=f"docs(card): 机审通过 {work_id}", actor="engine-audit", push=True)
        # 提交后二次校验：分支卡 HEAD 内容必须确含「机审：通过」结论才可放行。
        branch = f"codex/{Path(card_path).stem.lower()}"
        check = subprocess.run(
            ["git", "-C", worktree_path, "show", f"HEAD:{rel}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if check.returncode != 0 or (check.stdout and "机审：通过" not in check.stdout):
            if _remote_branch_audit_evidence(worktree_path, rel, branch):
                logger.info(
                    "机审证据本地 HEAD 复核空转但远端分支已含证据（ls-remote+卡文双重校验通过）: work=%s → 记 pass",
                    work_id,
                )
                return True
            logger.warning(
                "机审证据未进分支（commit/push 空转，只留工作区）: work=%s → 走 infra 续审",
                work_id,
            )
            return False
        logger.info("机审证据已提交并推送分支: work=%s", work_id)
        return True
    except CardStateError as exc:
        # 以 origin 分支事实双重校验：本地 commit/push 空转 ≠ 证据未达远端。
        branch = f"codex/{Path(card_path).stem.lower()}"
        if _remote_branch_audit_evidence(worktree_path, rel, branch):
            logger.info(
                "机审证据本地 commit/push 空转但远端分支已含证据（ls-remote+卡文双重校验通过）: work=%s → 记 pass",
                work_id,
            )
            return True
        logger.warning("机审证据未进分支（commit/push 空转，只留工作区）: work=%s (%s)", work_id, exc)
        return False
    except Exception as exc:
        logger.warning("机审证据 commit/push 异常: work=%s (%s)", work_id, exc)
        return False

def _cleanup_closed_worktrees(
    store: BoardStore,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
) -> int:
    """自动清理与生命周期管理：远端分支已删/卡已关闭/卡已打回时，回收 worktree 及本地残留分支。

    有未提交改动且卡仍在执行/机审中（.running 存在）的，绝不强删，保护数据底线。
    卡状态为终态（已关闭/打回）且有脏改动时，才允许 --force 强制 remove。
    """
    cleaned = 0
    try:
        from server.board.models import base_state
        from server.git_sync import resolve_repo_root

        main_repo = resolve_repo_root(cfg.get("DISPATCH_DIR") or "docs/dispatch")
    except Exception:
        logger.exception("worktree 清理：解析仓根失败，跳过")
        return 0

    bases: set[Path] = set()
    for entry in registry.entries:
        wt_base = getattr(entry, "worktree_base", "") or ""
        if wt_base:
            bases.add(Path(wt_base).expanduser().resolve())
    if not bases:
        return 0

    # 1. worktree 回收
    all_works = store.list_work()
    for work in all_works:
        is_running = (log_dir / f"{work.id}.running").is_file() or (log_dir / f"{work.id}-audit.running").is_file()

        wt: Path | None = None
        for base in bases:
            cand = Path(get_worktree_path(str(base), work.id)).resolve()
            if cand.is_dir():
                wt = cand
                break
        if wt is None:
            continue

        try:
            status = subprocess.run(
                ["git", "-C", str(wt), "status", "--porcelain", "-uall"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            is_dirty = status.returncode != 0 or bool(status.stdout.strip())

            card_id_slug = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
            remote_branch = f"origin/codex/{card_id_slug}"
            res_branch = subprocess.run(
                ["git", "-C", str(main_repo), "show-ref", "--verify", f"refs/remotes/{remote_branch}"],
                capture_output=True,
                check=False,
            )
            remote_branch_exists = res_branch.returncode == 0

            local_branch = f"refs/heads/codex/{card_id_slug}"
            res_local_branch = subprocess.run(
                ["git", "-C", str(main_repo), "show-ref", "--verify", local_branch], capture_output=True, check=False
            )
            local_branch_exists = res_local_branch.returncode == 0

            should_reap = False
            use_force = False

            if is_running:
                should_reap = False
            else:
                disk_base = base_state(work.state)
                if disk_base in ("待分派", "执行中", "已回写"):
                    # 保护：进行中/已回写/已收单卡的 worktree 是运行现场，一律不予回收
                    should_reap = False
                elif disk_base in ("已关闭", "打回", "作废"):
                    # 人审统一化：作废=终态，worktree 一并回收（此前归「未知状态」分支全失才 reap）
                    should_reap = True
                    if is_dirty:
                        use_force = True
                elif (not remote_branch_exists) and (not local_branch_exists):
                    # 孤儿判定：只有远端分支与本地分支均不存在时才属孤儿
                    should_reap = True
                    if is_dirty:
                        use_force = True

            if should_reap:
                cmd_remove = ["git", "-C", str(main_repo), "worktree", "remove", str(wt)]
                if use_force:
                    cmd_remove.append("--force")

                remove = subprocess.run(
                    cmd_remove,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if remove.returncode != 0:
                    logger.warning("worktree remove 失败: %s (%s)", wt, remove.stderr.strip())
                    continue

                subprocess.run(
                    ["git", "-C", str(main_repo), "worktree", "prune"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                cleaned += 1
                logger.info("worktree 已回收 (force=%s): %s", use_force, wt)
        except Exception as exc:
            logger.warning("worktree 清理异常（跳过）: %s (%s)", wt, exc)

    # 2. 本地残留分支清理
    try:
        res_branches = subprocess.run(
            ["git", "-C", str(main_repo), "branch", "--list", "codex/*"], capture_output=True, text=True, check=False
        )
        if res_branches.returncode == 0:
            local_branches = []
            for line in res_branches.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("*"):
                    continue
                local_branches.append(line.split()[-1])

            work_map = {w.id.lower(): w for w in all_works}
            for branch in local_branches:
                id_prefix_match = re.search(r"codex/([a-z]{2,4}\d{3})", branch)
                if not id_prefix_match:
                    continue
                cid = id_prefix_match.group(1).lower()
                work = work_map.get(cid)

                remote_branch = f"origin/{branch}"
                res_verify = subprocess.run(
                    ["git", "-C", str(main_repo), "show-ref", "--verify", f"refs/remotes/{remote_branch}"],
                    capture_output=True,
                    check=False,
                )
                remote_exists = res_verify.returncode == 0

                should_delete = False
                if not remote_exists:
                    should_delete = True
                elif work:
                    is_merged = (
                        subprocess.run(
                            ["git", "-C", str(main_repo), "merge-base", "--is-ancestor", remote_branch, "origin/main"],
                            capture_output=True,
                            check=False,
                        ).returncode
                        == 0
                    )
                    if base_state(work.state) == "已关闭" and is_merged:
                        should_delete = True

                if should_delete:
                    del_res = subprocess.run(
                        ["git", "-C", str(main_repo), "branch", "-D", branch],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if del_res.returncode == 0:
                        logger.info("已删除本地残留分支: %s", branch)
                    else:
                        logger.warning("删除本地分支失败: %s (%s)", branch, del_res.stderr.strip())
                else:
                    logger.info("本地分支 %s 保留（分叉/进行中/未合入）", branch)
    except Exception as exc:
        logger.warning("分支清理过程异常: %s", exc)

    # 业务仓 worktree 生命周期（2026-08-12 隔离升级）
    cleaned += _cleanup_business_worktrees(store, log_dir)
    return cleaned

def _cleanup_business_worktrees(store: BoardStore, log_dir: Path) -> int:
    """业务仓每卡 worktree 回收 + 本地残留分支清理。

    与 CCC worktree 同一套保护语义：执行中/已回写卡保护现场不回收；
    已关闭/打回/孤儿（分支引用全失）才回收；脏现场回收带 --force。
    """
    cleaned = 0
    try:
        from server.board.models import base_state
        from server.board.registry import load_projects

        projects = [p for p in load_projects() if p.isolation_worktree_root and p.path_mac2017]
    except Exception:
        return 0
    if not projects:
        return 0

    all_works = store.list_work()
    work_map = {w.id.lower(): w for w in all_works}

    for proj in projects:
        root = Path(proj.isolation_worktree_root).expanduser()
        repo = Path(proj.path_mac2017).expanduser()
        # 用 os.path.isdir（不经 Path.is_dir，避免测试 mock 与 FS 状态不一致）
        if not os.path.isdir(root) or not os.path.isdir(repo):
            continue

        # 1. worktree 回收
        for wt_dir in sorted(root.iterdir()):
            if not wt_dir.is_dir():
                continue
            cid = wt_dir.name
            work = work_map.get(cid)
            is_running = (log_dir / f"{cid}.running").is_file() or (log_dir / f"{cid}-audit.running").is_file()
            try:
                status = subprocess.run(
                    ["git", "-C", str(wt_dir), "status", "--porcelain", "-uall"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                is_dirty = status.returncode != 0 or bool(status.stdout.strip())
                should_reap = False
                use_force = False

                def _branch_refs_exist(branch: str) -> bool:
                    if not branch:
                        return False
                    r_remote = subprocess.run(
                        ["git", "-C", str(repo), "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
                        capture_output=True,
                        check=False,
                    )
                    r_local = subprocess.run(
                        ["git", "-C", str(repo), "show-ref", "--verify", f"refs/heads/{branch}"],
                        capture_output=True,
                        check=False,
                    )
                    return r_remote.returncode == 0 or r_local.returncode == 0

                if is_running:
                    should_reap = False
                elif work:
                    disk_base = base_state(work.state)
                    if disk_base in ("待分派", "执行中", "已回写"):
                        should_reap = False
                    elif disk_base in ("已关闭", "打回", "作废"):
                        should_reap = True
                        if is_dirty:
                            use_force = True
                    else:
                        # 未知状态（如作废）：分支引用全失才视为孤儿
                        branch = f"codex/{Path(work.card_path).stem.lower()}" if work.card_path else f"codex/{cid}"
                        if not _branch_refs_exist(branch):
                            should_reap = True
                            if is_dirty:
                                use_force = True
                else:
                    # 无对应卡：detached/孤儿 worktree 回收；有分支引用的保守保留
                    head_ref = subprocess.run(
                        ["git", "-C", str(wt_dir), "symbolic-ref", "--short", "-q", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    branch = head_ref.stdout.strip()
                    if branch and _branch_refs_exist(branch):
                        should_reap = False
                    else:
                        should_reap = True
                        if is_dirty:
                            use_force = True

                if should_reap:
                    # 先移除 worktree 内 .venv 符号链接（git worktree remove 拒删符号链接目标指向外部）
                    _remove_business_worktree_venv(wt_dir)
                    cmd = ["git", "-C", str(repo), "worktree", "remove", str(wt_dir)]
                    if use_force:
                        cmd.append("--force")
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
                    if res.returncode == 0:
                        subprocess.run(
                            ["git", "-C", str(repo), "worktree", "prune"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                            check=False,
                        )
                        cleaned += 1
                        logger.info("业务仓 worktree 已回收 (force=%s): %s", use_force, wt_dir)
                    else:
                        logger.warning("业务仓 worktree remove 失败: %s (%s)", wt_dir, res.stderr.strip())
            except Exception as exc:
                logger.warning("业务仓 worktree 清理异常（跳过）: %s (%s)", wt_dir, exc)

        # 2. 本地残留分支清理（远端已删 / 卡已关闭且已合入 main）
        try:
            res_branches = subprocess.run(
                ["git", "-C", str(repo), "branch", "--list", "codex/*"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res_branches.returncode == 0:
                for line in res_branches.stdout.splitlines():
                    line = line.strip()
                    if not line or line.startswith("*"):
                        continue
                    branch = line.split()[-1]
                    m = re.search(r"codex/([a-z]{2,4}\d{3})", branch)
                    if not m:
                        continue
                    cid = m.group(1).lower()
                    work = work_map.get(cid)
                    remote_branch = f"origin/{branch}"
                    res_verify = subprocess.run(
                        ["git", "-C", str(repo), "show-ref", "--verify", f"refs/remotes/{remote_branch}"],
                        capture_output=True,
                        check=False,
                    )
                    remote_exists = res_verify.returncode == 0
                    should_delete = False
                    if not remote_exists:
                        should_delete = True
                    elif work and base_state(work.state) == "已关闭":
                        is_merged = (
                            subprocess.run(
                                ["git", "-C", str(repo), "merge-base", "--is-ancestor", remote_branch, "origin/main"],
                                capture_output=True,
                                check=False,
                            ).returncode
                            == 0
                        )
                        if is_merged:
                            should_delete = True
                    if should_delete:
                        del_res = subprocess.run(
                            ["git", "-C", str(repo), "branch", "-D", branch],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if del_res.returncode == 0:
                            logger.info("业务仓本地残留分支已删除: %s", branch)
        except Exception as exc:
            logger.warning("业务仓分支清理异常: %s", exc)

    return cleaned

def get_worktree_path(worktree_base: str, work_id: str) -> str:
    """按 worktree_base 和 work_id 计算实际 worktree 路径，支持占位符。

    兼容旧测试/插件对 ``server.engine.main.get_worktree_path`` 的 patch：main 仍是
    外部兼容门面，若该门面被替换则沿用替换后的策略；正常运行时避免递归回到自身。
    """
    try:
        from server.engine import main as engine_main

        override = getattr(engine_main, "get_worktree_path", None)
        if override is not None and override is not get_worktree_path:
            return override(worktree_base, work_id)
    except (ImportError, AttributeError):
        pass
    worktree_id = work_id.lower()
    if "<task>" in worktree_base:
        return worktree_base.replace("<task>", worktree_id)
    if "{task}" in worktree_base:
        return worktree_base.replace("{task}", worktree_id)
    if "<work_id>" in worktree_base:
        return worktree_base.replace("<work_id>", worktree_id)
    if "{work_id}" in worktree_base:
        return worktree_base.replace("{work_id}", worktree_id)
    return f"{worktree_base}-{worktree_id}"

def _worktree_has_new_commit(worktree_path: str, since_ref: str | None = None) -> bool:
    """worktree 内相对 ``since_ref``（默认 origin/main）是否有 ≥1 个未合入新 commit（产物证据之一）。

    传 ``since_ref`` 为派发时记录的 origin/main tip（V2）：避免派发后他人合入导致
    执行体躺着不动也被误判「有新 commit」。命令失败一律视为无新 commit；不抛异常。
    """
    if not worktree_path or not os.path.isdir(worktree_path):
        return False
    base_ref = since_ref or "origin/main"
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "log", f"{base_ref}..HEAD", "--oneline"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return False
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())

def _worktree_has_nonempty_diff(worktree_path: str) -> bool:
    """worktree 相对 origin/main 是否有非空文件 diff（防空 commit / 只改消息冒充写码）。"""
    if not worktree_path or not os.path.isdir(worktree_path):
        return False
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "diff", "--stat", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return False
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())

def _worktree_card_candidate(worktree_path: str, card_path: str) -> Path | None:
    """worktree 内与生产卡相对路径对应的副本（机审常写在这里）。"""
    if not worktree_path or not card_path:
        return None
    prod = Path(card_path)
    # 常见：…/CCC/docs/dispatch/... → worktree/docs/dispatch/...
    parts = prod.parts
    for marker in ("docs", "dispatch"):
        if marker in parts:
            idx = parts.index(marker)
            rel = Path(*parts[idx:])
            cand = Path(worktree_path) / rel
            if cand.is_file():
                return cand
    # 回退：同名文件
    cand = Path(worktree_path) / "docs" / "dispatch" / prod.parent.name / prod.name
    if cand.is_file():
        return cand
    # 极简回退：直接在 worktree 目录下找同名文件 (for testing and simple layouts)
    flat_cand = Path(worktree_path) / prod.name
    return flat_cand if flat_cand.is_file() else None

def _card_rel_path_in_worktree(card_path: str) -> str | None:
    """生产卡路径 → 主仓内相对路径（docs/ 起的尾段），即卡副本在 worktree 内的落位。"""
    parts = Path(card_path).parts
    if "docs" not in parts:
        return None
    return Path(*parts[parts.index("docs") :]).as_posix()

def _local_main_has_card(main_repo: Path, card_rel: str) -> bool | None:
    """本地 main 树是否已含该卡文件（= 该卡 commit 已进本地 main）。

    Returns True/False；main ref 本身不可解析等探测异常返回 None（无法安全判定）。
    """
    try:
        res = subprocess.run(
            ["git", "-C", str(main_repo), "cat-file", "-e", f"main:{card_rel}"],
            capture_output=True,
            check=False,
            timeout=_GIT_DEFAULT_TIMEOUT,
        )
    except Exception:
        return None
    if res.returncode == 0:
        return True
    try:
        chk = subprocess.run(
            ["git", "-C", str(main_repo), "rev-parse", "--verify", "main^{commit}"],
            capture_output=True,
            check=False,
            timeout=_GIT_DEFAULT_TIMEOUT,
        )
    except Exception:
        return None
    return False if chk.returncode == 0 else None

def _self_heal_worktree_card(main_repo: Path, worktree_path: str, card_rel: str) -> tuple[bool, str]:
    """ccc092 自愈：从本地 main 读卡内容 copy 进 worktree（untracked，随执行体回写一并提交）。

    只恢复卡副本这一个文件，绝不触碰业务代码文件（红线）。
    """
    try:
        res = subprocess.run(
            ["git", "-C", str(main_repo), "show", f"main:{card_rel}"],
            capture_output=True,
            check=False,
            timeout=_GIT_DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        return False, f"读取本地 main 卡内容异常: {exc}"
    if res.returncode != 0:
        return False, f"读取本地 main 卡内容失败: {res.stderr.decode(errors='replace').strip()[:200]}"
    target = Path(worktree_path) / card_rel
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(res.stdout)
    except OSError as exc:
        return False, f"写入 worktree 卡副本失败: {exc}"
    return True, ""

def _seed_hardfail_alert(work: Work, log_dir: Path, cfg: dict[str, Any] | None, reason: str) -> None:
    """ccc092 硬失败告警：写 alerts 告警文件（一次性，人工核查删除后恢复自动派发）。"""
    env_log = os.environ.get("LOG_DIR") or ((cfg or {}).get("LOG_DIR") or "")
    log_base = Path(env_log) if env_log else Path(log_dir)
    try:
        alert_dir = log_base / "alerts"
        alert_dir.mkdir(parents=True, exist_ok=True)
        (alert_dir / f"missing-card-seed-{work.id}.txt").write_text(
            f"work={work.id}\n"
            f"时间={time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{reason}\n"
            "处理：确认该卡出卡 commit 已 push 且合入本地 main 后，删除本文件并人工恢复卡片待分派。\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("种子盲区告警文件写入失败: work=%s (%s)", work.id, exc)

def _ensure_worktree_card_seed(
    work: Work,
    worktree_path: str,
    main_repo: Path,
    log_dir: Path,
    cfg: dict[str, Any] | None = None,
) -> list[str] | None:
    """ccc092 种子一致性：worktree 存在但缺对应卡副本时的两分支处理。

    分支①自愈：该卡 commit 已存在于本地 main → 卡副本 copy 进 worktree 后放行；
    分支②硬失败：卡 commit 未进本地 main（未 push/未合入）或播种探测异常 →
    ERROR 日志 + alerts 告警文件 + 返回硬失败原因（worker 直达打回），取代原 WARNING 循环；
    硬失败不进任何重试/冷却循环，一次性人工介入（红线）。

    Returns:
        None → 卡副本就绪（原本就有或自愈成功），派发放行；
        list[str] → 硬失败原因清单（含 ``种子盲区硬失败`` 标记）。
    """
    if _worktree_card_candidate(worktree_path, work.card_path) is not None:
        return None
    card_rel = _card_rel_path_in_worktree(work.card_path)
    has_local: bool | None = None if card_rel is None else _local_main_has_card(main_repo, card_rel)
    detail = ""
    if card_rel is None:
        detail = f"无法从卡路径推导主仓相对路径: {work.card_path}"
    elif has_local:
        healed, heal_err = _self_heal_worktree_card(main_repo, worktree_path, card_rel)
        if healed and _worktree_card_candidate(worktree_path, work.card_path) is not None:
            logger.info("种子自愈: work=%s 卡副本已从本地 main 恢复到 worktree %s", work.id, worktree_path)
            return None
        detail = heal_err or "自愈后仍找不到卡副本"
    elif has_local is False:
        detail = f"卡 {work.card_path} 的 commit 未进本地 main（未 push 或未合入）"
    else:
        detail = f"本地 main 可达性探测异常，无法安全播种卡 {work.card_path}"
    reason = f"{_SEED_HARDFAIL_MARKER}：{detail}；已停止自动派发并打回，需人工介入"
    logger.error("%s: work=%s %s", _SEED_HARDFAIL_MARKER, work.id, detail)
    _seed_hardfail_alert(work, log_dir, cfg, reason)
    return [reason]

def _worktree_root_from(card_path: str) -> Path:
    """从分支卡绝对路径推导 worktree 根（卡副本所在仓 = repos 消息文件父级向上）。"""
    p = Path(card_path).expanduser().resolve()
    for ancestor in p.parents:
        if (ancestor / ".git").exists() or (ancestor / "docs" / "dispatch").exists():
            return ancestor
    raise ValueError(f"无法推导 worktree 根: {card_path}")
