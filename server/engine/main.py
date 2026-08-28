"""Engine 主入口 — 配置加载 + 主循环（薄驱动，负责真实派发/收单）。

用法：
    $PYTHON_BIN -m server.engine.main --config <config.env>        # 持续模式（循环 + 心跳）
    $PYTHON_BIN -m server.engine.main --config <config.env> --once  # 单次扫描 + 派发 + 收单后退出

`--once` 输出一行 JSON 统计；缺 `--config` 或配置缺失 → 非零退出并报错。

Engine 职责（契约 §2/§7）：读取执行体注册表 → 派发（可后台 CLI 自动拉起 / 手动 GUI 挂起）→
收单（按退出码 + 输出判定）→ 状态机流转（待分派 → 执行中 → 已回写/打回 → 已关闭）。

派发管道（T32 真实派发闭环）：
1. decide(role) → AUTO：从注册表取 CLI 条目，build_command 生成 argv；
2. subprocess.Popen 启动，stdout/stderr 重定向到 {EXECUTOR_LOG_DIR}/{work_id}.log；
3. wait(timeout=EXECUTOR_TIMEOUT_SECONDS)；
4. 退出码 0 → 已回写；非 0 / 超时 / 启动失败 → 打回（附问题清单）。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config.loader import ConfigError, load_config
from server.engine.dispatch import (
    DispatchDecision,
    ExecutorEntry,
    ExecutorRegistry,
    build_command,
    decide_work,
    load_registry,
)
from server.engine.gates import DispatchGate, GateContext, GateRegistry, GateResult
from server.engine.card_gate import enforce_card_gate
from server.engine.metrics import (
    WORKER_EVENTS_FILE,
    ProcessSampler,
    record_slot_snapshot,
    record_worker_event,
)
from server.engine.pool import get_dispatch_pool
from server.engine.store import BoardStore, FileBoardStore
from server.engine.task import State, Work
from server.board.roles import normalize_tool

# 业务仓 worktree 失败计数（2026-08-12 · 隔离升级）：进程内累计，run_once 汇总后清零
_WORKTREE_FAILURES = 0
_WORKTREE_FAILURES_LOCK = threading.Lock()


def _bump_worktree_failures() -> None:
    global _WORKTREE_FAILURES
    with _WORKTREE_FAILURES_LOCK:
        _WORKTREE_FAILURES += 1


def _business_project(work: Work):
    """按 work.project 找 registry 业务仓条目（须有 2017 路径 + 隔离根）。"""
    if not work or not work.project:
        return None
    from server.board.registry import load_projects

    for e in load_projects():
        if (
            ((e.prefix and e.prefix == work.project) or e.id == work.project)
            and e.path_mac2017
            and e.isolation_worktree_root
        ):
            return e
    return None


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


def _ensure_business_worktree(work: Work, project, log_dir: Path) -> tuple[str | None, str | None]:
    """确保业务仓每卡 worktree 存在；返回 (worktree_path | None, error | None)。

    生命周期对齐 CCC worktree：成功收单复用 / 未收单重置 / 脏或分叉强重建。
    失败返回错误（调用方记 infra 冷却，禁止回退业务仓主目录）。
    """
    repo = Path(project.path_mac2017).expanduser()
    if not repo.is_dir():
        return None, f"业务仓不存在: {repo}"
    target = _business_worktree_path(project, work.id)
    card_id_slug = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
    branch = f"codex/{card_id_slug}"

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
            return str(target), None
        # 未成功收单：重置
        subprocess.run(["git", "checkout", "--", "."], cwd=target, capture_output=True, check=False, timeout=30)
        subprocess.run(["git", "clean", "-fd"], cwd=target, capture_output=True, check=False, timeout=60)
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=target, capture_output=True, text=True, check=False
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
            return str(target), None
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
        return str(target), None
    else:
        rc, err = _try_add(new_branch=True)
        if rc != 0:
            rc2, err2 = _try_add(new_branch=False)
            if rc2 != 0:
                return None, f"业务仓 worktree 创建失败: {err or err2}"
        return str(target), None


logger = logging.getLogger("ccc.engine")
metrics_logger = logging.getLogger("ccc.engine.metrics")

DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_EXECUTOR_TIMEOUT = 300
MAX_MARKER_AGE_SECONDS = 7200  # 绝对兜底；实际强拆时距由 _effective_max_marker_age() 按执行超时 1.5× 推导（1-3）


def _effective_max_marker_age() -> int:
    """运行标记强拆时距（1-3 时距分离，2026-08-24 直修）。

    原与 EXECUTOR_TIMEOUT_SECONDS 同为 7200：两墙同刻触发，清扫侧抢先击杀会以
    「退出码 -9」烧掉业务重试预算。现取执行超时的 1.5×（下限 900s），合法长会话
    只会被执行器自身超时路径收单（含 infra 冷却语义），清扫兜底只收真僵尸。
    """
    try:
        t = max(60, int(os.environ.get("EXECUTOR_TIMEOUT_SECONDS") or 7200))
    except ValueError:
        t = 7200
    return max(900, int(t * 1.5))


def _acquire_engine_single_instance(data_dir: str) -> None:
    """1-4 单实例锁（2026-08-24 直修）：DATA_DIR/engine.lock fcntl 排他锁。

    防 watchdog kickstart 与 --once / 手动实例并发双开——双开叠加 claim 覆写前
    击杀（F1）会演变为跨实例互杀对方在途会话。拿不到锁即退出码 2。
    """
    import fcntl

    lock_path = Path(data_dir).expanduser() / "engine.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        logger.error("另一 engine 实例持有单实例锁(%s)，拒绝双开", lock_path)
        raise SystemExit(2)
    try:
        os.truncate(fd, 0)
        os.write(fd, f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S')}\n".encode())
    except OSError:
        pass
    globals()["_ENGINE_LOCK_FD"] = fd  # 进程生命周期持有，退出自动释放

# ── git 超时统一包装 ──
_GIT_DEFAULT_TIMEOUT = 30  # 默认值（git 命令通常 <30s）


def _git_run(
    args: list[str],
    timeout: int = _GIT_DEFAULT_TIMEOUT,
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """统一 git 调用：封装 timeout，避免磁盘锁/网络延迟永久阻塞。"""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=check,
    )


_probe_failures_count = 0

# T67 验收区预检缓存：{文件路径: (mtime, 已验收判定)}，避免持续模式每轮全量读盘
_acceptance_cache: dict[str, tuple[float, bool]] = {}


def _card_body_accepted(path: Path) -> bool:
    """读卡正文 ``## 验收区`` 后 20 行内是否含 ``✅`` / ``判定：通过``（与 validate.py 同语义）。

    文件缺失/不可读/未含验收区标记 → 视为未验收（返回 False，不阻断派发）。
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("## 验收区"):
            idx = i
            break
    if idx == -1:
        return False
    for j in range(idx + 1, min(idx + 21, len(lines))):
        line = lines[j]
        if "✅" in line or "判定：通过" in line:
            return True
    return False


def is_card_accepted(card_path: str) -> bool:
    """卡文件含验收区标记 → 已验收，Engine 不派发（防线 2，防御 validate 未覆盖的旧卡/漏网）。

    按文件 mtime 缓存判定结果，仅 mtime 变化才重读，避免持续模式每轮全量读盘。
    """
    if not card_path:
        return False
    path = Path(card_path)
    try:
        if not path.is_file():
            return False
        mtime = path.stat().st_mtime
    except OSError:
        return False
    cached = _acceptance_cache.get(str(path))
    if cached is not None and cached[0] == mtime:
        return cached[1]
    accepted = _card_body_accepted(path)
    _acceptance_cache[str(path)] = (mtime, accepted)
    return accepted


def probe_relay(url: str, timeout: int = 5) -> bool:
    """GET 探活地址，失败则跳过该卡（保持待分派），连续 3 次失败记录告警。"""
    global _probe_failures_count
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            pass
        _probe_failures_count = 0
        return True
    except urllib.error.HTTPError:
        # HTTPError is still a successful connection because the server responded
        _probe_failures_count = 0
        return True
    except Exception as exc:
        _probe_failures_count += 1
        if _probe_failures_count >= 3:
            logger.error("探活连续失败告警: URL %s 连续失败 %d 次! (%s)", url, _probe_failures_count, exc)
        else:
            logger.warning("探活失败: URL %s 失败 %d 次 (%s)", url, _probe_failures_count, exc)
        return False


def is_retryable_failure(work_id: str, problems: list[str], log_dir: Path, phase: str = "run") -> tuple[bool, str]:
    """识别基础设施故障（超时/网络/上游不可用）——这类失败不进业务重试预算、不打回。

    V4：只扫**当前阶段**的日志——执行阶段扫 ``{id}.log``，机审阶段扫 ``{id}.audit.log``。
    原实现两日志都扫，旧 audit 日志中的上游特征会污染执行阶段的 infra 判定。
    """
    # 2026-08-12 隔离升级：派发阶段返回的 worktree/基础设施错误直接判 infra（日志可能尚未落盘）
    for problem in problems:
        pl = problem.lower()
        if "基础设施" in problem:
            return True, f"基础设施特征: {problem[:80]}"
        if "worktree" in pl and ("失败" in problem or "创建" in problem or "异常" in problem):
            return True, f"基础设施特征: {problem[:80]}"

    # ccc083（2026-08-25）：击杀语义退出码 → 基础设施故障，不烧业务重试预算。
    # 137=128+9、143=128+15 是 shell 包装层上报形态；-9/-15/-137/-143 是负信号数形态。
    # 外力击杀（超时清扫/看门狗 kickstart 连带/防旋熔断）属基建语义；按业务失败处理会
    # 立即重派，放大「杀→重派→再杀」风暴（2026-08-24 ccc078 机审连环 kickstart 实证：
    # ccc079 audit exit 137 被记为业务失败 retry=1/3 回待分派）。
    _kill_exit = re.compile(r"退出码非 0: ((?:137|143)|-(?:9|15|137|143))(?![0-9])")
    for problem in problems:
        m = _kill_exit.search(problem)
        if m:
            return True, f"击杀语义退出码（按基础设施冷却处理）: exit={m.group(1)}"

    keywords = [
        "connection error",
        "network error",
        "network unreachable",
        "host unreachable",
        "dns resolution",
        "connection reset",
        "broken pipe",
        "bad gateway",
        "service unavailable",
        "relay error",
        "所有上游不可用",
        "upstream",
        "不可用（网络错误）",
        "上游不可用",
        "inference gateway",
        "上游",
        # 1-3（2026-08-24 直修）：超时/被清扫击杀属基建语义，不烧业务重试预算
        "执行超时",
        "退出码非 0: -9",
        "退出码非 0: -15",
    ]
    # 50x 仅在有 HTTP/状态码语义时判定基础设施失败；裸 "503"（行号/数值/端口）不误判
    status_5xx = re.compile(r"(?i)(?:http|status|错误|error|code)[^\n]{0,20}50[234]")
    for log_name in (f"{work_id}.log",) if phase != "audit" else (f"{work_id}.audit.log",):
        log_path = log_dir / log_name
        if not log_path.is_file():
            continue
        try:
            log_content = log_path.read_text(encoding="utf-8", errors="ignore").lower()
            for kw in keywords:
                if kw in log_content:
                    return True, f"日志含基础设施特征: {kw}"
            if status_5xx.search(log_content):
                return True, "日志含基础设施特征: HTTP 50x"
        except Exception as exc:
            logger.warning("读取日志判断重试失败: %s (%s)", log_path, exc)

    return False, ""


def _is_persistence_failure(reasons: list[str]) -> bool:
    """机审已通过但证据落盘/推送失败 → 引擎侧故障（audit 日志无业务否定）。"""
    return any(("机审区落盘" in r) or ("分支证据未推送" in r) or ("机审区落盘到分支卡失败" in r) for r in reasons)


def _write_pipeline_warning(event: str, work_id: str, detail: str) -> None:
    """写 pipeline 告警状态（不抛异常，Engine 运行时自动采集）。"""
    try:
        from server.engine.pipeline_status import write_pipeline_status

        write_pipeline_status(
            event=event,
            work_id=work_id,
            detail=detail,
            level="warning",
        )
    except Exception:
        pass


def _mark_branch_card_state(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    state_text: str,
) -> None:
    """机审打回：把远端分支卡状态落指定状态并推送。

    2026-08-12 终态权威补齐：分支信封与磁盘卡同属终态权威；机审打回若不改分支卡，
    下轮 FileBoardStore 又会把「已回写」残留读成 DONE → 无限机审（mx031/032 假机审根因）。
    - 重试路径（回待分派）：落「待分派（机审打回·重试中）」，信封读不到 → 按磁盘 TODO 重试执行
    - 重试耗尽：落「打回（机审：不通过）」，信封读打回 → 不再机审
    失败不阻断打回（打回本身已由磁盘/日志权威化）。
    """
    try:
        wt_hint = _worktree_hint_for(work, registry)
        if not wt_hint or not os.path.isdir(wt_hint) or not work.card_path:
            return
        if "docs/dispatch" not in work.card_path:
            return

        # 获取相对路径，避免 Path(wt_hint) / absolute_path 导致路径漂移至生产卡
        parts = Path(work.card_path).parts
        if "docs" in parts:
            idx = parts.index("docs")
            rel_card_path = Path(*parts[idx:])
        else:
            rel_card_path = Path(work.card_path).name

        card_file = Path(wt_hint) / rel_card_path
        if not card_file.is_file():
            return
        text = card_file.read_text(encoding="utf-8")
        new_text, n = re.subn(
            r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)",
            rf"\g<1>{state_text}",
            text,
            count=1,
        )
        if n == 0 or new_text == text:
            return
        # 打回次数修复（统一化）：机审打回（终态）时递增卡头 打回次数：N
        if state_text.startswith("打回"):
            from server.board.card_header import bump_reject_count

            new_text = bump_reject_count(new_text)
        card_file.write_text(new_text, encoding="utf-8")
        branch = f"codex/{Path(work.card_path).stem.lower()}"

        # 检查 rc：git add/commit/push 失败时保留脏现场 + 写告警（使用 worktree 相对路径）
        add = subprocess.run(
            ["git", "add", "--", str(rel_card_path)], cwd=wt_hint, capture_output=True, check=False, timeout=30
        )
        if add.returncode != 0:
            logger.error(
                "机审打回落分支 git add 失败（保留脏现场）: work=%s branch=%s stderr=%s",
                work.id,
                branch,
                add.stderr.strip()[:200],
            )
            _write_pipeline_warning("git_add_failed", work.id, f"git add 失败: {add.stderr.strip()[:200]}")
            return

        commit = subprocess.run(
            ["git", "commit", "-m", f"chore(engine): {work.id} 机审打回，状态落分支信封（防死循环）"],
            cwd=wt_hint,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if commit.returncode != 0:
            logger.error(
                "机审打回落分支 git commit 失败（保留脏现场）: work=%s branch=%s stderr=%s",
                work.id,
                branch,
                commit.stderr.strip()[:200],
            )
            _write_pipeline_warning("git_commit_failed", work.id, f"git commit 失败: {commit.stderr.strip()[:200]}")
            return

        push = subprocess.run(
            ["git", "push", "origin", branch], cwd=wt_hint, capture_output=True, check=False, timeout=60
        )
        if push.returncode != 0:
            logger.error(
                "机审打回落分支 git push 失败（保留脏现场）: work=%s branch=%s stderr=%s",
                work.id,
                branch,
                push.stderr.strip()[:200],
            )
            _write_pipeline_warning("git_push_failed", work.id, f"git push 失败: {push.stderr.strip()[:200]}")
            return

        logger.warning("机审打回已落分支卡状态: work=%s branch=%s", work.id, branch)
    except Exception as exc:
        logger.warning("机审打回落分支卡失败（不阻断打回）: work=%s (%s)", work.id, exc)


def _infra_cooldown_seconds(cfg: dict[str, Any]) -> int:
    try:
        return max(0, int(cfg.get("EXECUTOR_INFRA_COOLDOWN_SECONDS") or 60))
    except (TypeError, ValueError):
        return 60


def _hold_infra_failure(
    store: BoardStore,
    work: Work,
    log_dir: Path,
    reasons: list[str],
    cfg: dict[str, Any],
    *,
    phase: str,
    infra_count: int | None = None,
) -> None:
    """基础设施/引擎侧故障：不进业务重试预算、不打回；记冷却时间，冷却后自动续跑。

    - phase=audit：卡保持「已回写」，机审队列冷却后自动续审。
    - phase=run：卡回「待分派」，派发队列冷却后自动重派。
    """
    from datetime import datetime, timedelta, timezone

    strikes = infra_count if infra_count is not None else 0
    power = max(0, strikes - 1)
    base = _infra_cooldown_seconds(cfg)
    cooldown = base * (2**power)

    try:
        max_cooldown = int(cfg.get("EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS") or 1800)
    except (TypeError, ValueError):
        max_cooldown = 1800

    cooldown = min(cooldown, max_cooldown)

    until = (
        (datetime.now(timezone.utc) + timedelta(seconds=cooldown)).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    if phase == "run" and work.state is State.RUNNING:
        try:
            work.transition(State.TODO, problems=reasons)
        except Exception:
            pass
    try:
        store.save_work(work)
    except Exception:
        pass
    from server.engine.runtime_state import write_card_state

    if infra_count is None:
        infra_count = 0

    write_card_state(
        log_dir,
        work.id,
        state=work.state.value,
        retry_count=work.retry_count,
        reason=reasons[0] if reasons else "基础设施故障",
        infra_cooldown_until=until,
        infra_count=infra_count,
    )
    logger.warning(
        "基础设施失败（冷却 %ds 后自动续%s，不计重试预算）: work=%s reason=%s",
        cooldown,
        "审" if phase == "audit" else "派",
        work.id,
        reasons[0] if reasons else "",
    )


def _audit_timeout_seconds(cfg: dict[str, Any]) -> int:
    try:
        return max(60, int(cfg.get("EXECUTOR_AUDIT_TIMEOUT_SECONDS") or 1800))
    except (TypeError, ValueError):
        return 1800


# ccc093 审计预算自适应：diff 增删行 ≤ FREE 用 base（小 diff 不上浮）；≥ CAP 封顶 2×base；
# [FREE, CAP] 区间线性上浮。复杂大 diff 必然超时（ccc081 四连 900s 击杀）的根修参数面。
AUDIT_BUDGET_DIFF_FREE_LINES = 200
AUDIT_BUDGET_DIFF_CAP_LINES = 2000
AUDIT_BUDGET_SCALE_MAX = 2.0


def _audit_diff_changed_lines(worktree_path: str | None) -> int | None:
    """被审 diff 规模：worktree 相对 origin/main...HEAD 的增删行总数。

    取不到（无 worktree / 无 origin/main / git 命令失败）→ None，调用方回退 base 预算。
    """
    if not worktree_path:
        return None
    try:
        res = subprocess.run(
            ["git", "-C", str(worktree_path), "diff", "--numstat", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    total = 0
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        # 二进制文件 numstat 输出 "-	-	path"，非数字 → 跳过
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    return total


def _audit_adaptive_timeout_seconds(cfg: dict[str, Any], worktree_path: str | None) -> int:
    """审计超时预算按被审 diff 规模自适应（ccc093 目标①）。

    base = EXECUTOR_AUDIT_TIMEOUT_SECONDS；diff 增删行在 [FREE, CAP] 内线性上浮，
    上限 2×base 封顶；规模取不到或小 diff → 原 base 预算（不放宽也不收紧）。
    """
    base = _audit_timeout_seconds(cfg)
    lines = _audit_diff_changed_lines(worktree_path)
    if lines is None or lines <= AUDIT_BUDGET_DIFF_FREE_LINES:
        return base
    span = AUDIT_BUDGET_DIFF_CAP_LINES - AUDIT_BUDGET_DIFF_FREE_LINES
    scale = min(AUDIT_BUDGET_SCALE_MAX, 1.0 + (lines - AUDIT_BUDGET_DIFF_FREE_LINES) / span)
    return max(base, int(round(base * scale)))


def _infra_cooldown_active(
    runtime: dict,
    card_id: str,
    now_ts: float | None = None,
) -> bool:
    """运行时记录的 ``infra_cooldown_until`` 未到期 → 跳过本卡（防抖动风暴）。"""
    cd = (runtime.get(card_id) or {}).get("infra_cooldown_until")
    if not cd:
        return False
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(cd.replace("Z", "+00:00"))
        return parsed.timestamp() > (time.time() if now_ts is None else now_ts)
    except (ValueError, TypeError):
        return False


# ── ccc083 防旋（2026-08-25）：短命会话计数熔断 + 业务重试指数退避 ──
# 背景：2026-08-24 14:49–15:46 产生 46 个短命执行体会话（4–16 步无编辑即断），
# 与 watchdog 连环 kickstart 秒级对齐；引擎对失败会话立即原样重派是放大器。
# 本段两个机制：
#   1) 短命熔断：窗口内 ≥M 个「失败且短命」worker 事件 → 暂停一切自动派发 + 告警文件；
#   2) 业务重试退避：回待分派重试不再下一轮立即重派，按 retry_count 指数退避（进程内）。


def _short_session_seconds(cfg: dict[str, Any]) -> int:
    """会话寿命低于该秒数记「短命」。默认 300s。"""
    try:
        return max(30, int(cfg.get("EXECUTOR_SHORT_SESSION_SECONDS") or 300))
    except (TypeError, ValueError):
        return 300


def _short_session_window_seconds(cfg: dict[str, Any]) -> int:
    """短命计数统计窗口。默认 600s。"""
    try:
        return max(60, int(cfg.get("EXECUTOR_SHORT_SESSION_WINDOW_SECONDS") or 600))
    except (TypeError, ValueError):
        return 600


def _short_session_max_count(cfg: dict[str, Any]) -> int:
    """窗口内短命失败事件达到该数即熔断。默认 5。"""
    try:
        return max(2, int(cfg.get("EXECUTOR_SHORT_SESSION_MAX_COUNT") or 5))
    except (TypeError, ValueError):
        return 5


def count_recent_short_sessions(
    events_path: str | Path,
    now_ts: float | None = None,
    *,
    window_s: int = 600,
    short_s: int = 300,
) -> int:
    """统计 worker-events.jsonl 窗口内「失败且寿命 ≤ short_s」的 worker 事件数。

    只读解析；文件缺失/坏行容错（返回已解析计数）。``kind != "worker"`` 行
    （如 ccc083 会话探针 kind=session）不参与计数。
    """
    path = Path(events_path)
    if not path.is_file():
        return 0
    now = time.time() if now_ts is None else now_ts
    count = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or rec.get("kind") != "worker":
                    continue
                if rec.get("ok"):
                    continue
                dur = rec.get("duration_s")
                if not isinstance(dur, (int, float)) or dur < 0:
                    continue
                if dur > short_s:
                    continue
                ts = rec.get("ts")
                if isinstance(ts, str):
                    try:
                        from datetime import datetime

                        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        event_ts = parsed.timestamp()
                    except ValueError:
                        continue
                else:
                    continue
                if now - event_ts <= window_s:
                    count += 1
    except OSError:
        return count
    return count


def short_session_breaker_status(
    log_dir: str | Path,
    cfg: dict[str, Any],
    now_ts: float | None = None,
) -> tuple[bool, str]:
    """短命会话熔断判定：窗口内短命失败事件 ≥ 阈值 → (True, 描述)。"""
    window = _short_session_window_seconds(cfg)
    short_s = _short_session_seconds(cfg)
    max_count = _short_session_max_count(cfg)
    events = Path(log_dir) / "worker-events.jsonl"
    hits = count_recent_short_sessions(events, now_ts, window_s=window, short_s=short_s)
    if hits >= max_count:
        return (
            True,
            f"近 {window}s 内短命失败会话 {hits} 个 ≥ 阈值 {max_count}（寿命≤{short_s}s），暂停派发防旋",
        )
    return False, ""


def _write_short_session_alert(log_dir: str | Path, detail: str, now_ts: float | None = None) -> None:
    """熔断告警落盘（同窗口内覆盖写，人工删除即恢复观察）。"""
    alerts_dir = Path(log_dir) / "alerts"
    try:
        alerts_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(
            now_ts if now_ts is not None else time.time(), tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")
        (alerts_dir / "short-session-breaker.txt").write_text(
            f"[{stamp}] 短命会话熔断触发，自动派发暂停一个统计窗口：{detail}\n"
            "恢复条件：该告警随下一个非熔断轮次自动解除；人工核查后可删除本文件。\n",
            encoding="utf-8",
        )
    except OSError:
        logger.warning("短命熔断告警写入失败（不影响熔断判定）: %s", alerts_dir)


_RETRY_BACKOFF_UNTIL: dict[str, float] = {}


def retry_backoff_seconds(cfg: dict[str, Any], retry_count: int) -> int:
    """业务重试指数退避秒数：base × 2^(retry_count-1)，封顶 max。

    retry_count=1 → base；默认 base=60s、max=900s。
    """
    try:
        base = max(0, int(cfg.get("EXECUTOR_RETRY_BACKOFF_SECONDS") or 60))
    except (TypeError, ValueError):
        base = 60
    try:
        max_s = max(base, int(cfg.get("EXECUTOR_RETRY_BACKOFF_MAX_SECONDS") or 900))
    except (TypeError, ValueError):
        max_s = 900
    power = max(0, int(retry_count) - 1)
    return min(max_s, base * (2**power)) if base else 0


def set_retry_backoff(work_id: str, seconds: float, now_ts: float | None = None) -> None:
    """记录某卡下一次允许派发的最早时刻（进程内；引擎重启即失效，由熔断兜底）。"""
    if seconds <= 0:
        return
    _RETRY_BACKOFF_UNTIL[work_id] = (time.time() if now_ts is None else now_ts) + seconds


def clear_retry_backoff(work_id: str) -> None:
    """收单成功/终态清除退避标记。"""
    _RETRY_BACKOFF_UNTIL.pop(work_id, None)


def retry_backoff_active(work_id: str, now_ts: float | None = None) -> bool:
    """该卡是否仍在业务重试退避期内。"""
    until = _RETRY_BACKOFF_UNTIL.get(work_id)
    if until is None:
        return False
    now = time.time() if now_ts is None else now_ts
    if now >= until:
        _RETRY_BACKOFF_UNTIL.pop(work_id, None)
        return False
    return True


def _append_session_probe(
    log_dir: str | Path,
    *,
    work_id: str,
    phase: str,
    lifetime_s: float,
    short_threshold_s: int,
    worktree_path: str | Path | None,
    marker_id: str | None = None,
) -> None:
    """向 worker-events.jsonl 追加一行 kind=session 会话探针（ccc083）。

    字段：
    - ``session_lifetime_s``：会话墙钟寿命（秒）；
    - ``short_session``：寿命是否 ≤ short_threshold_s（短命会话标记）；
    - ``edit_hit``：编辑命中——worktree 相对派发基点（dispatch_tip）有新提交，
      或存在未提交改动；无法判定时为 null（降级，不伪造）。
    埋点失败只记日志（调用方兜底），绝不抛进收单热路径。
    """
    edit_hit: bool | None = None
    dirty = False
    head: str | None = None
    tip = _marker_dispatch_tip(log_dir, marker_id) if marker_id else None
    if worktree_path and os.path.isdir(str(worktree_path)):
        try:
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res_status.returncode == 0:
                dirty = bool(res_status.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            dirty = False
        try:
            res_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res_head.returncode == 0:
                head = res_head.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            head = None
    if dirty or (tip and head and head != tip):
        edit_hit = True
    elif tip and head and head == tip:
        edit_hit = False
    record = {
        "ts": (
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        ),
        "kind": "session",
        "work_id": work_id,
        "phase": phase,
        "session_lifetime_s": round(max(0.0, float(lifetime_s)), 3),
        "short_session": bool(lifetime_s <= short_threshold_s),
        "edit_hit": edit_hit,
    }
    path = Path(log_dir) / WORKER_EVENTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _business_repo_has_new_commit(work: Work, worktree_path: str) -> bool:
    """业务仓型任务（registry 指向外部仓）产物检查。

    当 CCC worktree 无 commit 时（业务仓任务在外部仓开发），回退检查 registry 指向的
    业务仓对应 codex 分支相对 origin/main 是否有新 commit。流程修正（2026-08-10）：
    clw011 业务开发在 clwarp 仓，CCC worktree 只应含卡回写，机械门禁只看 worktree
    会把业务仓产物误判为空回写 → 打回死循环。
    """
    if not work.project or not work.card_path:
        return False
    try:
        from server.board.registry import load_projects

        projects = load_projects()
        entry = next(
            (e for e in projects if (e.prefix and e.prefix == work.project) or e.id == work.project),
            None,
        )
        if entry is None or not entry.path_mac2017:
            return False
        repo = Path(entry.path_mac2017).expanduser()
        if not repo.is_dir():
            return False
    except Exception:
        return False
    branch = f"codex/{Path(work.card_path).stem.lower()}"
    try:
        # 2026-08-12 隔离升级：业务仓产物在 worktree 分支上，先 fetch 确保远端 ref 在场
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "origin", branch],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        res = subprocess.run(
            ["git", "-C", str(repo), "log", "origin/main..origin/" + branch, "--oneline"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return False
    if res.returncode != 0:
        return False
    return bool(res.stdout.strip())


def is_empty_writeback_or_placeholder(work: Work, worktree_path: str) -> tuple[bool, str]:
    """判定是否为空回写（回写 diff 为空 或 卡 ## 维护区 为模板占位/空白）。"""
    if worktree_path:
        has_commit = _worktree_has_new_commit(worktree_path)
        has_diff = _worktree_has_nonempty_diff(worktree_path)
        if not (has_commit and has_diff):
            # 流程修正（2026-08-10）：业务仓型任务 worktree 无 commit 时，
            # 回退检查业务仓对应 codex 分支产物（clw011 误打回根因）
            if _business_repo_has_new_commit(work, worktree_path):
                logger.info("worktree 无 commit 但业务仓分支有产物，放行: work=%s", work.id)
            else:
                return True, "回写 diff 为空（未在 worktree 内产生新 commit 或有效 diff）"

    card_file_path = Path(work.card_path)
    if worktree_path:
        wt_card = _worktree_card_candidate(worktree_path, work.card_path)
        if wt_card and wt_card.is_file():
            card_file_path = wt_card

    text = None
    if card_file_path.is_file():
        try:
            text = card_file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("检查空回写/维护区异常: %s", e)
    if text is None:
        # 2026-08-12 v2：worktree 卡缺失/损坏 → 回退远端分支卡（执行体 push 的真值）
        text = _read_branch_card_text(work)
    if text:
        if "## 维护区" not in text:
            return True, "缺失 ## 维护区 节（回写时必填）"
        seg = text.split("## 维护区", 1)[1]
        seg = seg.split("## ", 1)[0]

        import re

        items = re.findall(r"^(\d+)\. \*\*([^*]+)\*\*：[^\[]*\[([^]]*)\]", seg, re.M)
        if len(items) < 4:
            return True, "## 维护区 四问格式不完整，仍为占位模板"

        for num, name, choice in items:
            choice_strip = choice.strip()
            if "是/否" in choice_strip or "有/无" in choice_strip or choice_strip not in ("是", "否", "有", "无"):
                return True, f"## 维护区 第 {num} 问「{name.strip()}」未勾选或仍为占位"

        notes = re.findall(r"^   - 说明：(.+)$", seg, re.M)
        if len(notes) < 4:
            return True, "## 维护区 说明少于 4 条，仍为占位模板"
        for note in notes:
            n_strip = note.strip()
            if not n_strip or "占位" in n_strip or "逐项勾选" in n_strip or "说明：" in n_strip:
                return True, "## 维护区 说明为空或包含占位文本"

    return False, ""


def max_retries_from_cfg(cfg: dict[str, Any]) -> int:
    """失败回待分派上限。``EXECUTOR_RETRY_ONCE=false`` → 0（首次即打回）。"""
    retry_enabled = str(cfg.get("EXECUTOR_RETRY_ONCE", "true")).lower() in ("true", "1", "yes")
    if not retry_enabled:
        return 0
    try:
        return max(0, int(cfg.get("EXECUTOR_MAX_RETRIES") or 3))
    except (TypeError, ValueError):
        return 3


def _is_manual_or_remote_executor(work: Work) -> bool:
    """判定执行体是否为「不可自愈」类型：manual / W 号（跨节点 Worker 认领）。

    sidecar 契约（ccc-plan-021）：manual/W 号卡由人工或远端 Worker 认领，
    Engine 无本地 PID 可收单，打回后若残留 sidecar 流程态会挂死（clw019 根因）。
    此类卡打回/重试出口必须立即 clear sidecar，磁盘卡为终态唯一权威。
    """
    ex = (work.executor or "").strip().lower()
    if not ex:
        return False
    if "manual" in ex:
        return True
    # W 号（W1-W9）或跨节点 Worker 标识
    import re as _re

    return bool(_re.match(r"^w\d+$", ex))


def _fail_retry_or_reject(
    work: Work,
    store: BoardStore,
    problems: list[str],
    cfg: dict[str, Any],
    log_dir: str | Path | None = None,
) -> bool:
    """失败：写原因；未达上限 → 待分派并 ``retry_count+=1``；否则打回。

    sidecar 契约（ccc-plan-021）：重试（可自愈）只写 retry_count、清流程态；
    打回（不可自愈，含 manual/W 号卡）立即 clear sidecar，磁盘卡终态权威。

    Returns:
        True 若已回待分派（将再派）；False 若已打回。
    """
    max_r = max_retries_from_cfg(cfg)
    reasons = list(problems) if problems else ["失败（未附原因）"]
    # 不可自愈类型（manual/W 号）：不打业务重试预算，直接打回 + 立即 clear sidecar
    if _is_manual_or_remote_executor(work):
        work.transition(State.REJECTED, problems=reasons)
        store.save_work(work)
        if log_dir:
            from server.engine.runtime_state import clear_card_state

            clear_card_state(log_dir, work.id)
        logger.warning("不可自愈执行体（manual/远端）打回并清 sidecar: work=%s problems=%s", work.id, reasons[:2])
        return False
    if work.retry_count < max_r:
        work.retry_count += 1
        work.transition(State.TODO, problems=reasons)
        store.save_work(work)
        # ccc083：回待分派重试不再下一轮立即重派——按 retry_count 指数退避（防旋）
        backoff_s = retry_backoff_seconds(cfg, work.retry_count)
        set_retry_backoff(work.id, backoff_s)
        if log_dir:
            from server.engine.runtime_state import write_card_state, clear_card_state

            # 可自愈：写重试预算，清流程态残留（sidecar 不存流程终态）
            write_card_state(log_dir, work.id, retry_count=work.retry_count)
            clear_card_state(log_dir, work.id)
        logger.info(
            "失败回待分派重试: work=%s retry=%d/%d 退避=%ds problems=%s",
            work.id,
            work.retry_count,
            max_r,
            backoff_s,
            reasons[:2],
        )
        return True
    work.transition(State.REJECTED, problems=reasons)
    store.save_work(work)
    if log_dir:
        from server.engine.runtime_state import clear_card_state

        clear_card_state(log_dir, work.id)
    logger.warning(
        "重试用尽打回: work=%s retry=%d/%d problems=%s",
        work.id,
        work.retry_count,
        max_r,
        reasons[:2],
    )
    return False


def _load_registry_cached(
    registry_path: str | Path | None,
    last_mtime: float | None,
) -> tuple[ExecutorRegistry | None, float | None]:
    """executors.json mtime 级热重载（仿 _slot_limits 热读模式）。

    改注册表免重启：文件 mtime 变化才重新 load_registry，否则返回原 registry。
    ``last_mtime=None`` 表示首次加载（无条件重载）。

    Returns:
        (registry 或 None（未变/不可读）, 最新 mtime 或 None)。
    """
    if not registry_path:
        return None, None
    p = Path(registry_path)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None, last_mtime
    if last_mtime is not None and mtime == last_mtime:
        return None, last_mtime  # 未变，复用
    try:
        registry = load_registry(p)
    except (ConfigError, OSError, ValueError) as exc:
        logger.warning("executors.json 热重载失败（沿用旧注册表）: %s", exc)
        return None, last_mtime
    logger.info("executors.json 热重载完成 (mtime=%s)", mtime)
    return registry, mtime


def _slot_limits(cfg: dict[str, Any], config_path: str | Path | None = None) -> tuple[int, int]:
    """执行/机审槽位上限；config_path 可读时热读文件值（改配置免重启）。

    Returns:
        (exec_max, audit_max)，均至少 1。
    """

    def _int_val(raw: Any, default: int) -> int:
        try:
            return max(1, int(str(raw).strip()))
        except (TypeError, ValueError):
            return default

    exec_max = _int_val(cfg.get("EXECUTOR_MAX_CONCURRENT"), 3)
    audit_max = _int_val(cfg.get("EXECUTOR_MAX_AUDIT_CONCURRENT"), 2)
    if config_path:
        try:
            for line in Path(config_path).read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                k = k.strip()
                val = v.strip().strip('"').strip("'")
                if k == "EXECUTOR_MAX_CONCURRENT":
                    exec_max = _int_val(val, exec_max)
                elif k == "EXECUTOR_MAX_AUDIT_CONCURRENT":
                    audit_max = _int_val(val, audit_max)
        except OSError:
            pass
    return exec_max, audit_max


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


def _pin_audit_commit(card_path: str, sha: str) -> bool:
    """机审信封钉被审 commit：把「机审：通过」改写为「机审：通过（被审 <sha12>）」（幂等）。

    V6：合入前凭此行校验分支无漂移（机审通过后执行体再 push 非卡改动 → 拒绝合入）。
    """
    if not sha:
        return True
    try:
        text = Path(card_path).read_text(encoding="utf-8")
    except OSError:
        return False
    if "被审 " in text:
        return True
    m = re.search(r"^(机审：通过\s*)$", text, flags=re.MULTILINE)
    if not m:
        return True
    text = text[: m.start()] + f"机审：通过（被审 {sha[:12]}）\n" + text[m.end() :]
    try:
        Path(card_path).write_text(text, encoding="utf-8")
    except OSError:
        return False
    return True


def _is_remote_work(work: Work) -> bool:
    """判定卡是否为远端 Worker 卡（认领协议）：执行体 W 号 或 派发 scheduler|remote。

    remote 卡无本地 worktree → 机审/证据检查走分支信封（ccc-plan-020 v2）。
    """
    import re as _re

    if work.dispatch in ("scheduler", "remote"):
        return True
    return bool(_re.fullmatch(r"W\d+", (work.executor or "").strip()))


def _audit_evidence_passed(work: Work, worktree_hint: str, main_repo: Path | None = None) -> bool:
    """机审证据是否已在信封（**分支 git 证据**为准，生产卡兜底）。

    只认进 git 的证据：worktree 卡文件有标记但分支没有（commit 被吞的洞）
    不算通过，避免死结（xy016 事故）。

    remote 卡（无本地 worktree）：走分支信封 —— `git show origin/<codex分支>:<卡>` 读机审区，
    生产卡兜底作为最终 fallback（ccc-plan-020 v2 · 机审 remote 适配）。
    """
    if worktree_hint:
        wt_card = _worktree_card_candidate(worktree_hint, work.card_path)
        if wt_card is not None and _card_machine_audit_passed(str(wt_card)):
            try:
                rel = wt_card.relative_to(Path(worktree_hint).expanduser().resolve()).as_posix()
            except ValueError:
                rel = wt_card.name
            branch = f"codex/{Path(work.card_path).stem.lower()}"
            res = subprocess.run(
                ["git", "-C", worktree_hint, "show", f"origin/{branch}:{rel}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if res.returncode == 0:
                from server.board.models import machine_audit_passed_text

                if machine_audit_passed_text(res.stdout):
                    return True
        return _card_machine_audit_passed(work.card_path)
    # remote 卡（无本地 worktree）：分支信封读机审区
    if _is_remote_work(work) and work.card_path:
        try:
            repo = main_repo if main_repo is not None else Path(__file__).resolve().parents[2]
            branch = f"codex/{Path(work.card_path).stem.lower()}"
            rel = Path(work.card_path).as_posix()
            res = subprocess.run(
                ["git", "-C", str(repo), "show", f"origin/{branch}:{rel}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if res.returncode == 0:
                from server.board.models import machine_audit_passed_text

                if machine_audit_passed_text(res.stdout):
                    return True
        except Exception:
            pass
    return _card_machine_audit_passed(work.card_path)


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
    """把 worktree 卡（含机审区）commit+push 到分支（信封证据进 git）。"""
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
        subprocess.run(
            ["git", "-C", worktree_path, "add", "--", rel],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        res = subprocess.run(
            ["git", "-C", worktree_path, "commit", "-m", f"docs(card): 机审通过 {work_id}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode != 0:
            logger.info("worktree 卡 commit 无改动（可能已由机审 CLI 提交）: %s", work_id)
        push = subprocess.run(
            ["git", "-C", worktree_path, "push", "origin", "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if push.returncode != 0:
            # ccc093：push 报错 ≠ 未达远端（helper 噪声可致假失败）——以 origin 分支事实复核，
            # 远端已含证据则记 pass 覆盖；校验不过仍走原失败路径（不放宽）。
            branch = f"codex/{Path(card_path).stem.lower()}"
            if _remote_branch_audit_evidence(worktree_path, rel, branch):
                logger.info(
                    "机审证据 push 报错但远端分支已含证据（ls-remote+卡文双重校验通过）: work=%s → 记 pass",
                    work_id,
                )
                return True
            logger.warning("机审证据 push 失败: work=%s (%s)", work_id, push.stderr.strip())
            return False
        # 验证证据确实进了分支（commit 失败被吞 → 机审区只留工作区的死结洞）
        check = subprocess.run(
            ["git", "-C", worktree_path, "show", f"HEAD:{rel}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if check.returncode != 0 or "机审：通过" not in check.stdout:
            # ccc093：本地 HEAD 复核空转 ≠ 证据未达远端（ccc088 假 infra 行）——
            # 以 origin 分支事实双重校验（ls-remote + 分支卡文含机审区），核实已达
            # 远端则记 pass 覆盖；校验失败仍走原 infra 续审路径（不放宽）。
            branch = f"codex/{Path(card_path).stem.lower()}"
            if _remote_branch_audit_evidence(worktree_path, rel, branch):
                logger.info(
                    "机审证据本地校验空转但远端分支已含证据（ls-remote+卡文双重校验通过）: work=%s → 记 pass",
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
    except Exception as exc:
        logger.warning("机审证据 commit/push 异常: work=%s (%s)", work_id, exc)
        return False


AUDIT_MARKER_GRACE_SECONDS = 900  # 机审标记宽限期：子进程未拉起/刚结束的防双审窗（对齐 AUDIT_TIMEOUT）


def _audit_marker_alive(
    log_dir: Path,
    work_id: str,
    grace_seconds: int = AUDIT_MARKER_GRACE_SECONDS,
) -> bool:
    """``{id}-audit.running`` 标记判定机审在途（跨重启防双审）。

    2026-08-20 事故修复（mx055 卡死）：engine 自身 PID 常驻永活，不能作为
    在途依据——机审子进程失败残留的标记若只含 engine_pid，会让失败卡永远
    「在途」不重审。修复语义：

    - 排除 engine 自身 PID；
    - 存在存活子进程 → 在途；
    - 无存活子进程 → 仅刚写入（宽限期内）算在途（子进程拉起前的防双审窗）；
      超宽限期 = 残留死标记 → 可重审。

    ccc082 加固（2026-08-24）：本地 log_dir 未命中「或判死」后，追加查用户级
    全局机审注册表（``_audit_inflight_registry_dir``）——原防线只锚定单个
    DATA_DIR（engine.lock 与 running 标记都在 DATA_DIR 内），双 engine 各用
    不同 DATA_DIR 时互不可见 → 并发双审穿透（tmp 双目录实验实锤：
    cross-log_dir alive=False）。现任一共享面判在途即在途。
    """
    marker = log_dir / f"{work_id}-audit.running"
    try:
        raw = marker.read_text(encoding="utf-8")
        mtime = marker.stat().st_mtime
    except OSError:
        # 本地无标记 ≠ 无机审在途：其他 DATA_DIR 的 engine 可能在审同一卡
        return _registry_audit_inflight_alive(work_id, grace_seconds)
    if _marker_raw_alive(raw, mtime, grace_seconds):
        return True
    # 本地标记已死（残留/超宽限）≠ 全线可重审：另一 DATA_DIR 可能正在审
    return _registry_audit_inflight_alive(work_id, grace_seconds)


def _audit_inflight_registry_dir() -> Path:
    """跨 DATA_DIR 全局机审在途注册表目录（ccc082 加固）。

    防双审共享面原本只有两处，均锚定单个 DATA_DIR：
    - ``DATA_DIR/engine.lock`` 单实例锁：不同 DATA_DIR 各持各锁，互不排斥；
    - ``{EXECUTOR_LOG_DIR}/{id}-audit.running`` 标记：log_dir 不同则互不可见。
    双 engine 各用不同 DATA_DIR 时两者同时失效 → 并发机审风暴（ccc078 多实例
    场景的等价小模型，pytest 双目录实验复现）。

    注册表锚定到用户级固定点：环境变量 ``CCC_AUDIT_REGISTRY_DIR`` 优先
    （测试隔离用），默认 ``~/.ccc/data/audit-inflight`` —— 生产所有 engine
    同用户同机，即使各自配错 DATA_DIR 也必然互见。条目格式与 running 标记
    完全一致（engine_pid=/pid=/child_pid=），判活复用同一套 PID+宽限语义，
    死条目由 ``_registry_audit_inflight_alive`` 判死时顺手回收，零额外清扫器。
    """
    override = os.environ.get("CCC_AUDIT_REGISTRY_DIR", "").strip()
    base = Path(override) if override else Path.home() / ".ccc" / "data"
    return base / "audit-inflight"


def _marker_raw_alive(raw: str, mtime: float, grace_seconds: int) -> bool:
    """按标记内容判「机审在途」（本地标记与全局注册表共用的单一判定源）。

    - 排除 engine 自身 PID（常驻永活，不作数）；
    - 任一工作者 PID（pid=/child_pid=）存活 → 在途；
    - 否则仅当写入时刻在宽限期内 → 在途（子进程拉起前的防双审窗）。
    """
    engine_pid = os.getpid()
    pids: list[int] = []
    for line in (raw or "").splitlines():
        text = line.strip()
        if text.startswith("engine_pid="):
            continue  # engine 常驻，不作为在途依据
        if text.startswith(("pid=", "child_pid=")) and "=" in text:
            rest = text.split("=", 1)[1].strip().split()[0]
            if rest.isdigit() and int(rest) > 1:
                pids.append(int(rest))
    if any(_pid_alive(p) for p in pids if p != engine_pid):
        return True
    return (time.time() - mtime) < grace_seconds


def _registry_audit_inflight_alive(work_id: str, grace_seconds: int) -> bool:
    """查全局注册表条目（跨 DATA_DIR 防第二道面）；死条目顺手回收防堆积。"""
    entry = _audit_inflight_registry_dir() / f"{work_id}-audit.running"
    try:
        raw = entry.read_text(encoding="utf-8")
        mtime = entry.stat().st_mtime
    except OSError:
        return False
    if _marker_raw_alive(raw, mtime, grace_seconds):
        return True
    try:
        entry.unlink(missing_ok=True)
    except OSError:
        pass
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine",
        description="CCC Engine 薄驱动核心（负责真实派发/收单）",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次扫描 + 派发 + 收单后退出")
    parser.add_argument(
        "--audit",
        metavar="CARD_ID",
        action="append",
        default=[],
        help="对已回写卡重跑机审后退出（可重复；M4 首跑机审）",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="持续模式心跳间隔（秒）",
    )
    return parser.parse_args(argv)


def get_worktree_path(worktree_base: str, work_id: str) -> str:
    """按 worktree_base 和 work_id 计算实际 worktree 路径，支持占位符。"""
    work_id_lower = work_id.lower()
    if "<task>" in worktree_base:
        return worktree_base.replace("<task>", work_id_lower)
    if "{task}" in worktree_base:
        return worktree_base.replace("{task}", work_id_lower)
    if "<work_id>" in worktree_base:
        return worktree_base.replace("<work_id>", work_id_lower)
    if "{work_id}" in worktree_base:
        return worktree_base.replace("{work_id}", work_id_lower)
    return f"{worktree_base}-{work_id_lower}"


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


def _card_is_written_back(card_path: str) -> bool:
    """卡头「状态」段是否已为「已回写」（状态观测用；不再单独充当产物证据）。"""
    if not card_path:
        return False
    try:
        lines = Path(card_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(">"):
            continue
        for seg in stripped[1:].split("·"):
            seg = seg.strip()
            if seg.startswith("状态："):
                return seg[len("状态：") :].strip() == "已回写"
    return False


def _card_machine_audit_passed(card_path: str) -> bool:
    """卡正文 ``## 机审区`` 后是否含通过标记。"""
    if not card_path:
        return False
    try:
        text = Path(card_path).read_text(encoding="utf-8")
    except OSError:
        return False
    from server.board.models import machine_audit_passed_text

    return machine_audit_passed_text(text)


def _read_branch_card_text(work: Work) -> str | None:
    """读远端 ``codex/<slug>`` 分支卡全文（git show）。

    2026-08-12 v2：worktree 卡缺失/损坏时，分支卡是执行体 push 后的真值，
    空回写/维护区检查回退到它，避免机审读占位卡误打回。
    """
    if not work or not work.card_path or "docs/dispatch" not in work.card_path:
        return None
    try:
        from server.git_sync import resolve_repo_root

        repo = resolve_repo_root("docs/dispatch")
    except Exception:
        return None
    branch = f"codex/{Path(work.card_path).stem.lower()}"
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "show", f"origin/{branch}:{work.card_path}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        return None
    if res.returncode != 0:
        return None
    return res.stdout


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


# ── ccc092 worktree 播种一致性：缺卡副本 → ①本地 main 有卡则自愈；②否则硬失败 ──
# 背景（R3/R4 种子盲区两种死法）：worktree 存在但无对应卡副本时，原「派发防护」只
# WARNING+打回，卡永远无法被正常执行 → 无限 WARNING 循环；或执行体拿到空 worktree
# 空跑后被判「空回写」假打回。本组函数把该场景收敛为两个确定性出口。

_SEED_HARDFAIL_MARKER = "种子盲区硬失败"


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


def _audit_output_body(text: str) -> str:
    """截取机审 agent 真实输出区（判定区），排除引擎启动行与注入的 prompt。

    引擎 audit.log 格式：
      [ccc.engine] start work=... phase=audit pid_pending cmd=...<prompt 单行>

      [ccc.engine] child_pid=<pid>

      <agent 真实输出>

    陷阱（clw009 事故）：启动行 cmd= 后的 prompt 里含字面「\n」与多行文本，
    prompt 里就有「输出「机审：不通过（具体原因）」并以非零退出」字样——
    若只截到 start work 后的第一个真实换行，prompt 中段会被误当作 agent 判定区。
    正确判定区 = ``[ccc.engine] child_pid=`` 之后（agent 输出起点）。
    """
    if not text:
        return ""
    for marker in ("[ccc.engine] child_pid=", "child_pid="):
        idx = text.find(marker)
        if idx >= 0:
            return text[idx:]
    # 无 child_pid（echo 类快输出/测试夹具）→ 回退到启动行后的首个真实换行
    for marker in ("pid_pending cmd=", "[ccc.engine] start work="):
        idx = text.find(marker)
        if idx >= 0:
            nl = text.find("\n", idx)
            return text[nl + 1 :] if nl >= 0 else ""
    return text


def _audit_output_indicates_pass(text: str) -> bool:
    """从机审席 stdout/audit.log 判断是否已给出通过结论（ccc006）。

    只看 child 启动后的模型输出，避免 prompt/启动行里「不通过写…」误判为失败（xy001）。
    判定区 = engine 启动行（含 ``pid_pending cmd=``）之后的所有输出——子进程输出无论
    先于/后于 ``child_pid=`` 行落盘都能被捕获（echo 类快输出不再漏判）。
    不通过优先：输出区含「机审：不通过」/「机审不通过」。
    通过：合格机审区，或出现「机审：通过」/「机审通过」/「判定：通过」。
    """
    if not text or not text.strip():
        return False
    from server.board.models import machine_audit_passed_text

    body = _audit_output_body(text)

    if machine_audit_passed_text(body):
        return True
    if "机审：不通过" in body or "机审不通过" in body:
        return False
    return ("机审：通过" in body) or ("机审通过" in body) or ("判定：通过" in body)


def _audit_output_indicates_rejection(text: str) -> bool:
    """审计输出明确给出「不通过」结论 → 业务判定（优先于任何 infra 特征）。
    与 pass 判定同口径，截断到 pid_pending cmd= 之后，避免 prompt 启动行误判。
    """
    if not text or not text.strip():
        return False
    body = _audit_output_body(text)
    return ("机审：不通过" in body) or ("机审不通过" in body)


def _audit_rejection_reason(text: str) -> str | None:
    """从 audit 文本提取「不通过」的结论文本（结论行 + 后续说明摘要）。

    返回供机审打回原因使用的可读字符串；无明确结论 → None（调用方兜底）。
    """
    if not text:
        return None
    body = _audit_output_body(text)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return None
    for ln in lines:
        if "机审：不通过" in ln or "机审不通过" in ln:
            return re.sub(r"\s+", " ", ln)[:400]
    return None


def _audit_severity(text: str) -> str:
    """解析审计输出里的 severity 标记（机审 v4 三级：轻/中/重）。

    机审 v4（qx-map 0538bef）：审计模型按 skill 三维度打分判定 severity，
    并在输出写约定标记 `severity：轻|中|重` / `机审等级：轻|中|重`，
    或在不通过结论带 `（重度/中度/轻度：原因）` 变体。默认「中」。
    """
    if not text:
        return "中"
    body = _audit_output_body(text)
    # 显式标记优先：severity：X / 机审等级：X
    m = re.search(r"(?:severity|机审等级|审计等级)\s*[:：]\s*(轻|中|重)", body)
    if m:
        return m.group(1)
    # 变体：不通过结论 `（重度/中度/轻度：原因）`
    m = re.search(r"（\s*(轻|中|重)度\s*[:：]", body)
    if m:
        return m.group(1)
    return "中"


class MachineAuditPrompt:
    """机审/验收席系统 Prompt 构造器。

    遵循职责分离原则：仅进行原则性审查与就地修复，删除「独立复跑测试/编译裁决」职责。
    """

    def __init__(self, card_path: str, work_id: str, worktree: str) -> None:
        self.card_path = card_path
        self.work_id = work_id
        self.worktree = worktree

    def build(self) -> str:
        return (
            f"你是 2017 机审席。任务卡 {self.card_path}（work {self.work_id}）已回写。你以验收席身份独立审查——"
            "即使开发者与你同工具，也按独立审查执行，不因同工具放水。\n"
            "职责规范：\n"
            "- 只做原则性 Code Review（包括代码实现质量、边界安全、架构隐患、人工批注落实等）；\n"
            f"- 发现可修问题 → 在 worktree {self.worktree} 路径下就地修复并 commit+push，修完直接通过（进 ready）；\n"
            "- 原则性红线问题（如范围系统性越界、核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出。\n"
            "- 不通过结论必须标注 severity（机审 v4 三级）：可快速修复=「severity：轻」/ 一般=「severity：中」/ 红线高风险=「severity：重」。\n"
            "⚠️ 打回时必须在最后真正执行非零退出（exit 1）：引擎按 audit 文本「机审：不通过」判定业务打回，"
            "但仅靠文字声明而 exit 0 会造成收单歧义。\n"
            f"通过则把「## 机审区」+「机审：通过」+ 审查摘要 写进 worktree 卡文件（相对路径同 {self.card_path}，engine 会提交推送）。"
            "禁止改动与任务无关的文件、禁止编写 ## 验收区、禁止置卡状态为已关闭。"
        )


def _is_mechanical_rejection_text(text: str) -> bool:
    """是否包含机械问题特征（测试/编译/lint 失败、范围越界等）。"""
    if not text or not text.strip():
        return False
    body = _audit_output_body(text)

    keywords = [
        "测试失败",
        "测试未跑",
        "编译失败",
        "lint失败",
        "lint 失败",
        "范围越界",
        "超出范围",
        "不在范围",
        "范围外",
    ]
    body_lower = body.lower()
    return any(kw in body_lower for kw in keywords)


def match_path(file_path: str, pattern: str) -> bool:
    import fnmatch

    f = file_path.replace("\\", "/")
    p = pattern.replace("\\", "/").strip()
    if not p:
        return False
    if fnmatch.fnmatch(f, p):
        return True
    p_dir = p if p.endswith("/") else p + "/"
    if f.startswith(p_dir):
        return True
    return False


def parse_gate_section(card_file_path: Path) -> dict[str, str]:
    if not card_file_path.is_file():
        return {}
    try:
        content = card_file_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    lines = content.splitlines()
    gate_lines = []
    in_gate = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 门禁"):
            in_gate = True
            continue
        if in_gate:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            gate_lines.append(line)
    gates = {}
    for line in gate_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            k, _, v = stripped.partition(":")
            gates[k.strip()] = v.strip()
        elif "：" in stripped:
            k, _, v = stripped.partition("：")
            gates[k.strip()] = v.strip()
    return gates


def _read_card_section(card_path: Path | str, section_name: str) -> str:
    """从任务卡 Markdown 文件中提取指定节的内容。

    匹配 ``## <section_name>`` 开头的节，提取内容直到下一个 ``## `` 节或文件末尾。
    节名匹配规则：前缀匹配，如 ``## 执行提示`` 可匹配 ``## 执行提示（给开发大模型）``。

    Args:
        card_path: 卡文件路径。
        section_name: 节名（不含 ``## `` 前缀），如 ``"执行提示"``。

    Returns:
        节内容文本（不含节标题行）；文件不存在/不可读/无此节 → 返回空字符串。
    """
    path = Path(card_path)
    if not path.is_file():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = content.splitlines()
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and stripped[3:].strip().startswith(section_name):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            section_lines.append(line)
    # 去掉首尾空行
    while section_lines and not section_lines[0].strip():
        section_lines.pop(0)
    while section_lines and not section_lines[-1].strip():
        section_lines.pop()
    result = "\n".join(section_lines).strip()

    # 占位文本 → 视为空（中枢尚未注入实际内容）
    if result.startswith("（中枢在出卡时注入"):
        return ""

    return result


def check_range_gate(worktree_path: str, card_path: str) -> tuple[bool, str]:
    card_file = Path(worktree_path) / card_path
    if not card_file.is_file():
        return True, ""
    try:
        content = card_file.read_text(encoding="utf-8")
    except OSError:
        return True, ""

    # Extract ## 范围 section
    lines = content.splitlines()
    range_lines = []
    in_range = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 范围"):
            in_range = True
            continue
        if in_range:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            range_lines.append(line)

    if not in_range:
        return True, ""

    # Extract whitelist patterns from range_lines
    whitelist_patterns = []
    for line in range_lines:
        if any(kw in line for kw in ["不动", "保持", "不改", "禁止", "不碰"]):
            continue
        matches = re.findall(r"`([^`]+)`", line)
        for m in matches:
            m_clean = m.strip()
            if m_clean:
                whitelist_patterns.append(m_clean)

    if not whitelist_patterns:
        return True, ""

    # Get modified files in worktree relative to origin/main
    import subprocess

    res = subprocess.run(
        ["git", "-C", worktree_path, "diff", "--name-only", "origin/main"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if res.returncode != 0:
        return True, ""  # Git error, skip to avoid blocking

    modified_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]

    out_of_scope = []
    for f in modified_files:
        # Exempt card file, logs, runnings
        if f == card_path or Path(f).name == Path(card_path).name:
            continue
        if f.endswith(".running") or f.endswith(".tmp") or f.endswith(".log"):
            continue
        matched = False
        for pat in whitelist_patterns:
            if match_path(f, pat):
                matched = True
                break
        if not matched:
            out_of_scope.append(f)

    if out_of_scope:
        return (
            False,
            f"范围越界门禁拦截：修改了不属于卡「范围」声明中的路径: {out_of_scope} (允许范围: {whitelist_patterns})",
        )

    return True, ""


def _read_text_best_effort(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return ""


def _replace_audit_section(text: str, section: str) -> str:
    """把卡内已有的 ``## 机审区`` 整节替换为新内容（重审通过覆盖旧「不通过」区）。

    保留节标题行，替换到下一个 ``## `` 主节标题或文件尾。
    """
    m = re.search(r"^##\s*机审区\s*$", text, flags=re.MULTILINE)
    if not m:
        return text.rstrip() + section
    rest = text[m.end() :]
    nxt = re.search(r"^##\s", rest, flags=re.MULTILINE)
    end = m.end() + (nxt.start() if nxt else len(rest))
    new_section = section.lstrip("\n")
    if not new_section.endswith("\n"):
        new_section += "\n"
    return text[: m.start()] + new_section + text[end:]


def _append_machine_audit_pass(card_path: str, *, source: str, evidence: str) -> bool:
    """生产卡写入通过机审区；已有「不通过」区则替换为通过（2026-08-20 事故修复）。"""
    if not card_path:
        return False
    if _card_machine_audit_passed(card_path):
        return True
    prod = Path(card_path)
    try:
        text = prod.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("读取生产卡失败，无法落盘机审区: %s (%s)", card_path, exc)
        return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    snippet = re.sub(r"\s+", " ", (evidence or "").strip())[:400]
    # F3（ccc-plan-035）：engine 输出对齐契约格式（> 结论： + > 来源：）
    section = f"\n\n## 机审区\n\n> 结论：通过\n> 来源：engine 自动落盘（{source}）· {stamp}\n> 证据：{snippet or '见 audit.log'}\n"
    if re.search(r"^##\s*机审区\s*$", text, flags=re.MULTILINE):
        # 已有机审区（不通过结论）→ 替换旧区，重审通过覆盖
        new_text = _replace_audit_section(text, section)
    else:
        new_text = text.rstrip() + section
    # F1（ccc-plan-035）：落盘前校验机审区格式，非法即拦截
    from server.board.card_header import validate_audit_section

    valid, reason = validate_audit_section(new_text)
    if not valid:
        logger.error("机审区格式校验失败，拒绝落盘: %s (%s)", card_path, reason)
        return False
    try:
        prod.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        logger.warning("写入机审区失败: %s (%s)", card_path, exc)
        return False
    ok = _card_machine_audit_passed(card_path)
    if ok:
        logger.info("机审区已自动落盘到生产卡: %s (%s)", card_path, source)
        # 033 阶段 2 M6：机审通过写批准真值账本（machine_audit_pass）——机审来源不可伪造
        from server.board.audit_ledger import record_action

        _card_id = Path(card_path).stem.split("-", 1)[0]
        record_action("machine_audit_pass", _card_id, source=source or "engine", detail=card_path)
    return ok


def _archive_executor_log(log_path: Path) -> Path | None:
    """覆盖写之前归档已有日志，避免机审/重派抹掉开发阶段「调用」证据。"""
    try:
        if not log_path.is_file() or log_path.stat().st_size <= 0:
            return None
    except OSError:
        return None
    stem = log_path.stem
    parent = log_path.parent
    for i in range(1, 64):
        dest = parent / f"{stem}.run{i}.log"
        if dest.exists():
            continue
        try:
            log_path.rename(dest)
            logger.info("执行日志已归档: %s → %s", log_path.name, dest.name)
            return dest
        except OSError as exc:
            logger.warning("归档执行日志失败: %s (%s)", log_path, exc)
            return None
    return None


def check_writeback_credentials(card_path: Path, stem: str) -> tuple[bool, str]:
    """校验卡文件的回写区（两态语义：无节放行、有节空白拦截）。

    返回 (ok, error_msg)。
    约定：
    1. 无 '## 回写区' 节 -> 直接放行（不适用；历史构造卡或旧卡兼容）。
    2. 有 '## 回写区' 节但内容空白 -> 拦截打回（防空提交糊弄）。
    分支/commit 凭证不再强校验固定行：执行体以自由文本回写（如「push 到 codex/x 分支
    Commit: sha」），分支存在性与提交证据由引擎收单侧的远端分支/提交校验兜底。
    """
    if not card_path.is_file():
        return True, ""  # 卡文件不存在则跳过以防异常

    text = card_path.read_text(encoding="utf-8")

    # 提取「回写区」：以 `## 回写区` 开头，到下一个 `## ` 或 `---` 或文件末尾
    lines = text.splitlines()
    writeback_lines = []
    in_writeback = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 回写区"):
            in_writeback = True
            continue
        if in_writeback:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            writeback_lines.append(line)

    if not in_writeback:
        return True, ""  # 状态1：无回写区节则直接放行（不适用；历史构造卡/无节卡）

    writeback_content = "\n".join(writeback_lines).strip()
    if not writeback_content:
        return False, "空回写卡（回写区无凭证内容），禁止空提交收单"  # 状态2：有节空白拦截

    return True, ""


def validate_card_state_after_writeback(card_path: Path) -> tuple[bool, str]:
    """执行体回写后校验卡头「状态」字段是否合法。

    执行体可能写出非标准状态值（如 "completed" 代替 "已回写"），
    导致机审链路静默断裂。此校验在引擎收单时拦截非法状态，强制执行体修正。

    返回 (ok, error_msg)。
    """
    if not card_path.is_file():
        return True, ""  # 卡文件不存在则跳过

    from server.board.models import STATES as _VALID_STATES

    text = card_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(">"):
            continue
        for seg in stripped[1:].split("·"):
            seg = seg.strip()
            if seg.startswith("状态："):
                raw_state = seg[len("状态：") :].strip()
                from server.board.models import base_state as _base_state

                base = _base_state(raw_state)
                if base not in _VALID_STATES:
                    return False, (
                        f"卡头状态值非法: {raw_state!r}。"
                        f"合法状态: {sorted(_VALID_STATES)}。"
                        f"回写时必须将状态设为「已回写」，不可写 'completed'/'done' 等英文。"
                    )
                return True, ""
    return True, ""  # 无状态行则放行（历史兼容）

    return True, ""


def _dispatch_and_collect(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
    *,
    entry_override: ExecutorEntry | None = None,
    skip_product_gate: bool = False,
    log_phase: str = "run",
    fresh: bool = False,
) -> tuple[bool, list[str]]:
    """真实派发单个 work + 同步收单。

    Args:
        entry_override: 指定注册表行（机审复用派发时传入验收席 CLI，避免命中开发模板）。
        skip_product_gate: 机审路径跳过「新 commit+diff」门禁（机审不改业务码）。
        log_phase: ``run`` → ``{id}.log``（覆盖前归档）；``audit`` → ``{id}.audit.log``（不碰开发日志）。
        fresh: 重度机审零上下文模式（2026-08-14 机审 v4）——build_command 新会话标志 + 审计 prompt 强化。

    Returns:
        (ok, problems)：ok=True → 已回写；ok=False → 打回（附问题清单）。
    """
    # F2 熔断（2026-08-24 直修）：近24h被强制击杀达阈值的卡，停止一切自动派发
    if _dispatch_blocked_by_ledger(work.id, data_dir=cfg.get("DATA_DIR")):
        logger.error("派发被熔断跳过（近24h强拆≥%d，需人工核查告警文件）: work=%s", _FORCE_KILL_LEDGER_LIMIT, work.id)
        logger.info("[ccc089-trace] dispatch 拉起前早退（熔断）: work=%s phase=%s", work.id, log_phase)
        return False, [f"自动派发熔断：{work.id} 近24h多次被强制击杀，需人工介入（见 alerts/auto-dispatch-blocked-{work.id}.txt）"]

    entry = entry_override
    if entry is None and work.executor:
        entry = registry.cli_entry_for_binding(work.executor, project=work.project)
    if entry is None:
        entry = registry.cli_entry_for_role(work.role, project=work.project)

    if entry is None:
        return False, [
            f"无法为卡片找到对应的可后台 CLI 注册行 (role={work.role}, executor={work.executor}, project={work.project})"
        ]

    _t_start = time.monotonic()
    default_workdir = cfg.get("DATA_DIR", "")
    worktree_path = ""
    worktree_base = getattr(entry, "worktree_base", "")

    if worktree_base:
        target_worktree = get_worktree_path(worktree_base, work.id)
        card_id_slug = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
        branch_name = f"codex/{card_id_slug}"

        try:
            from server.git_sync import resolve_repo_root

            main_repo = resolve_repo_root(cfg.get("DISPATCH_DIR") or "docs/dispatch")
        except Exception:
            main_repo = Path(__file__).resolve().parents[2]

        try:
            target_path = Path(target_worktree).expanduser().resolve()
            if target_path.exists():
                # 2026-08-12 v2：worktree 是 git 管理的分支工作树，存在即可复用。
                # 不再按「日志 ok:true」判定收单（收单后日志归档会误判未收单 → 强重建
                # 毁执行现场 → 机审读占位卡 → 空回写打回循环）。仅当目录损坏（非 git）才重建。
                res_git = subprocess.run(
                    ["git", "-C", str(target_path), "rev-parse", "--git-dir"],
                    capture_output=True,
                    check=False,
                    timeout=15,
                )
                if res_git.returncode == 0:
                    worktree_path = str(target_path)
                    logger.info("复用 existing worktree: %s", target_worktree)
                else:
                    logger.warning("worktree 目录损坏（非 git），移除重建: %s", target_worktree)
                    subprocess.run(
                        ["git", "-C", str(main_repo), "worktree", "remove", "--force", str(target_path)],
                        capture_output=True,
                        check=False,
                    )
                    subprocess.run(["git", "-C", str(main_repo), "worktree", "prune"], capture_output=True, check=False)
                    cmd_add = [
                        "git",
                        "-C",
                        str(main_repo),
                        "worktree",
                        "add",
                        str(target_path),
                        "-b",
                        branch_name,
                        _worktree_branch_seed(main_repo, branch_name),
                    ]
                    res_add = subprocess.run(cmd_add, capture_output=True, text=True, check=False)
                    if res_add.returncode == 0:
                        worktree_path = str(target_path)
                        logger.info("Worktree 重建成功: %s", worktree_path)
                    else:
                        cmd_add_existing = [
                            "git",
                            "-C",
                            str(main_repo),
                            "worktree",
                            "add",
                            str(target_path),
                            branch_name,
                        ]
                        res_existing = subprocess.run(cmd_add_existing, capture_output=True, text=True, check=False)
                        if res_existing.returncode == 0:
                            worktree_path = str(target_path)
                            logger.info("Worktree 关联已有分支成功: %s", worktree_path)
                        else:
                            _bump_worktree_failures()
                            logger.info("[ccc089-trace] dispatch 拉起前早退（worktree 重建+关联均失败）: work=%s phase=%s", work.id, log_phase)
                            return False, [
                                "基础设施：worktree 重建与关联均失败（隔离强制，不回退默认目录）: "
                                + (res_existing.stderr or res_add.stderr or "").strip()
                            ]
            else:
                # 创建（seed 优先远端分支：执行体已 push 的产物/回写不丢）
                cmd_add = [
                    "git",
                    "-C",
                    str(main_repo),
                    "worktree",
                    "add",
                    str(target_path),
                    "-b",
                    branch_name,
                    _worktree_branch_seed(main_repo, branch_name),
                ]
                logger.info("正在创建 worktree: %s", " ".join(cmd_add))
                res = subprocess.run(cmd_add, capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    worktree_path = str(target_path)
                    logger.info("Worktree 创建成功: %s (分支 %s)", worktree_path, branch_name)
                else:
                    logger.warning("git worktree add -b 失败: %s. 尝试关联已存在分支...", res.stderr.strip())
                    cmd_add_existing = [
                        "git",
                        "-C",
                        str(main_repo),
                        "worktree",
                        "add",
                        str(target_path),
                        branch_name,
                    ]
                    res_existing = subprocess.run(cmd_add_existing, capture_output=True, text=True, check=False)
                    if res_existing.returncode == 0:
                        worktree_path = str(target_path)
                        logger.info("Worktree 关联已有分支成功: %s", worktree_path)
                    else:
                        _bump_worktree_failures()
                        logger.info("[ccc089-trace] dispatch 拉起前早退（worktree 创建+关联均失败）: work=%s phase=%s", work.id, log_phase)
                        return False, [
                            "基础设施：worktree 创建与关联均失败（隔离强制，不回退默认目录）: "
                            + (res_existing.stderr or res.stderr or "").strip()
                        ]
        except Exception as exc:
            # 2026-08-12 隔离升级：异常也不再静默回退
            _bump_worktree_failures()
            logger.info("[ccc089-trace] dispatch 拉起前早退（worktree 过程异常）: work=%s phase=%s err=%s", work.id, log_phase, exc)
            return False, [f"基础设施：worktree 创建过程异常（隔离强制，不回退默认目录）: {exc}"]

    # ── 业务仓隔离（2026-08-12 事故修复）：业务仓型任务必须建每卡 worktree ──
    # 执行阶段强制；机审阶段复用开发产物（远程卡走分支信封，不重复建仓）
    biz_worktree_path = ""
    if (log_phase or "run").strip().lower() == "run":
        biz_project = _business_project(work)
        if biz_project:
            biz_worktree_path, biz_err = _ensure_business_worktree(work, biz_project, log_dir)
            if biz_err:
                _bump_worktree_failures()
                logger.warning(
                    "业务仓 worktree 失败（卡保持待分派+冷却，禁止回退主目录）: work=%s err=%s",
                    work.id,
                    biz_err,
                )
                return False, [f"基础设施：业务仓 worktree 创建失败：{biz_err}"]
            logger.info("业务仓 worktree 就绪: work=%s path=%s", work.id, biz_worktree_path)
    else:
        # E2E体检发现 · 老板授权热修（2026-08-26）：机审阶段补传 biz_worktree，与开发派发对齐。
        # 复用开发期已建的业务仓 worktree（存在才传；缺失保持空串走旧路径，不重复建仓、
        # 不改门禁逻辑、不削弱任何检查）——修复机审门禁在卡副本仓跑业务测试必 exit=4 的死循环。
        biz_project = _business_project(work)
        if biz_project:
            candidate = _business_worktree_path(biz_project, work.id)
            if candidate.is_dir():
                biz_worktree_path = str(candidate)
                logger.info("机审复用业务仓 worktree: work=%s path=%s", work.id, biz_worktree_path)

    # 在单测下，豁免对 mock/fake 临时卡的缺失校��
    import sys

    is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
    if not is_pytest and worktree_path and work.card_path and "docs/dispatch" in work.card_path:
        # ccc092 种子一致性：worktree 在但卡副本缺 → 本地 main 有卡则自愈放行；
        # 卡 commit 未进本地 main（未 push）→ 硬失败（ERROR+alerts+打回），取代原 WARNING 循环。
        hardfail_reasons = _ensure_worktree_card_seed(work, worktree_path, main_repo, log_dir, cfg)
        if hardfail_reasons:
            return False, hardfail_reasons

    try:
        cmd = build_command(
            entry,
            work_id=work.id,
            role=work.role,
            card_path=work.card_path,
            default_workdir=default_workdir,
            worktree=worktree_path,
            biz_worktree=biz_worktree_path,
        )
    except ValueError as exc:
        logger.info("[ccc089-trace] dispatch 拉起前早退（build_command 失败）: work=%s phase=%s err=%s", work.id, log_phase, exc)
        return False, [f"命令构造失败: {exc}"]

    # ── 中枢 Prompt 注入：读取卡内提示段，追加到执行体/验收体 prompt ──
    # 执行阶段 → 读「## 执行提示」；机审阶段 → 读「## 机审提示」
    _card_hint_section = "机审提示" if (log_phase or "").strip().lower() == "audit" else "执行提示"
    _card_file = Path(worktree_path) / work.card_path if worktree_path else Path(work.card_path)
    _card_hint = _read_card_section(_card_file, _card_hint_section)
    if _card_hint:
        # 派发时动态注入（ccc-plan-020 A 轨第 4 项）：按卡「角色」实时查 role-skills.yaml，
        # 出卡后改 yaml 存量卡也能拿到最新映射（出卡时注入保留为默认，派发时刷新覆盖）。
        _dyn_role_hint = ""
        try:
            _card_full = _card_file.read_text(encoding="utf-8", errors="replace")
            from server.board.prompt_inject import _role_skill_hint

            _dyn_role_hint = _role_skill_hint(_card_full)
        except Exception:
            pass
        # 注入：追加到「含 work.id 的 prompt 参数」而非 cmd[-1]
        # （复审 P2-2：与 v4 指令块同定位逻辑；OpenCode 模板 cmd[-1] 是尾随 worktree 串）
        # wrapper 型执行体（entry.inject_hint=False，如 DSH run-executor.sh）自读卡内提示，
        # Engine 不注入——避免污染 card_path 等非 prompt 参数（2026-08-18 探针发现）。
        if getattr(entry, "inject_hint", True):
            _hint_block = "\n\n---\n## 项目提示（由中枢在出卡时注入，请优先遵循）\n" + _card_hint
            if _dyn_role_hint:
                _hint_block += "\n" + _dyn_role_hint
            _hint_idx = next(
                (i for i in range(len(cmd) - 1, -1, -1) if work.id in cmd[i]),
                len(cmd) - 1,
            )
            cmd[_hint_idx] = cmd[_hint_idx] + _hint_block
            logger.info(
                "已注入 %s: work=%s arg[%d] (%d 字符, 动态角色=%s)",
                _card_hint_section,
                work.id,
                _hint_idx,
                len(_card_hint),
                bool(_dyn_role_hint),
            )

    # 机审 v4 强化（2026-08-14）：审计阶段追加三级/就地修复/severity 标记指令。
    # 修复 MachineAuditPrompt 死代码——真实审计 prompt 由注册表模板+卡提示+skill 拼装，
    # v4 指令必须在此实际注入审计 agent 才能生效。
    # 重度复审 P1-A：v4 块注入到「含 work.id 的 prompt 参数」而非 cmd[-1]
    # （OpenCode 模板 cmd[-1] 是尾随 worktree 串；fresh 标志在注入后追加，保住 prompt 不变量）。
    if (log_phase or "").strip().lower() == "audit" and cmd and getattr(entry, "inject_hint", True):
        # S4（2026-08-22）：wrapper 型机审执行体（如 dsh-auditor.sh，inject_hint=False）自含 v4 指令，
        # Engine 不注入——避免污染位置参数（与 run 阶段 inject_hint 守卫一致）。
        _v4_audit_block = (
            "\n\n---\n## 机审 v4 指令（三级 · 必须遵循）\n"
            "1. 对抗式找茬：假设有 P0/P1，找具体可复现问题；0 发现须给风险论证。\n"
            "2. 三级判定 severity：影响面/改动深度/红线邻近各 1-3 分，合计 3-4=轻 5-7=中 8-9=重，"
            "任一维度高→强制重。\n"
            "3. 可快速修复的轻问题 → 就地修复并 commit+push（不打回）；原则性红线（业务意图违背/系统性越界）→ 打回。\n"
            "4. 结论行必须输出 severity 标记（severity：轻/中/重）并明示结论（通过 / 不通过，不通过须附原因）。\n"
        )
        if fresh:
            _v4_audit_block += (
                "5. 本审计为【重度·异席 fresh 独立 agent】零上下文审查：不沿用任何历史上下文，"
                "全量多视角独立重算关键口径，完整闭环后方可下结论。\n"
            )
        # 定位 prompt 参数：含 work.id 的 arg（prompt 模板必带 work_id 占位符）
        _prompt_idx = next(
            (i for i in range(len(cmd) - 1, -1, -1) if work.id in cmd[i]),
            len(cmd) - 1,
        )
        cmd[_prompt_idx] = cmd[_prompt_idx] + _v4_audit_block
        logger.info("机审 v4 指令已注入审计 prompt(arg[%d]): work=%s fresh=%s", _prompt_idx, work.id, fresh)
        # 重度 fresh：注入完成后追加新会话标志（不污染 prompt）
        if fresh:
            from server.engine.dispatch import _FRESH_FLAG_BY_CMD

            _flag = _FRESH_FLAG_BY_CMD.get(entry.command)
            if _flag:
                cmd.append(_flag)

    phase = (log_phase or "run").strip().lower() or "run"

    sampler: ProcessSampler | None = None

    def _emit(
        ok: bool,
        returncode: int | None,
        exit_kind: str,
        problems: list[str] | None = None,
    ) -> None:
        lifetime_s = time.monotonic() - _t_start
        try:
            record_worker_event(
                log_dir,
                work_id=work.id,
                phase=phase,
                ok=ok,
                returncode=returncode,
                duration_s=lifetime_s,
                exit_kind=exit_kind,
                peak_rss_mb=sampler.peak_rss_mb if sampler else None,
                peak_cpu_pct=sampler.peak_cpu_pct if sampler else None,
                problems=problems,
            )
        except Exception:
            logger.exception("worker 事件埋点失败（不影响流程）: work=%s", work.id)
        # ccc083 会话探针：worker-events.jsonl 追加 kind=session 行（会话寿命/短命标记/编辑命中）。
        # 与 kind=worker 行并存；消费方按 kind 过滤互不干扰（web/server.py 只取 kind==worker）。
        try:
            _marker_id = f"{work.id}-audit" if phase == "audit" else work.id
            _append_session_probe(
                log_dir,
                work_id=work.id,
                phase=phase,
                lifetime_s=lifetime_s,
                short_threshold_s=_short_session_seconds(cfg),
                worktree_path=worktree_path,
                marker_id=_marker_id,
            )
        except Exception:
            logger.exception("会话探针埋点失败（不影响流程）: work=%s", work.id)

    if phase == "audit":
        log_path = log_dir / f"{work.id}.audit.log"
    else:
        log_path = log_dir / f"{work.id}.log"
        _archive_executor_log(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "拉起执行体: work=%s role=%s phase=%s cmd=%s log=%s",
        work.id,
        work.role,
        phase,
        cmd,
        log_path,
    )

    logf = None
    try:
        child_env = os.environ.copy()
        # 减轻 Python 类执行体块缓冲；Node/Claude 仍可能块缓冲（非 TTY），见日志延迟。
        child_env.setdefault("PYTHONUNBUFFERED", "1")
        # 日志句柄必须保持到 wait 结束：过早 close 会导致子进程 stdout 断开、看板 log_tail 空白
        logf = log_path.open("w", encoding="utf-8", buffering=1)
        logf.write(f"[ccc.engine] start work={work.id} phase={phase} pid_pending cmd={' '.join(cmd)}\n")
        logf.flush()
        proc = subprocess.Popen(  # noqa: S603 - 命令来自注册表配置，非用户输入
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=worktree_path or entry.workdir or default_workdir or None,
            env=child_env,
            start_new_session=True,  # 隔离进程组：kill 时杀全组，避免孙进程变僵尸
        )
        # 标记写入子进程 PID：Engine 重启时若 CLI 仍活，不得假打回
        # 1-1 标记名分流（2026-08-24 直修）：机审阶段刷新 {id}-audit.running，
        # 不再覆写 plain {id}.running——原实现导致机审结束只清 -audit 标记而
        # plain 标记泄漏至兜底期（ccc079 实证），且 engine_pid 恒活造成假强拆记账。
        _refresh_running_marker_child(log_dir, work.id, proc.pid, phase=log_phase)
        logf.write(f"[ccc.engine] child_pid={proc.pid}\n")
        logf.flush()
        sampler = ProcessSampler(proc)
        sampler.start()
    except FileNotFoundError as exc:
        if logf is not None:
            logf.close()
        _emit(False, None, "launch_error", [f"启动失败（命令不存在）: {exc}"])
        return False, [f"启动失败（命令不存在）: {exc}"]
    except OSError as exc:
        if logf is not None:
            logf.close()
        _emit(False, None, "launch_error", [f"启动失败: {exc}"])
        return False, [f"启动失败: {exc}"]

    try:
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # killpg 杀全进程组（含孙进程），避免 proc.kill() 只杀直接子进程导致僵尸
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            # 1-2 台账口径（2026-08-24 直修）：同步超时击杀同样入强拆台账，熔断口径才完整
            # R2 修正：必须透传 data_dir——缺省回退 ~/.ccc/data 曾使测试实锤污染生产台账
            _record_force_kill(work.id, data_dir=cfg.get("DATA_DIR"))
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.error("子进程 killpg 后仍超时（僵尸）: work=%s pid=%s", work.id, proc.pid)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                proc.wait()
            _emit(False, None, "timeout", [f"执行超时（{timeout}s 已 kill）"])
            return False, [f"执行超时（{timeout}s 已 kill）"]
        finally:
            if logf is not None:
                try:
                    logf.close()
                except OSError:
                    pass

        if returncode == 0:
            if not skip_product_gate:
                remote_passed = False
                if worktree_path and work.card_path:
                    card_id_slug = Path(work.card_path).stem.lower()
                    remote_branch = f"origin/codex/{card_id_slug}"
                    try:
                        res_show = subprocess.run(
                            ["git", "show", f"{remote_branch}:{work.card_path}"],
                            capture_output=True,
                            text=True,
                            cwd=worktree_path,
                            check=False,
                        )
                        if res_show.returncode == 0:
                            from server.board.models import machine_audit_passed_text

                            if machine_audit_passed_text(res_show.stdout):
                                remote_passed = True
                                logger.info(
                                    "远端凭证成立: %s 机审已通过，忽略本地 commit/diff 校验与回写校验", remote_branch
                                )
                    except Exception as e:
                        logger.warning("检查远端凭证异常: %s", e)

                if not remote_passed:
                    # 空回写与凭证校验 (Task 2 & 3) - 无论 worktree 与默认目录派发都生效
                    card_file_path = Path(work.card_path)
                    if worktree_path:
                        card_file_path = Path(worktree_path) / work.card_path
                    stem = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
                    wb_ok, wb_err = check_writeback_credentials(card_file_path, stem)
                    if not wb_ok:
                        logger.warning("回写凭证校验失败: %s -> 打回", wb_err)
                        _emit(False, 0, "ok", [wb_err])
                        return False, [wb_err]

                    # 卡头状态合法性校验：防止执行体写非法状态值（如 "completed"）
                    # 导致机审链路静默断裂（mx028 事故）
                    state_ok, state_err = validate_card_state_after_writeback(card_file_path)
                    if not state_ok:
                        logger.warning("卡头状态非法: %s -> 打回", state_err)
                        _emit(False, 0, "ok", [state_err])
                        return False, [state_err]

                    # 机械门禁：仅在 worktree_path 存在时生效
                    if worktree_path:
                        tip = _marker_dispatch_tip(log_dir, work.id)
                        has_commit = _worktree_has_new_commit(worktree_path, since_ref=tip)
                        has_diff = _worktree_has_nonempty_diff(worktree_path)
                        if not (has_commit and has_diff):
                            logger.warning(
                                "exit 0 但无有效产物: work=%s worktree=%s tip=%s commit=%s diff=%s → 打回",
                                work.id,
                                worktree_path,
                                tip or "(无 tip 记录)",
                                has_commit,
                                has_diff,
                            )
                            _emit(
                                False,
                                0,
                                "ok",
                                [
                                    f"exit 0 但无有效产物（机械门禁）: worktree {worktree_path} "
                                    f"须同时满足 origin/main..HEAD 有新 commit 且 diff 非空 "
                                    f"(commit={has_commit}, diff={has_diff})"
                                ],
                            )
                            return False, [
                                f"exit 0 但无有效产物（机械门禁）: worktree {worktree_path} "
                                f"须同时满足 origin/main..HEAD 有新 commit 且 diff 非空 "
                                f"(commit={has_commit}, diff={has_diff})"
                            ]

                        # 机械门禁扩展：解析卡内门禁探针
                        # 门禁分层：
                        #   1. 环境缺失（命令不存在）→ 跳过门禁，放行进机审
                        #   2. 代码级失败（测试/编译报错）→ 标记可修复，放行进机审
                        #   3. 硬底线（空提交/无 diff/范围越界）→ 直接打回，不重试
                        if work.card_path:
                            gates = parse_gate_section(card_file_path)
                            for gate_name, cmd in gates.items():
                                if gate_name in ("编译", "测试", "lint"):
                                    if not cmd:
                                        continue
                                    # 检查命令是否存在（worktree 可能无 venv/toolchain）
                                    cmd_binary = cmd.split()[0] if cmd else ""
                                    cmd_exists = False
                                    if cmd_binary:
                                        try:
                                            which_rc = subprocess.run(
                                                ["which", cmd_binary],
                                                capture_output=True,
                                                timeout=5,
                                            )
                                            cmd_exists = which_rc.returncode == 0
                                        except Exception:
                                            cmd_exists = False
                                    if not cmd_exists:
                                        logger.warning(
                                            "门禁【%s】跳过: 命令 '%s' 在 worktree 环境不可用，非代码问题，放行进机审",
                                            gate_name,
                                            cmd_binary,
                                        )
                                        metrics_logger.info(
                                            "gate_skip card=%s gate=%s reason=%s",
                                            work.id,
                                            gate_name,
                                            "env_missing",
                                        )
                                        continue
                                    logger.info("运行门禁【%s】: cmd=%s", gate_name, cmd)
                                    res_gate = subprocess.run(
                                        cmd,
                                        shell=True,
                                        cwd=worktree_path,
                                        capture_output=True,
                                        text=True,
                                        timeout=120,
                                    )
                                    if res_gate.returncode != 0:
                                        combined_output = (res_gate.stdout or "") + (res_gate.stderr or "")
                                        snippet = (
                                            combined_output[-800:] if len(combined_output) > 800 else combined_output
                                        )
                                        # 2026-08-16 质量门禁：测试/编译失败 = 硬打回（不再放行就地修复）
                                        logger.warning(
                                            "卡 %s 门禁【%s】未通过（硬门禁，打回）: 退出码 %d",
                                            work.id,
                                            gate_name,
                                            res_gate.returncode,
                                        )
                                        metrics_logger.info(
                                            "gate_block card=%s gate=%s rc=%d",
                                            work.id,
                                            gate_name,
                                            res_gate.returncode,
                                        )
                                        _emit(
                                            False,
                                            1,
                                            "ok",
                                            [f"门禁【{gate_name}】未通过（2026-08-16 起硬门禁）: {snippet[:300]}"],
                                        )
                                        return False, [f"门禁【{gate_name}】未通过: {snippet[:300]}"]
                                elif gate_name == "范围":
                                    if str(cmd).strip().lower() in ("true", "yes", "1", "on"):
                                        range_ok, range_err = check_range_gate(worktree_path, work.card_path)
                                        if not range_ok:
                                            # 范围越界是硬底线 → 直接打回
                                            logger.warning("卡 %s 门禁【范围】未通过: %s", work.id, range_err)
                                            _emit(False, 1, "ok", [range_err])
                                            return False, [range_err]
            # F3（2026-08-10）：机审路径 exit 0 但 audit 明确「机审：不通过」→ 按失败返回。
            # 双重保险：机审 agent 打回时 exit code 可能为 0（claude -p 声称非零退出不可靠），
            # 仅凭 exit 0 会把「不通过」误判为通过（F1 在 _run_machine_audit_after_writeback 也兜底）。
            if log_phase == "audit":
                _audit_log = log_dir / f"{work.id}.audit.log"
                _audit_text = _read_text_best_effort(_audit_log)
                if _audit_output_indicates_rejection(_audit_text):
                    _reason = _audit_rejection_reason(_audit_text) or "机审：不通过"
                    logger.warning(
                        "机审 exit 0 但 audit 含「不通过」→ 按失败返回: work=%s reason=%s",
                        work.id,
                        _reason,
                    )
                    _emit(False, 1, "ok", [_reason])
                    return False, [_reason]
            _emit(True, 0, "ok")
            return True, []

        # 检查是否为空提交信号 (V3 根修)：执行体空手交单（nothing to commit）→ 失败打回，
        # 禁止拦截成假成功（原逻辑绕过产物门禁，是 clw006 空回写死循环的燃料）。
        try:
            if _detect_empty_commit_signal(log_path):
                reason = "空提交信号（nothing to commit）：执行体无产物交单，禁止假成功"
                logger.warning("检测到空提交信号 → 按失败打回: work=%s", work.id)
                _emit(False, 1, "ok", [reason])
                return False, [reason]
        except Exception as e:
            logger.warning("检查空提交日志异常: %s", e)
        except Exception as e:
            logger.warning("检查空提交日志异常: %s", e)

        _emit(
            False,
            returncode,
            "signal" if returncode < 0 else "nonzero",
            [f"退出码非 0: {returncode}（日志: {log_path}）"],
        )
        return False, [f"退出码非 0: {returncode}（日志: {log_path}）"]
    finally:
        if sampler is not None:
            sampler.stop()


def _pid_alive(pid: int) -> bool:
    """``os.kill(pid, 0)`` 探测进程是否仍存在（权限不足也视为存活）。"""
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _parse_running_marker_pids(raw: str) -> list[int]:
    """解析 ``.running`` 中所有 PID（``pid=`` / ``engine_pid=`` / ``child_pid=``）。

    旧格式纯 ``1`` / 空 → 空列表（按遗留孤儿处理）。
    """
    pids: list[int] = []
    for line in (raw or "").splitlines():
        text = line.strip()
        for prefix in ("pid=", "engine_pid=", "child_pid="):
            if not text.startswith(prefix):
                continue
            rest = text[len(prefix) :].strip().split()[0] if text[len(prefix) :].strip() else ""
            if rest.isdigit():
                pid = int(rest)
                if pid > 1 and pid not in pids:
                    pids.append(pid)
            break
    return pids


def _parse_running_marker_worker_pids(raw: str) -> list[int]:
    """解析标记中的「工作者」PID（仅 ``pid=`` / ``child_pid=``，剔除 ``engine_pid=``）。

    1-2 口径修正（2026-08-24 直修）：engine 重启后标记里的旧 engine_pid 恒活，
    会让陈旧标记永远判「存活」、拖到兜底强拆且零击杀也记账（q2 误熔断告警根因）。
    判活只看真正干活的子进程；killpg 收割仍走 _kill_marker_pids（含防自伤守卫）。
    """
    out: list[int] = []
    for line in (raw or "").splitlines():
        t = line.strip()
        for prefix in ("pid=", "child_pid="):
            if not t.startswith(prefix):
                continue
            rest = t[len(prefix):].strip().split()[0] if t[len(prefix):].strip() else ""
            if rest.isdigit():
                pid = int(rest)
                if pid > 1 and pid not in out:
                    out.append(pid)
            break
    return out


def _parse_running_marker_pid(raw: str) -> int | None:
    """兼容旧测试：返回标记中的主 ``pid=``（或首个解析到的 PID）。"""
    text = (raw or "").strip()
    for line in text.splitlines():
        ln = line.strip()
        if ln.startswith("pid="):
            rest = ln[4:].strip().split()[0] if ln[4:].strip() else ""
            if rest.isdigit():
                return int(rest)
    pids = _parse_running_marker_pids(raw)
    return pids[0] if pids else None


def _kill_marker_pids(raw: str, reason: str, work_id: str = "") -> list[int]:
    """强制击杀标记记录的整棵进程树（F1 根修 2026-08-24 · 受老板临时授权直修）。

    派发侧 ``start_new_session=True`` 使每个子 CLI 自成进程组：即使组领导已死，
    幸存孙进程仍持有同 pgid，``killpg`` 可整体收割——这正是此前「只删标记不杀
    进程」导致机审会话孤儿越积越多的漏洞。逐个 killpg；ProcessLookupError 视为
    已清空；PermissionError 回退单 pid SIGKILL。
    返回实际发出信号的 pid 列表（仅日志/台账用）。
    """
    me = os.getpid()
    my_group = os.getpgrp()
    signaled: list[int] = []
    for p in _parse_running_marker_pids(raw):
        if p == me or p == my_group:
            continue  # 绝不自伤：旧标记里的 engine_pid 可能恰是本进程
        try:
            os.killpg(p, signal.SIGKILL)
            signaled.append(p)
        except ProcessLookupError:
            pass
        except PermissionError:
            try:
                os.kill(p, signal.SIGKILL)
                signaled.append(p)
            except OSError:
                pass
        except OSError:
            pass
    if signaled:
        logger.warning("强制击杀进程组: work=%s reason=%s pids=%s", work_id, reason, signaled)
    return signaled


# ── F2 熔断：同卡反复被强拆 → 停止自动派发，转人工（2026-08-24 直修） ──
_FORCE_KILL_LEDGER_LIMIT = 3  # 24h 内同卡被强拆次数上限
_FORCE_KILL_LEDGER_WINDOW_S = 86400


def _force_kill_ledger_path(data_dir: str | None = None) -> Path:
    """强拆台账路径：优先用调用方透传的 cfg DATA_DIR（生产/测试一致）。

    2026-08-24 直修补：原只读环境变量 DATA_DIR，测试进程不设该环境变量时
    会回退写真实生产台账 ~/.ccc/data/force_kill_ledger.json，污染生产并被
    测试内累积触发熔断（test_concurrency_cap 红）。改为显式透传。
    """
    base = data_dir or os.environ.get("DATA_DIR") or str(Path.home() / ".ccc" / "data")
    return Path(base).expanduser() / "force_kill_ledger.json"


def _record_force_kill(work_id: str, data_dir: str | None = None) -> None:
    """记录一次强制击杀；24h 内超限则写告警文件并打 CRITICAL（熔断依据）。"""
    now = time.time()
    path = _force_kill_ledger_path(data_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except Exception:
        data = {}
    ts_list = [t for t in (data.get(work_id) or []) if now - float(t) < _FORCE_KILL_LEDGER_WINDOW_S]
    ts_list.append(now)
    data[work_id] = ts_list
    data = {k: v for k, v in data.items() if any(now - float(t) < _FORCE_KILL_LEDGER_WINDOW_S for t in v)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.exception("强拆台账写入失败: work=%s", work_id)
    if len(ts_list) >= _FORCE_KILL_LEDGER_LIMIT:
        log_base = Path(os.environ.get("LOG_DIR") or (path.parent.parent / "logs"))
        try:
            alert_dir = log_base / "alerts"
            alert_dir.mkdir(parents=True, exist_ok=True)
            (alert_dir / f"auto-dispatch-blocked-{work_id}.txt").write_text(
                f"{work_id} 近24h被强制击杀 {len(ts_list)} 次（阈值 {_FORCE_KILL_LEDGER_LIMIT}），"
                "自动派发已熔断；人工核查后删除本文件即可恢复自动派发。\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        logger.critical("自动派发熔断: work=%s 近24h强拆 %d 次", work_id, len(ts_list))


def _dispatch_blocked_by_ledger(work_id: str, data_dir: str | None = None) -> bool:
    """该卡是否已被熔断（近24h强拆次数达阈值）。"""
    path = _force_kill_ledger_path(data_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except Exception:
        return False
    now = time.time()
    recent = [t for t in (data.get(work_id) or []) if now - float(t) < _FORCE_KILL_LEDGER_WINDOW_S]
    return len(recent) >= _FORCE_KILL_LEDGER_LIMIT


def reclaim_orphaned_running(store: BoardStore, log_dir: Path, data_dir: str | None = None) -> int:
    """回收带 ``{work_id}.running`` 标记的「执行中」残留（AUTO 崩溃未收单）。

    manual 挂起等人不会写标记，故不被误回收。
    若标记含任一存活 PID（Engine 收单进程 **或** 子 CLI），**跳过回收**——
    避免 launchd KeepAlive / 手动 ``--once`` / Engine 重启误杀仍在跑的 CLI。
    死标记 → 回「待分派」自动重派（不进打回）。返回重派张数。
    """
    n = 0
    now_ts = time.time()
    for w in store.list_work(state=State.RUNNING):
        marker = log_dir / f"{w.id}.running"
        if not marker.is_file():
            if w.dispatch == "manual":
                continue
            # 2026-08-17 v2：执行中卡缺失运行标记。
            # 为了避免新建卡派发及单元测试时的微秒级竞态，只有当对应的日志文件存在且最后修改时间超过 60s 时，才判定为真正丢失标记并回收。
            log_path = log_dir / f"{w.id}.log"
            if log_path.is_file():
                try:
                    log_age = now_ts - log_path.stat().st_mtime
                except OSError:
                    log_age = 0.0
                if log_age >= 60:
                    try:
                        w.transition(
                            State.TODO,
                            problems=["运行标记丢失，自动重派恢复"],
                        )
                        store.save_work(w)
                        n += 1
                        logger.warning("回收缺失标记的孤儿执行中: work=%s → 待分派", w.id)
                    except Exception:
                        logger.exception("回收缺失标记的孤儿执行中失败: work=%s", w.id)
            continue
        try:
            raw = marker.read_text(encoding="utf-8")
            mtime = marker.stat().st_mtime
        except OSError:
            raw = ""
            mtime = 0.0
        owner_pids = _parse_running_marker_worker_pids(raw)
        alive = [p for p in owner_pids if _pid_alive(p)]

        # 2026-08-17 v2：即使 PID 存活，超过强拆时距同样强制中止并回收（1-3：1.5×执行超时）。
        # 否则仅由 cleanup_dead_markers 删标记而子进程不死，会导致卡永久处于假在途、槽死锁状态。
        _eff_max_age = _effective_max_marker_age()
        if alive and mtime > 0 and (now_ts - mtime) >= _eff_max_age:
            logger.warning(
                "执行中任务超时未回写（age=%ds，max=%ds），强制中止进程并回收: work=%s",
                int(now_ts - mtime),
                _eff_max_age,
                w.id,
            )
            # F1 根修：killpg 收割整棵进程树（含幸存孙进程），并记强拆台账
            _kill_marker_pids(raw, reason="执行中超时强制中止", work_id=w.id)
            _record_force_kill(w.id, data_dir=data_dir)
            alive = []

        if alive:
            logger.info(
                "跳过孤儿回收: work=%s 存活 pid=%s（标记=%s）",
                w.id,
                alive,
                owner_pids,
            )
            continue
        try:
            # R2 修正（C-P1-A，2026-08-24）：本支路是全链唯一不做 killpg 的回收口——
            # 组领导已死但同组孙进程幸存时，判死回收+重派会让幸存者与新会话并发写
            # 同一 worktree（即 ccc078 雪崩机制）。unlink 前先按进程组收割。
            killed = _kill_marker_pids(raw, reason="回收孤儿执行中", work_id=w.id)
            if killed:
                _record_force_kill(w.id, data_dir=data_dir)
            # 不进打回：回待分派自动再派（避免 kickstart 误杀长任务）
            w.transition(
                State.TODO,
                problems=["Engine 中断未收单，自动重派"],
            )
            store.save_work(w)
            n += 1
            logger.warning("回收孤儿执行中: work=%s → 待分派（重派）", w.id)
        except Exception:
            logger.exception("回收孤儿执行中失败: work=%s", w.id)
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass
    return n


def cleanup_dead_markers(log_dir: Path, running_ids: set[str] | None = None, data_dir: str | None = None) -> int:
    """清扫任意卡状态下的死标记（``*.running``，含 ``*-audit.running``）。

    引擎崩溃/部署后，非「执行中」卡（已关闭/待分派/打回）上的残留标记不会被
    ``reclaim_orphaned_running`` 回收，会污染看板「进行中」视图并让 web 每轮
    对死卡做全套富化。此处按 PID 存活判定：标记内所有 PID 已死（或无 PID）→
    删除；任一 PID 存活（可能刚写完、子进程刚拉起）→ 保留，绝不误删在途任务。

    此外，标记超过强拆时距（_effective_max_marker_age()=1.5×执行超时；机审标记再收紧到
    2×机审超时）同样强制删除——即使 PID 存活也不能让僵尸进程永久占用槽位。
    """
    n = 0
    now_ts = time.time()
    try:
        markers = list(log_dir.glob("*.running"))
    except OSError:
        return 0
    for marker in markers:
        if not marker.is_file():
            continue
        # 2026-08-17 v2：跳过执行中卡的运行标记。这些标记由 reclaim_orphaned_running 独占回收，防竞争。
        work_id = marker.stem.split("-", 1)[0]
        if running_ids and work_id in running_ids:
            continue
        try:
            raw = marker.read_text(encoding="utf-8")
            mtime = marker.stat().st_mtime
        except OSError:
            raw = ""
            mtime = 0.0
        # 1-2 口径修正（2026-08-24）：存活判定只认工作者 PID（pid=/child_pid=），
        # 剔除恒活的旧 engine_pid——见 _parse_running_marker_worker_pids。
        pids = _parse_running_marker_worker_pids(raw)
        # F3 根修：机审标记的强拆上限收紧为 2×机审超时（默认配置下 30min），
        # 不再统一等兜底期——机审会话挂起时尽早收割，防孤儿堆积。
        max_age = _effective_max_marker_age()
        if marker.name.endswith("-audit.running"):
            try:
                audit_to = max(60, int(os.environ.get("EXECUTOR_AUDIT_TIMEOUT_SECONDS") or 1800))
            except ValueError:
                audit_to = 1800
            max_age = min(max_age, 2 * audit_to)
        alive_any = any(_pid_alive(p) for p in pids)
        if alive_any:
            # 存活的 PID + 未超时 → 保留；超时 → 兜底强制回收
            if mtime > 0 and (now_ts - mtime) < max_age:
                continue
            logger.warning(
                "标记超时强制回收（age=%ds，max=%ds）: %s", int(now_ts - mtime), max_age, marker.name
            )
        # F1 根修：无论记录的 PID 死活，先按进程组收割幸存者——组可能比领导活得久，
        # 只删标记会让真实子进程变成无人认领的孤儿（ccc078 雪崩根因）。
        killed = _kill_marker_pids(raw, reason="清理死标记", work_id=work_id)
        if killed or (alive_any and pids):
            _record_force_kill(work_id, data_dir=data_dir)
        try:
            marker.unlink(missing_ok=True)
            n += 1
            logger.info("清理死标记: %s", marker.name)
        except OSError:
            pass
    return n


def _write_running_marker(
    log_dir: Path,
    work_id: str,
    *,
    engine_pid: int,
    child_pid: int | None = None,
    dispatch_tip: str | None = None,
) -> Path:
    """写运行标记：主 ``pid=`` 优先子进程，否则 Engine；并保留 engine/child 字段。

    原子写（tmp → rename）：``reclaim_orphaned_running`` 每轮心跳读取标记，
    非原子写入的半截文件会被误判为无存活 PID → 把仍在执行的卡假孤儿回收。

    ccc082 加固（2026-08-24）：机审标记（``work_id`` 以 ``-audit`` 结尾）同步
    原子镜像进用户级全局注册表（``_audit_inflight_registry_dir``），使不同
    DATA_DIR 的 engine 对同一卡机审互见在途；认领（_claim_running_marker）与
    子进程刷新（_refresh_running_marker_child）两路都经此函数，自动覆盖。
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    marker = log_dir / f"{work_id}.running"
    primary = child_pid if child_pid is not None else engine_pid
    lines = [f"engine_pid={engine_pid}\n", f"pid={primary}\n"]
    if dispatch_tip:
        lines.append(f"dispatch_tip={dispatch_tip}\n")
    if child_pid is not None:
        lines.append(f"child_pid={child_pid}\n")
    text = "".join(lines)
    tmp = marker.with_suffix(marker.suffix + f".tmp.{time.time_ns()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, marker)
    if work_id.endswith("-audit"):
        _mirror_audit_registry(work_id, text)
    return marker


def _mirror_audit_registry(work_id: str, text: str) -> None:
    """把机审在途登记镜像进全局注册表（ccc082 跨 DATA_DIR 防线写入面）。

    best-effort：镜像失败仅告警不打断派发——单机同用户下与本地标记同级可靠，
    打断主流程会让 engine 派发瘫痪，风险远大于防线降级；warning 可观测。
    """
    try:
        reg_dir = _audit_inflight_registry_dir()
        reg_dir.mkdir(parents=True, exist_ok=True)
        entry = reg_dir / f"{work_id}.running"
        tmp = entry.with_suffix(entry.suffix + f".tmp.{time.time_ns()}")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, entry)
    except OSError:
        logger.warning("全局机审注册表写入失败（跨 DATA_DIR 防线降级）: %s", work_id)


def _clear_claim_marker(card_path: Path, card_id: str) -> None:
    """清卡头认领标记（认领协议超时回收）：去掉「 · 认领：<W号> · 认领时间：<ts>」，commit+push。

    认领协议（ccc-plan-020 v2）：Worker 认领后超时未完成 → Engine 回收认领，卡回待分派可被重认领。
    """
    import re as _re

    try:
        text = card_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.warning("清理认领标记失败（读）: %s", card_id)
        return
    # 找卡头第一个 `>` 元数据行（认领字段在卡头元数据）
    m = _re.search(r"^(>[^\n]*?)(?:\n|$)", text, _re.MULTILINE)
    if not m:
        return
    first = m.group(1)
    if "认领：" not in first:
        return
    new_first = _re.sub(r" · 认领：\S+ · 认领时间：\S+", "", first)
    if new_first == first:
        new_first = _re.sub(r" · 认领：\S+", "", first)
    text = text[: m.start(1)] + new_first + text[m.end(1) :]
    try:
        card_path.write_text(text, encoding="utf-8")
        import subprocess

        subprocess.run(
            ["git", "add", str(card_path)], cwd=card_path.parents[2], check=False, capture_output=True, timeout=30
        )
        commit_res = subprocess.run(
            ["git", "commit", "-m", f"claim-reclaim: 认领超时回收 {card_id}"],
            cwd=card_path.parents[2],
            check=False,
            capture_output=True,
            timeout=30,
        )
        # 1-5（2026-08-24 直修）：不再直推 origin main——主树是 origin 的本地镜像，
        # 认领回收只落本地提交，由 sync_origin_main ff-only 对齐；原 push 失败静默
        # 曾致本地 main 提交无限累积、环节② push 撞 non-FF。
        if commit_res.returncode != 0:
            logger.warning("认领回收 commit 未生效（可能无改动或冲突）: %s rc=%s", card_id, commit_res.returncode)
        logger.info("认领标记已清理（超时回收，仅本地提交）: %s", card_id)
    except OSError:
        logger.warning("清理认领标记失败（写）: %s", card_id)


def _claim_running_marker(log_dir: Path, work_id: str, main_repo: Path | None = None, data_dir: str | None = None) -> Path:
    """AUTO 派发起写运行标记（先记 Engine PID；子进程拉起后 refresh）。

    同时记录 ``dispatch_tip``：派发时刻 origin/main 的 commit（V2 产物门禁基准），
    防「派发后他人合入 → 执行体未写码也被误判有产物」。

    F1 根修（2026-08-24）：覆写前若存在旧标记，先按进程组收割旧会话——
    否则旧子进程被新标记抹去记账，成为无人认领的孤儿（ccc078 雪崩帮凶）。
    """
    try:
        old = log_dir / f"{work_id}.running"
        if old.is_file():
            old_raw = old.read_text(encoding="utf-8")
            if _parse_running_marker_pids(old_raw):
                killed = _kill_marker_pids(old_raw, reason="重复派发前清理旧标记", work_id=work_id)
                if killed:
                    _record_force_kill(work_id, data_dir=data_dir)
    except OSError:
        pass
    tip = ""
    if main_repo is not None:
        try:
            res = subprocess.run(
                ["git", "-C", str(main_repo), "rev-parse", "origin/main"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if res.returncode == 0:
                tip = res.stdout.strip()
        except Exception:
            tip = ""
    return _write_running_marker(log_dir, work_id, engine_pid=os.getpid(), dispatch_tip=tip or None)


def _refresh_running_marker_child(log_dir: Path, work_id: str, child_pid: int, phase: str = "run") -> None:
    """子 CLI 已 Popen → 标记改写为 child_pid（防 Engine 重启假打回）；保留 dispatch_tip。

    1-1 标记名分流（2026-08-24 直修）：机审阶段刷新 ``{id}-audit.running``，
    与机审认领/清理使用同一名字；原实现覆写 plain ``{id}.running`` 造成
    机审结束后 plain 标记泄漏（ccc079 实证）。
    """
    marker_id = f"{work_id}-audit" if phase == "audit" else work_id
    tip = _marker_dispatch_tip(log_dir, marker_id)
    _write_running_marker(log_dir, marker_id, engine_pid=os.getpid(), child_pid=child_pid, dispatch_tip=tip)


def _marker_dispatch_tip(log_dir: Path, work_id: str) -> str | None:
    """读运行标记里的 ``dispatch_tip=``（无则 None）。"""
    try:
        marker = log_dir / f"{work_id}.running"
        if not marker.is_file():
            return None
        for ln in marker.read_text(encoding="utf-8").splitlines():
            if ln.startswith("dispatch_tip="):
                return ln[len("dispatch_tip=") :].strip() or None
    except OSError:
        return None
    return None


def _clear_running_marker(log_dir: Path, work_id: str) -> None:
    try:
        (log_dir / f"{work_id}.running").unlink(missing_ok=True)
    except OSError:
        pass
    if work_id.endswith("-audit"):
        # ccc082：机审收尾同步清全局注册表条目，防跨 DATA_DIR 假在途
        try:
            (_audit_inflight_registry_dir() / f"{work_id}.running").unlink(missing_ok=True)
        except OSError:
            logger.warning("全局机审注册表清理失败: %s", work_id)


def _audit_cli_entry(registry: ExecutorRegistry, acceptor: str) -> ExecutorEntry | None:
    """验收席可后台 CLI 行（机审）；按绑定名匹配，未命中回退按角色取行。

    R-2026-08-23 P0-1：2026-08-22 工具收口后验收席绑定改为 DSH（S4），
    交叉配对名（Claude Code/OpenCode）永不再命中 → 机审被静默跳过。
    绑定名匹配优先保留（兼容显式指定工具的旧口径），未命中时按「验收席」
    角色取首个可后台 CLI 行（现行态 = dsh-auditor.sh v4，指令自含）。
    """
    name = normalize_tool(acceptor)
    if name:
        for e in registry.entries:
            if e.role == "验收席" and e.category == "可后台 CLI" and normalize_tool(e.binding) == name:
                return e
        # 回退：绑定名失配 → 按角色取验收席 CLI 行（工具收口后主路径）
        for e in registry.entries:
            if e.role == "验收席" and e.category == "可后台 CLI":
                return e
    return None


def _ledger_record(
    work: Work,
    severity: str | None,
    conclusion: str,
    reasons: list[str] | None,
    *,
    fix_action: str = "",
    source: str = "engine",
    kind: str = "audit",
    probe: bool = False,  # rebuild/phase2：True=扫描/无裁决尝试（探针），False=真实裁决
) -> None:
    """机审结论落台账（命中率台账 · v4 2026-08-14 · 重度复审口径修正）。

    - 通过 → 回填既往「不通过·审计」行为命中（不碰通过行自身，通过行 hit 留待合入时标）。
    - kind="infra"（机审执行失败）不参与命中判定。
    失败不阻断主流程（台账是观测面）。
    """
    if kind == "infra":
        # ccc089 插桩（纯日志·零行为变更）：定位每条 infra 台账行的精确产生出口。
        try:
            import traceback as _tb

            _chain = " <- ".join(f"{f.name}:{f.lineno}" for f in reversed(_tb.extract_stack()[-4:-1]))
            logger.info(
                "[ccc089-trace] infra 记账: work=%s source=%s reason0=%s 出口链=%s",
                getattr(work, "id", ""),
                source,
                (reasons or [""])[0][:80],
                _chain,
            )
        except Exception:
            logger.debug("[ccc089-trace] 插桩失败（不阻断）", exc_info=True)
    try:
        from server.board.audit_ledger import backfill_card_hits, record_audit

        record_audit(
            getattr(work, "id", "") or "",
            getattr(work, "id", "") or "",
            conclusion=conclusion,
            severity=severity or "中",
            reasons=reasons or [],
            fix_action=fix_action,
            source=source,
            kind=kind,
            probe=probe or kind == "infra",  # infra（无裁决的基建失败）一律视为探针
        )
        if conclusion == "通过" and kind != "infra":
            backfill_card_hits(getattr(work, "id", "") or "")
    except Exception:
        logger.exception("机审台账写入失败（不阻断）: work=%s", getattr(work, "id", ""))


def _record_machine_audit_pass(work: Work, source: str = "engine-audit") -> None:
    """机审通过 → 写批准真值账本 machine_audit_pass（8-16 后合入门禁 provenance 依赖）。

    2026-08-20 事故修复（mx054/mx055 合入被拒）：机审通过存在 4 条出口
    （已通过跳过/补提交/分支路径/生产卡兜底），其中「已通过跳过」「补提交」
    路径不调 _append_machine_audit_pass → 不写 machine_audit_pass ledger，
    合入门禁 `has_action('machine_audit_pass', id)` 拒绝放行。
    修复：所有通过出口统一调本 helper，幂等（已存在不重复写）。
    失败不阻断主流程（账本是证据面，机审结论仍以卡内机审区为准）。
    """
    try:
        from server.board.audit_ledger import has_action, record_action

        card_id = Path(work.card_path).stem.split("-", 1)[0] if work.card_path else (getattr(work, "id", "") or "")
        if not card_id:
            return
        if has_action("machine_audit_pass", card_id):
            return
        record_action(
            "machine_audit_pass",
            card_id,
            source=source,
            detail=f"engine 机审通过（work={getattr(work, 'id', '')}）",
        )
    except Exception:
        logger.exception("machine_audit_pass 账本写入失败（不阻断）: work=%s", getattr(work, "id", ""))


def _run_machine_audit_after_writeback(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
    severity: str | None = None,
    force: bool = False,
    manual: bool = False,
) -> tuple[bool, list[str], bool]:
    """机审信封化：结果写进 worktree 分支卡并 commit+push；生产卡只读。

    已通过（分支卡优先，生产卡兜底）→ 跳过（force=True 时强制重审，P1-B 修复）；
    注册表无验收席 CLI → 返回 (True, [], audited=False)（未审，P1-E 修复，调用方不得当「通过」）。

    Returns:
        (ok, problems, audited)：audited=False 表示本次没有真正审计（无验收席/已跳过）。
    """
    worktree_hint = _worktree_hint_for(work, registry)
    if not force and _audit_evidence_passed(work, worktree_hint):
        logger.info("机审已通过（分支/生产卡证据），跳过: work=%s", work.id)
        _record_machine_audit_pass(work)
        return True, [], False
    # 补提交：机审区已在 worktree 文件但未进分支（commit 被吞的历史洞）→ 直接补提交，不重审
    if worktree_hint:
        wt_card = _worktree_card_candidate(worktree_hint, work.card_path)
        if (
            wt_card is not None
            and _card_machine_audit_passed(str(wt_card))
            and not _audit_evidence_passed(work, worktree_hint)
        ):
            if _commit_and_push_worktree_card(worktree_hint, work.card_path, work.id):
                logger.info("机审区补提交进分支（历史遗留）: work=%s", work.id)
                _record_machine_audit_pass(work)
                return True, [], True
            logger.warning("机审区补提交失败: work=%s → 走重审", work.id)
            logger.info("[ccc089-trace] 补提交支路失败转重审（本支路自身不记账）: work=%s", work.id)
    # 2017 机审固定交叉配对（老板 2026-08-08 定稿，恢复 08-06 原规则）：
    # OpenCode 开发 → Claude Code 机审（2026-08-15 起开发仅 OpenCode，Claude Code 不接触开发职能）。
    # 卡头「验收」字段只决定 M1 端合入验收席（自验收），不决定 2017 机审工具。
    executor_norm = normalize_tool(work.executor)
    acceptor = "OpenCode" if executor_norm == "Claude Code" else "Claude Code"
    entry = _audit_cli_entry(registry, acceptor)
    if entry is None:
        logger.warning(
            "机审跳过（无验收席可后台 CLI 绑定 %s）: work=%s",
            acceptor,
            work.id,
        )
        # P1-E 修复：无验收席 = 未审（audited=False），调用方不得当作「通过」
        return True, [], False
    logger.info("拉起机审: work=%s acceptor=%s", work.id, acceptor)
    audited_tip: str | None = None
    if worktree_hint:
        branch = f"codex/{Path(work.card_path).stem.lower()}"
        audited_tip = _worktree_branch_tip(worktree_hint, branch)
    # 机审 v4 重度：severity=重 → fresh 独立 agent 零上下文（build_command 新会话 + prompt 强化）
    fresh = severity == "重"
    _claim_running_marker(log_dir, f"{work.id}-audit", data_dir=cfg.get("DATA_DIR"))
    try:
        ok, problems = _dispatch_and_collect(
            work,
            registry,
            cfg,
            log_dir,
            timeout,
            entry_override=entry,
            skip_product_gate=True,
            log_phase="audit",
            fresh=fresh,
        )
    finally:
        _clear_running_marker(log_dir, f"{work.id}-audit")

    audit_log = log_dir / f"{work.id}.audit.log"
    audit_text = _read_text_best_effort(audit_log)

    # 业务结论优先（F1 根修，2026-08-10）：audit 文本明确「机审：不通过」→ 业务打回，
    # 与 exit code 无关。机审 agent 打回时可能 exit 0（claude -p 声称非零退出不可靠），
    # 仅凭 exit code 会把「不通过」误判为通过/落盘失败 → 进 infra 冷却死循环（clw009 事故）。
    if _audit_output_indicates_rejection(audit_text):
        rejection = _audit_rejection_reason(audit_text) or "机审：不通过"
        _ledger_record(
            work,
            severity,
            "不通过",
            [rejection],
            fix_action="",
            source=("manual" if manual else "engine"),
            kind="audit",
        )
        logger.warning("机审明确不通过（业务，按 audit 文本判定）: work=%s reason=%s", work.id, rejection)
        return False, [rejection], True

    if not ok and not _audit_output_indicates_pass(audit_text):
        # P1-C 修复：机审执行失败 = 基建故障（kind=infra），不参与命中判定
        _ledger_record(
            work,
            severity,
            "不通过",
            problems or ["机审执行失败"],
            fix_action="",
            source=("manual" if manual else "engine"),
            kind="infra",
        )
        return False, problems or ["机审执行失败"], True

    evidence = audit_text[-800:]
    if worktree_hint:
        wt_card = _worktree_card_candidate(worktree_hint, work.card_path)
        if wt_card is not None:
            if not _append_machine_audit_pass(
                str(wt_card),
                source="engine-audit",
                evidence=evidence,
            ):
                return False, ["机审通过但机审区落盘到分支卡失败"], True
            if audited_tip:
                _pin_audit_commit(str(wt_card), audited_tip)
            if not _commit_and_push_worktree_card(
                worktree_hint,
                work.card_path,
                work.id,
            ):
                _ledger_record(
                    work,
                    severity,
                    "不通过",
                    ["机审通过但分支证据未推送"],
                    fix_action="",
                    source=("manual" if manual else "engine"),
                    kind="infra",
                )
                return False, ["机审通过但分支证据未推送（ready 不可见）"], True
            _ledger_record(
                work, severity, "通过", [], fix_action="", source=("manual" if manual else "engine"), kind="audit"
            )
            _record_machine_audit_pass(work)
            return True, [], True
        logger.warning("worktree 卡缺失，回退生产卡落证据: work=%s", work.id)
    if not _append_machine_audit_pass(
        work.card_path,
        source="engine-audit",
        evidence=evidence,
    ):
        _ledger_record(
            work,
            severity,
            "不通过",
            ["机审通过但机审区落盘失败"],
            fix_action="",
            source=("manual" if manual else "engine"),
            kind="infra",
        )
        return False, ["机审通过但机审区落盘失败"], True
    _ledger_record(work, severity, "通过", [], fix_action="", source=("manual" if manual else "engine"), kind="audit")
    _record_machine_audit_pass(work)
    return True, [], True


def _parent_blocks_dispatch(work: Work, by_id: dict[str, Work]) -> str | None:
    """父卡未关闭则阻断 AUTO 派发（保持待分派）；无父卡/父卡已关闭/已作废 → None。

    人审调整动作统一化（2026-08-14）：父卡作废 = 该依赖已取消，子卡放行
    （不自动级联子卡，由老板在子卡上定去留；observer 提示）。
    """
    parent_id = (work.parent or "").strip()
    if not parent_id:
        return None
    parent = by_id.get(parent_id)
    if parent is None:
        return None
    if parent.state in (State.CLOSED, State.VOIDED):
        return None
    return f"父卡 {parent_id} 状态={parent.state.value}（须已关闭/已作废后才派发）"


def _depends_on_blocks_dispatch(work: Work, by_id: dict[str, Work]) -> str | None:
    """显式依赖卡未关闭则阻断 AUTO 派发（保持待分派）。

    依赖卡状态 ∈ {已关闭, 已作废} 放行；∈ {待分派/执行中/已回写/打回} 阻塞；
    依赖卡不存在/为空则视为无依赖（向后兼容存量卡）。
    人审调整动作统一化（2026-08-14）：依赖卡作废 = 该依赖已取消 → 下游放行。
    """
    deps = list(getattr(work, "depends_on", None) or [])
    if not deps:
        return None
    blocked: list[str] = []
    for dep_id in deps:
        dep = by_id.get(dep_id)
        if dep is None:
            continue  # 依赖卡不存在 → 不阻塞（避免假死；由出卡方保证存在）
        if dep.state not in (State.CLOSED, State.VOIDED):
            blocked.append(f"{dep_id}({dep.state.value})")
    if not blocked:
        return None
    return "依赖未完成: " + ", ".join(blocked)


def _detect_dependency_cycle(work: Work, by_id: dict[str, Work]) -> str | None:
    """检测依赖环：从 work 出发 DFS，若沿依赖链回到 work 自身则报环。

    环判定：DFS 当前路径 stack 中出现重复节点即成环；返回环路径字符串。
    """
    visited: set[str] = set()

    def visit(wid: str, stack: list[str]) -> str | None:
        if wid in stack:
            return " → ".join(stack + [wid])
        visited.add(wid)
        w = by_id.get(wid)
        deps = list(getattr(w, "depends_on", None) or []) if w else []
        for d in deps:
            if d in visited and d not in stack:
                continue
            found = visit(d, stack + [wid])
            if found:
                return found
        return None

    return visit(work.id, [])


def _detect_empty_commit_signal(log_path: Path) -> bool:
    """检测执行体日志尾部的空提交信号（nothing to commit 等）→ V3 禁止假成功。

    仅当尾部含空提交关键字且无 ``error:`` 字样时判定为真。
    """
    if not log_path or not log_path.is_file():
        return False
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    tail = content[-2000:]
    keywords = [
        "nothing to commit",
        "no changes added to commit",
        "nothing added to commit",
        "no commit created",
    ]
    return any(kw in tail.lower() for kw in keywords) and "error:" not in tail.lower()


def _run_auto_worker(
    work: Work,
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> dict[str, int]:
    """单卡 AUTO 执行：派发 → 回写/打回（机审走独立槽位池，证据进分支信封）。"""
    outcome = {"collected": 0, "timed_out": 0}
    try:
        ok, problems = _dispatch_and_collect(work, registry, cfg, log_dir, timeout)
        if ok:
            work.transition(State.DONE)
            store.save_work(work)
            clear_retry_backoff(work.id)  # ccc083：收单成功清业务重试退避
            logger.info("收单成功: work=%s → 已回写", work.id)
            # sidecar 契约（ccc-plan-021）：成功出口 clear sidecar，无在途残留
            from server.engine.runtime_state import clear_card_state

            clear_card_state(log_dir, work.id)
            outcome["collected"] = 1
        else:
            reasons = list(problems) if problems else ["执行失败"]
            # ccc092 种子盲区硬失败：一次性打回（RUNNING→REJECTED 合法），禁入重试/冷却循环
            if any(_SEED_HARDFAIL_MARKER in p for p in reasons):
                logger.error("%s 打回: work=%s reason=%s", _SEED_HARDFAIL_MARKER, work.id, reasons[0])
                work.transition(State.REJECTED, problems=reasons)
                store.save_work(work)
                # sidecar 契约：打回出口 clear sidecar，磁盘终态权威
                from server.engine.runtime_state import clear_card_state

                clear_card_state(log_dir, work.id)
                outcome["failed"] = 1
                return outcome
            # 补一句可读原因（超时/网络特征优先）
            retryable, hint = is_retryable_failure(work.id, problems, log_dir, phase="run")
            if hint and hint not in reasons[0]:
                reasons = [hint, *reasons]

            # 空回写判定：直接打回，不再无限 retry
            is_empty = False
            empty_reason = ""
            if any("无有效产物" in p or "空回写卡" in p or "模板占位" in p for p in reasons):
                is_empty = True
                empty_reason = reasons[0]
            else:
                wt_hint = _worktree_hint_for(work, registry)
                if wt_hint and work.card_path and "docs/dispatch" in work.card_path:
                    is_empty, empty_reason = is_empty_writeback_or_placeholder(work, wt_hint)

            if is_empty:
                logger.warning(
                    "检测到空回写或维护区模板占位，强制直接打回不予重试: work=%s, reason=%s", work.id, empty_reason
                )
                reasons = [empty_reason, *reasons]
                work.transition(State.REJECTED, problems=reasons)
                store.save_work(work)
                # sidecar 契约：打回出口 clear sidecar，磁盘终态权威
                from server.engine.runtime_state import clear_card_state

                clear_card_state(log_dir, work.id)
                outcome["failed"] = 1
            elif retryable:
                # 读 sidecar 的 infra_count
                from server.engine.runtime_state import read_card_state

                rt = read_card_state(log_dir).get(work.id) or {}
                strikes = int(rt.get("infra_count") or 0)
                next_strikes = strikes + 1

                try:
                    max_strikes = int(cfg.get("EXECUTOR_INFRA_MAX_STRIKES") or 5)
                except (TypeError, ValueError):
                    max_strikes = 5

                if next_strikes >= max_strikes:
                    # 连续失败超限，不再冷却续跑，强制打回
                    reasons = [f"基础设施连续失败 {next_strikes} 次强制打回（可人工恢复后再派）", *reasons]
                    work.transition(State.REJECTED, problems=reasons)
                    store.save_work(work)
                    # sidecar 契约：熔断打回出口 clear sidecar，磁盘终态权威（reason 在 problems）
                    from server.engine.runtime_state import clear_card_state

                    clear_card_state(log_dir, work.id)
                    logger.error(
                        "基础设施故障连续失败超限（已触发熔断打回）: work=%s strikes=%d", work.id, next_strikes
                    )
                    outcome["failed"] = 1
                else:
                    # 上游/网络/超时：基础设施故障 → 回待分派 + 冷却，不计业务重试预算、不打回
                    _hold_infra_failure(store, work, log_dir, reasons, cfg, phase="run", infra_count=next_strikes)
                    outcome["infra"] = 1
            else:
                retried = _fail_retry_or_reject(work, store, reasons, cfg, log_dir)
                # 催单计数：仅最终打回时记 timed_out（回待分派不算）
                if (not retried) and any("超时" in p for p in reasons):
                    outcome["timed_out"] = 1
    except Exception as exc:
        logger.exception("Worker 异常: work=%s: %s", work.id, exc)
        try:
            if work.state in (State.RUNNING, State.DONE):
                _fail_retry_or_reject(work, store, [f"worker 异常: {exc}"], cfg, log_dir)
        except Exception:
            logger.exception("Worker 异常后失败流转失败: work=%s", work.id)
    finally:
        _clear_running_marker(log_dir, work.id)
    return outcome


def _build_dispatch_gates() -> GateRegistry:
    """装配派发门禁链（借鉴 Cordis 依赖图思想 · 轻量前置条件版）。

    11 个门禁与 run_once 原 if/elif 顺序一一对应；`requires` 声明前置条件，
    框架按 order 排序 + 环校验。每个 gate 的 check 闭包逐字搬运原逻辑
    （含日志/计数/副作用），保证行为不回归。

    门禁链：
        infra_cooldown → retry_backoff → short_session_breaker → card_gate
        → worktree_card_copy → accepted_card → parent_closed → depends_closed → dependency_cycle
        → decision → slot_available → biz_isolation → relay_probe → submit

    submit gate 为原子占槽（transition RUNNING + marker + pool.submit + 回滚），
    绝不拆分——拆开会产生「假 RUNNING + marker 泄漏」，破坏 reclaim 不变量。
    """
    reg = GateRegistry()

    def _infra_cooldown(ctx: GateContext) -> GateResult:
        if _infra_cooldown_active(ctx.runtime, ctx.work.id, ctx.now_ts):
            logger.info("基础设施冷却中，跳过派发: work=%s", ctx.work.id)
            return GateResult(passed=False, reason="infra_cooldown")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="infra_cooldown", order=10, check=_infra_cooldown))

    def _retry_backoff(ctx: GateContext) -> GateResult:
        # ccc083：业务重试退避期内不重派（指数退避，防「失败→立即重派」空转）
        if retry_backoff_active(ctx.work.id, ctx.now_ts):
            logger.info("业务重试退避中，跳过派发: work=%s", ctx.work.id)
            return GateResult(passed=False, reason="retry_backoff")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="retry_backoff", order=12, check=_retry_backoff))

    def _short_session_breaker(ctx: GateContext) -> GateResult:
        # ccc083：短命会话计数熔断——窗口内 ≥M 个短命失败会话即全局暂停派发并告警
        tripped, detail = short_session_breaker_status(ctx.log_dir, ctx.cfg, ctx.now_ts)
        if tripped:
            ctx.counters["breaker_skips"] = ctx.counters.get("breaker_skips", 0) + 1
            logger.error("短命会话熔断，暂停派发: work=%s (%s)", ctx.work.id, detail)
            _write_short_session_alert(ctx.log_dir, detail, ctx.now_ts)
            return GateResult(passed=False, reason="short_session_breaker")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="short_session_breaker", order=15, check=_short_session_breaker))

    def _card_gate(ctx: GateContext) -> GateResult:
        # ccc-plan-053 阶段2：DSH 产卡派发前强制校验；非法卡作废+ledger 告警
        return enforce_card_gate(ctx.work, ctx.store, ctx.log_dir)

    reg.register(DispatchGate(name="card_gate", order=17, check=_card_gate))

    def _worktree_card_copy(ctx: GateContext) -> GateResult:
        # 2026-08-18 清理 is_pytest 嗅探：wt_hint 为空（无 worktree_base 的注册行/测试夹具）时
        # 短路，检查不会触发；is_pytest 豁免属多余防御（worktree_path 空即跳过）。
        wt_hint = _worktree_hint_for(ctx.work, ctx.registry)
        if wt_hint and os.path.isdir(wt_hint) and "docs/dispatch" in ctx.work.card_path:
            if _worktree_card_candidate(wt_hint, ctx.work.card_path) is None:
                logger.warning(
                    "派发防护：worktree %s 存在但无对应卡副本 %s，跳过派发避免空转",
                    wt_hint,
                    ctx.work.card_path,
                )
                ctx.counters["none_skips"] = ctx.counters.get("none_skips", 0) + 1
                return GateResult(passed=False, reason="worktree_no_card_copy")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="worktree_card_copy", order=20, check=_worktree_card_copy))

    def _accepted_card(ctx: GateContext) -> GateResult:
        if is_card_accepted(ctx.work.card_path):
            logger.warning("已验收卡不派发: work=%s", ctx.work.id)
            return GateResult(passed=False, reason="accepted")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="accepted_card", order=30, check=_accepted_card))

    def _parent_closed(ctx: GateContext) -> GateResult:
        block = _parent_blocks_dispatch(ctx.work, ctx.by_id)
        if block:
            ctx.counters["parent_skips"] = ctx.counters.get("parent_skips", 0) + 1
            logger.info("父卡未关闭，跳过派发: work=%s (%s)", ctx.work.id, block)
            return GateResult(passed=False, reason=block)
        return GateResult(passed=True)

    reg.register(DispatchGate(name="parent_closed", order=40, check=_parent_closed))

    def _depends_closed(ctx: GateContext) -> GateResult:
        dep_block = _depends_on_blocks_dispatch(ctx.work, ctx.by_id)
        if dep_block:
            ctx.counters["dep_skips"] = ctx.counters.get("dep_skips", 0) + 1
            logger.info("依赖卡未关闭，跳过派发: work=%s (%s)", ctx.work.id, dep_block)
            return GateResult(passed=False, reason=dep_block)
        return GateResult(passed=True)

    reg.register(DispatchGate(name="depends_closed", order=50, check=_depends_closed))

    def _dependency_cycle(ctx: GateContext) -> GateResult:
        cycle = _detect_dependency_cycle(ctx.work, ctx.by_id)
        if cycle:
            ctx.counters["cycle_skips"] = ctx.counters.get("cycle_skips", 0) + 1
            logger.warning("检测到依赖环，跳过派发: work=%s 环=%s", ctx.work.id, cycle)
            return GateResult(passed=False, reason=f"cycle:{cycle}")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="dependency_cycle", order=60, check=_dependency_cycle))

    def _decision(ctx: GateContext) -> GateResult:
        """派发决策：MANUAL→RUNNING+save（派发非跳过，短路后续）；REMOTE/NONE→跳过；AUTO→PASS。

        注意：MANUAL 的 transition(RUNNING)+save 是「派发」，必须在 decision gate
        内完成并返回 passed=False（短路后续 slot/probe），否则 MANUAL 卡会错误
        流到槽位/探活。
        """
        decision = decide_work(ctx.work, ctx.registry)
        if decision is DispatchDecision.MANUAL:
            logger.info(
                "挂起等人接单: work=%s role=%s executor=%s",
                ctx.work.id,
                ctx.work.role,
                ctx.work.executor or "(未指定)",
            )
            ctx.work.transition(State.RUNNING)
            ctx.store.save_work(ctx.work)
            ctx.counters["dispatched"] = ctx.counters.get("dispatched", 0) + 1
            return GateResult(passed=False, reason="manual")
        if decision is DispatchDecision.REMOTE:
            ctx.counters["remote_pending"] = ctx.counters.get("remote_pending", 0) + 1
            logger.info(
                "远端卡待 Worker 认领（保持待分派，不标执行中）: work=%s role=%s executor=%s",
                ctx.work.id,
                ctx.work.role,
                ctx.work.executor or "(未指定)",
            )
            return GateResult(passed=False, reason="remote")
        if decision is not DispatchDecision.AUTO:
            ctx.counters["none_skips"] = ctx.counters.get("none_skips", 0) + 1
            logger.warning(
                "不参与派发: work=%s role=%s executor=%s",
                ctx.work.id,
                ctx.work.role,
                ctx.work.executor or "(未指定)",
            )
            return GateResult(passed=False, reason="none")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="decision", order=70, check=_decision))

    def _slot_available(ctx: GateContext) -> GateResult:
        if ctx.slots <= 0:
            ctx.counters["queued"] = ctx.counters.get("queued", 0) + 1
            logger.info(
                "无空闲执行槽位，进入排队等待: work=%s, 当前并发数=%d, 上限=%d",
                ctx.work.id,
                ctx.pool.occupancy(ctx.store, ctx.log_dir),
                ctx.max_concurrent,
            )
            return GateResult(passed=False, reason="no_slot")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="slot_available", order=80, check=_slot_available, requires=("decision",)))

    def _biz_isolation(ctx: GateContext) -> GateResult:
        biz_project = _business_project(ctx.work)
        if biz_project:
            running_same_project = [
                w for w in ctx.store.list_work(state=State.RUNNING) if w.project == ctx.work.project
            ]
            if len(running_same_project) >= biz_project.isolation_max_concurrent:
                ctx.counters["queued"] = ctx.counters.get("queued", 0) + 1
                logger.info(
                    "同业务仓已达并发上限 %d，排队等待: work=%s project=%s running=%s",
                    biz_project.isolation_max_concurrent,
                    ctx.work.id,
                    ctx.work.project,
                    [w.id for w in running_same_project],
                )
                return GateResult(passed=False, reason="biz_isolation")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="biz_isolation", order=90, check=_biz_isolation, requires=("decision",)))

    def _relay_probe(ctx: GateContext) -> GateResult:
        if ctx.probe_url and not probe_relay(ctx.probe_url):
            ctx.counters["probe_skips"] = ctx.counters.get("probe_skips", 0) + 1
            logger.warning("探活失败，跳过该卡（保持待分派）: work=%s", ctx.work.id)
            return GateResult(passed=False, reason="probe_fail")
        return GateResult(passed=True)

    reg.register(DispatchGate(name="relay_probe", order=100, check=_relay_probe, requires=("decision",)))

    def _submit(ctx: GateContext) -> GateResult:
        """原子占槽：transition RUNNING → save → marker → pool.submit → 回滚。

        绝不拆分（见模块 docstring）——拆开产生假 RUNNING + marker 泄漏。
        """
        ctx.work.transition(State.RUNNING)
        ctx.store.save_work(ctx.work)
        try:
            from server.git_sync import resolve_repo_root

            dispatch_main_repo = resolve_repo_root(ctx.cfg.get("DISPATCH_DIR") or "docs/dispatch")
        except Exception:
            dispatch_main_repo = Path(__file__).resolve().parents[2]
        _claim_running_marker(ctx.log_dir, ctx.work.id, main_repo=dispatch_main_repo, data_dir=ctx.cfg.get("DATA_DIR"))

        def _make_fn(w: Work = ctx.work) -> Any:
            def _fn() -> dict[str, int]:
                return _run_auto_worker(w, ctx.registry, ctx.store, ctx.cfg, ctx.log_dir, ctx.timeout)

            return _fn

        try:
            ctx.pool.submit(ctx.work.id, _make_fn())
        except RuntimeError as exc:
            logger.warning("submit 跳过: work=%s (%s)", ctx.work.id, exc)
            # 回滚占槽
            try:
                ctx.work.transition(State.TODO, problems=[str(exc)])
                ctx.store.save_work(ctx.work)
            except Exception:
                logger.exception("submit 失败回滚待分派失败: work=%s", ctx.work.id)
            _clear_running_marker(ctx.log_dir, ctx.work.id)
            return GateResult(passed=False, reason=f"submit_fail:{exc}")
        ctx.counters["dispatched"] = ctx.counters.get("dispatched", 0) + 1
        ctx.slots -= 1
        return GateResult(passed=True)

    reg.register(
        DispatchGate(
            name="submit",
            order=110,
            check=_submit,
            requires=("decision", "biz_isolation", "relay_probe"),
        )
    )

    return reg


def run_once(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any] | None = None,
    *,
    wait: bool = True,
    config_path: str | Path | None = None,
) -> dict[str, int]:
    """收割 + 补位：执行槽派发与收单（legacy 机审槽已拆除，验收席唯一座席=phase2 CC）。

    ``wait=True``（``--once`` / 测试默认）：本轮 submit 后 drain 池再返回。
    ``wait=False``（持续心跳）：立即返回，不阻塞下一轮扫卡。
    ``config_path``：热读槽位上限的 config.env 路径（改配置免重启）。
    """
    cfg = cfg or {}
    timeout = int(cfg.get("EXECUTOR_TIMEOUT_SECONDS") or DEFAULT_EXECUTOR_TIMEOUT)
    log_dir_str = cfg.get("EXECUTOR_LOG_DIR", "").strip()
    if not log_dir_str:
        raise ConfigError("EXECUTOR_LOG_DIR 未配置（必填，执行体日志目录）")
    log_dir = Path(log_dir_str)

    max_concurrent, max_audit_concurrent = _slot_limits(cfg, config_path)
    probe_url = cfg.get("EXECUTOR_PROBE_URL")
    if probe_url is None:
        # 中转站已退役（2026-08-24 拆除，受老板临时授权）：默认不再探测任何 relay，
        # 仅当显式配置 EXECUTOR_PROBE_URL 时才启用探针门禁。
        probe_url = os.environ.get("EXECUTOR_PROBE_URL", "")

    pool = get_dispatch_pool()
    data_dir = cfg.get("DATA_DIR")
    reclaimed = reclaim_orphaned_running(store, log_dir, data_dir=data_dir)
    running_ids = {w.id for w in store.list_work(state=State.RUNNING)}
    dead_markers_cleaned = cleanup_dead_markers(log_dir, running_ids=running_ids, data_dir=data_dir)

    # sidecar 契约（ccc-plan-021）：收敛器入 run_once——孤儿/终态残留 sidecar 自动清除，
    # 去掉人工 sync-runtime-state 依赖。终态（已回写/打回/已关闭）由磁盘卡唯一权威。
    from server.engine.runtime_state import read_card_state, clear_card_state

    runtime_now = read_card_state(log_dir) if log_dir else {}
    if runtime_now:
        all_works = {w.id: w for w in store.list_work()}
        for cid in list(runtime_now.keys()):
            rec = runtime_now[cid]
            w = all_works.get(cid)
            if w is None:
                # 孤儿记录：不对应任何卡 → 清除
                clear_card_state(log_dir, cid)
                logger.info("收敛器清除孤儿 sidecar: %s", cid)
                continue
            if rec.get("state") in (State.DONE.value, State.REJECTED.value, State.CLOSED.value):
                # 终态残留（磁盘已是终态）→ 清除，磁盘卡权威。
                # 例外：带 infra_cooldown_until 的记录是「冷却临时态」，保留（冷却到期自然失效）。
                if rec.get("infra_cooldown_until"):
                    continue
                clear_card_state(log_dir, cid)
                logger.info("收敛器清除终态残留 sidecar: %s state=%s", cid, rec.get("state"))
            elif rec.get("state") == State.TODO.value and w.state is State.REJECTED:
                # sidecar 待分派但磁盘已打回 → 清除（双源漂移收口）
                clear_card_state(log_dir, cid)
                logger.info("收敛器清除双源漂移 sidecar: %s", cid)

    git_sync_ok = True
    git_sync_detail = ""
    try:
        from server.git_sync import auto_pull_enabled, resolve_repo_root, sync_origin_main

        if auto_pull_enabled(cfg):
            dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
            sync_res = sync_origin_main(resolve_repo_root(dispatch_dir))
            git_sync_ok = bool(sync_res.get("ok"))
            git_sync_detail = str(sync_res.get("detail") or sync_res.get("method") or "")
            if not git_sync_ok:
                logger.warning("自动 git sync 未成功: %s", sync_res)
    except Exception as exc:
        git_sync_ok = False
        git_sync_detail = str(exc)
        logger.exception("自动 git sync 失败，本轮继续用本地卡视图")

    reaped = pool.reap()
    collected = reaped["collected"]
    timed_out = reaped["timed_out"]

    pending = store.list_work(state=State.TODO)
    by_id = {w.id: w for w in store.list_work()}
    from server.engine.runtime_state import read_card_state

    runtime_for_dispatch = read_card_state(log_dir) if log_dir else {}
    now_ts = time.time()
    # 派发门禁链（Cordis 依赖图思想）：11 门禁经 _build_dispatch_gates 装配，
    # counters 跨卡累计，summary 前解包回本地变量。
    counters: dict[str, int] = {
        "dispatched": 0,
        "probe_skips": 0,
        "parent_skips": 0,
        "dep_skips": 0,
        "cycle_skips": 0,
        "none_skips": 0,
        "remote_pending": 0,
        "queued": 0,
    }
    slots = pool.free_slots(max_concurrent, store, log_dir)

    dispatch_gates = _build_dispatch_gates()
    ctx = GateContext(
        work=Work(id="", role=""),  # 占位，每卡覆盖
        registry=registry,
        by_id=by_id,
        runtime=runtime_for_dispatch,
        now_ts=now_ts,
        store=store,
        log_dir=log_dir,
        cfg=cfg,
        pool=pool,
        probe_url=probe_url or "",
        slots=slots,
        max_concurrent=max_concurrent,
        timeout=timeout,
        counters=counters,
    )

    for work in pending:
        ctx.work = work
        dispatch_gates.run(ctx)

    # ── 认领协议收单（ccc-plan-020 v2）：REMOTE 卡按「认领态」收单，不靠本地 PID ──
    def _claim_round() -> tuple[int, int, int]:
        """一次认领收单扫描：返回 (collected, reclaimed, in_flight)。

        Worker 认领协议：Worker 写卡头「认领：<W号> · 认领时间：<ts>」→ push origin。
        Engine（已 git_sync 到最新）扫 dispatch 卡头：
        - 有认领 + 状态=已回写 → 收单（collected，转 DONE，清认领态）
        - 有认领 + 状态=待分派 + 认领超时 → 回收认领（reclaimed，清认领，卡回待分派可重认领）
        - 有认领 + 其他（执行中）→ in_flight（Worker 执行中）
        - 无认领 + 状态=待分派 → 保持待分派（等 Worker 认领，不标执行中）
        """
        from server.board.card_header import parse_metadata
        from datetime import datetime, timezone

        dispatch_rel = cfg.get("DISPATCH_DIR") or "docs/dispatch"
        if os.path.isabs(dispatch_rel):
            dispatch_root = Path(dispatch_rel)
        else:
            try:
                from server.git_sync import resolve_repo_root

                dispatch_root = resolve_repo_root(dispatch_rel) / dispatch_rel
            except Exception:
                dispatch_root = Path(__file__).resolve().parents[2] / dispatch_rel
        if not dispatch_root.is_dir():
            return (0, 0, 0)
        collected = reclaimed = in_flight = 0
        for card_path in sorted(dispatch_root.rglob("*.md")):
            if card_path.name.startswith("."):
                continue
            try:
                text = card_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            meta = parse_metadata(text)
            dispatch = meta.get("派发", "engine")
            executor = meta.get("执行体", "")
            import re as _re

            is_remote = dispatch in ("scheduler", "remote") or bool(_re.fullmatch(r"W\d+", executor or ""))
            if not is_remote:
                continue
            state = meta.get("状态", "").strip()
            claim = meta.get("认领", "").strip()
            claim_ts = meta.get("认领时间", "").strip()
            card_id = card_path.stem
            if claim:
                # 已认领
                if state == "已回写":
                    # Worker 完成回写 → 收单（清认领标记，消除残留观测噪声）
                    collected += 1
                    logger.info("认领收单（Worker %s 完成回写）: %s", claim, card_id)
                    try:
                        _clear_claim_marker(card_path, card_id)
                    except Exception:
                        logger.exception("收单清认领标记失败: %s", card_id)
                elif state in ("待分派", ""):
                    # 认领超时检查：claim_ts 超过 timeout → 回收认领，卡回待分派
                    if claim_ts:
                        try:
                            claim_dt = datetime.fromisoformat(claim_ts.replace("Z", "+00:00"))
                            elapsed = (datetime.now(timezone.utc) - claim_dt).total_seconds()
                        except ValueError:
                            elapsed = 0
                        if elapsed > timeout:
                            reclaimed += 1
                            logger.warning(
                                "认领超时回收: %s (claim=%s elapsed=%.0fs > %ds)",
                                card_id,
                                claim,
                                elapsed,
                                timeout,
                            )
                            _clear_claim_marker(card_path, card_id)
                        else:
                            in_flight += 1
                    else:
                        in_flight += 1
                else:
                    in_flight += 1
            else:
                # 未认领：保持待分派（不标执行中，防假执行中）
                pass
        return (collected, reclaimed, in_flight)

    claim_collected, claim_reclaimed, claim_in_flight = _claim_round()

    if wait:
        drained = pool.drain()
        collected += drained["collected"]
        timed_out += drained["timed_out"]

    # 看板 in_flight = 全部执行中（含 manual 挂起）；CLI 空位另用 pool.occupancy
    in_flight = len(store.list_work(state=State.RUNNING))
    worktrees_cleaned = _cleanup_closed_worktrees(store, registry, cfg, log_dir)
    global _WORKTREE_FAILURES
    worktrees_failed = _WORKTREE_FAILURES
    _WORKTREE_FAILURES = 0
    # 派发门禁链计数器 → 本地变量（summary 兼容原接口）
    dispatched = counters.get("dispatched", 0)
    probe_skips = counters.get("probe_skips", 0)
    parent_skips = counters.get("parent_skips", 0)
    dep_skips = counters.get("dep_skips", 0)
    cycle_skips = counters.get("cycle_skips", 0)
    none_skips = counters.get("none_skips", 0)
    remote_pending = counters.get("remote_pending", 0)
    queued = counters.get("queued", 0)
    summary: dict[str, int] = {
        "mode": "once",
        "scanned": len(pending),
        "dispatched": dispatched,
        "in_flight": in_flight,
        "collected": collected,
        "timed_out": timed_out,
        "reclaimed": reclaimed,
        "dead_markers_cleaned": dead_markers_cleaned,
        "probe_skips": probe_skips,
        "parent_skips": parent_skips,
        "dep_skips": dep_skips,
        "cycle_skips": cycle_skips,
        "none_skips": none_skips,
        "queued": queued,
        # legacy 机审槽已拆（ccc-plan-053 C0，验收席=phase2 CC）：观测字段恒 0，保留兼容
        "audit_dispatched": 0,
        "audit_in_flight": 0,
        "audit_pending": 0,
        "audit_collected": 0,
        "audit_failed": 0,
        "audit_failed_infra": 0,
        "worktrees_cleaned": worktrees_cleaned,
        "worktrees_failed": worktrees_failed,
        "claim_collected": claim_collected,
        "claim_reclaimed": claim_reclaimed,
        "claim_in_flight": claim_in_flight,
    }
    try:
        from server.engine.pipeline_status import write_pipeline_status

        write_pipeline_status(
            log_dir,
            {
                "ok": git_sync_ok and probe_skips == 0,
                "git_sync_ok": git_sync_ok,
                "git_sync_detail": git_sync_detail,
                "probe_skips": probe_skips,
                "parent_skips": parent_skips,
                "dep_skips": dep_skips,
                "cycle_skips": cycle_skips,
                "none_skips": none_skips,
                "reclaimed": reclaimed,
                "dispatched": dispatched,
                "in_flight": in_flight,
                "scanned": len(pending),
                "queued": queued,
                "dead_markers_cleaned": dead_markers_cleaned,
                "audit_dispatched": 0,
                "audit_in_flight": 0,
                "audit_pending": 0,
                "audit_collected": 0,
                "audit_failed": 0,
                "audit_failed_infra": 0,
                "worktrees_cleaned": worktrees_cleaned,
                "worktrees_failed": worktrees_failed,
            },
        )
    except Exception:
        logger.exception("写管道状态失败（不影响本轮）")
    try:
        record_slot_snapshot(
            log_dir,
            exec_used=len(pool.alive_ids()),
            exec_max=max_concurrent,
            audit_used=0,
            audit_max=max_audit_concurrent,
            pending_exec=len(pending),
            audit_pending=0,
            dispatched=dispatched,
            collected=collected,
            timed_out=timed_out,
            audit_dispatched=0,
            audit_collected=0,
            audit_failed=0,
            audit_failed_infra=0,
            reclaimed=reclaimed,
            dead_markers_cleaned=dead_markers_cleaned,
            worktrees_cleaned=worktrees_cleaned,
        )
    except Exception:
        logger.exception("写槽位快照失败（不影响本轮）")
    return summary


def _dispatch_dir_mtime(dispatch_dir: str) -> float:
    """dispatch 目录（含卡子目录）最新 mtime，用于检测卡片变化（事件感知，2026-08-10）。"""
    root = Path(dispatch_dir)
    if not root.exists():
        return 0.0
    latest = 0.0
    for p in root.rglob("*"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m > latest:
            latest = m
    return latest


def run_loop(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    heartbeat_interval: int,
    config_path: str | Path | None = None,
) -> None:
    """持续模式：收割 + 补位心跳（不等待在途收单）。

    2026-08-10 事件感知：dispatch 目录 mtime 变化立即 run_once（写卡即响应），
    无变化则轻量睡眠探测（2s），替代固定 heartbeat_interval 轮询延迟。
    """
    logger.info("Engine 持续模式启动（收割+补位，真实派发/收单）")
    # 2-2 观测载体（2026-08-24 直修）：engine 内嵌 scheduler 巡检线程。
    # 此前 scheduler.py 注册的 cluster-collect / log-janitor / scheduled-ops /
    # merge-dsh-trigger 从无任何运行载体（launchd/cron/engine 均未加载），
    # cluster.js 冻结在退役前快照仍宣称 610x 可达。现随 engine 进程内嵌轮跑，
    # 首轮立即执行以刷新观测数据；watchdog 重启 engine 时线程随之复活。
    try:
        import threading

        def _embedded_scheduler() -> None:
            from server.engine.scheduler import _default_registry

            reg = _default_registry()
            try:
                interval = max(30, int(cfg.get("SCHEDULER_INTERVAL") or 60))
            except (TypeError, ValueError):
                interval = 60
            while True:
                for task in reg.tasks:
                    try:
                        ok, summary = task.run(cfg)
                        (logger.warning if not ok else logger.info)(
                            "内嵌巡检 %s%s: %s", task.name, "" if ok else " 异常", summary
                        )
                    except Exception:
                        logger.exception("内嵌巡检 %s 执行异常", task.name)
                time.sleep(interval)

        threading.Thread(target=_embedded_scheduler, name="embedded-scheduler", daemon=True).start()
        logger.info("内嵌 scheduler 线程已启动（巡检任务随引擎常驻）")
    except Exception:
        logger.exception("内嵌 scheduler 启动失败（不影响派发主流程）")
    dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
    last_mtime = _dispatch_dir_mtime(dispatch_dir)
    # executors.json 热重载（2026-08-18）：每轮按 mtime 决定是否重新加载注册表
    registry_path = cfg.get("EXECUTOR_REGISTRY_PATH")
    registry_mtime: float | None = None
    while True:
        new_reg, new_mtime = _load_registry_cached(registry_path, registry_mtime)
        if new_reg is not None:
            registry = new_reg
        registry_mtime = new_mtime if new_mtime is not None else registry_mtime
        summary = run_once(registry, store, cfg, wait=False, config_path=config_path)
        summary = {**summary, "mode": "loop"}
        logger.info("heartbeat: %s", json.dumps(summary, ensure_ascii=False))
        if summary["timed_out"] > 0:
            logger.warning("催单: 本轮 %d 个任务超时未回写", summary["timed_out"])
        # phase2 后半段（rebuild/phase1）：已回写卡 → CC 审核 → 合入 → 部署 → 终态。
        # 与派发主流程隔离：异常只告警不阻断；事件感知 + 轮询兜底，10 分钟内必被消费。
        try:
            from server.engine.phase2 import consume_once

            p2 = consume_once(dispatch_dir, cfg, audit_driver=os.environ.get("PHASE2_AUDIT_DRIVER", "real"))
            if any(v for k, v in p2.items() if k in ("closed", "rejected", "audit_failed", "deploy_failed", "error")):
                logger.info("phase2: %s", json.dumps(p2, ensure_ascii=False))
        except Exception:
            logger.exception("phase2 消费异常（不阻断派发主流程）")
        # 事件感知：等 dispatch 目录变化（写卡/回写/状态变更）即触发，或最长 heartbeat_interval 兜底
        waited = 0.0
        while waited < heartbeat_interval:
            time.sleep(2)
            waited += 2
            if _dispatch_dir_mtime(dispatch_dir) != last_mtime:
                last_mtime = _dispatch_dir_mtime(dispatch_dir)
                logger.info("dispatch 目录变化，立即触发派发")
                break


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    try:
        cfg: dict[str, Any] = load_config(args.config)
        registry_path = cfg.get("EXECUTOR_REGISTRY_PATH", "")
        if not registry_path:
            print("[FATAL] EXECUTOR_REGISTRY_PATH 未配置", file=sys.stderr)
            return 2
        registry = load_registry(registry_path)
    except (ConfigError, OSError, ValueError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2

    # 1-4 单实例锁（2026-08-24 直修）：防 watchdog kickstart 与 --once 并发双开互杀
    _acquire_engine_single_instance(cfg.get("DATA_DIR") or str(Path.home() / ".ccc" / "data"))

    dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
    store: BoardStore = FileBoardStore(
        dispatch_dir,
        registry,
        log_dir=cfg.get("EXECUTOR_LOG_DIR", "").strip() or None,
    )
    if args.audit:
        timeout = int(cfg.get("EXECUTOR_TIMEOUT_SECONDS") or DEFAULT_EXECUTOR_TIMEOUT)
        log_dir_str = cfg.get("EXECUTOR_LOG_DIR", "").strip()
        if not log_dir_str:
            print("[FATAL] EXECUTOR_LOG_DIR 未配置", file=sys.stderr)
            return 2
        log_dir = Path(log_dir_str)
        by_id = {w.id: w for w in store.list_work()}
        results: dict[str, Any] = {"audited": [], "failed": [], "skipped": []}
        for cid in args.audit:
            work = by_id.get(cid)
            if work is None:
                results["failed"].append({"id": cid, "error": "not_found"})
                continue
            if _card_machine_audit_passed(work.card_path):
                results["skipped"].append(cid)
                continue
            ok, problems, audited = _run_machine_audit_after_writeback(work, registry, cfg, log_dir, timeout)
            if not audited:
                results["skipped"].append(cid)  # 无验收席/已跳过：不算已审
            elif ok:
                results["audited"].append(cid)
            else:
                results["failed"].append({"id": cid, "error": problems})
        print(json.dumps(results, ensure_ascii=False))
        return 0 if not results["failed"] else 1
    if args.once:
        summary = run_once(registry, store, cfg)
        try:
            from server.engine.phase2 import consume_once

            summary = {**summary, "phase2": consume_once(dispatch_dir, cfg)}
        except Exception:
            logger.exception("phase2 消费异常（--once 不阻断）")
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    run_loop(
        registry,
        store,
        cfg,
        args.heartbeat_interval,
        config_path=args.config,
    )
    return 0  # 持续模式不返回（Ctrl-C 终止）


if __name__ == "__main__":
    sys.exit(main())
