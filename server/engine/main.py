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
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from server.config.loader import ConfigError, load_config
from server.engine.dispatch import (
    DispatchDecision,
    ExecutorRegistry,
    build_command,
    decide_work,
    load_registry,
)
from server.engine.store import BoardStore, FileBoardStore
from server.engine.task import State, Work

logger = logging.getLogger("ccc.engine")

DEFAULT_HEARTBEAT_SECONDS = 60
DEFAULT_EXECUTOR_TIMEOUT = 300

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


def is_retryable_failure(work_id: str, problems: list[str], log_dir: Path) -> tuple[bool, str]:
    """判断执行体是否因上游问题非正常结束（退出码非 0 且日志含超时/网络特征，或执行超时）。"""
    if any("超时" in p for p in problems) or any("timeout" in p.lower() for p in problems):
        return True, "执行超时"

    log_path = log_dir / f"{work_id}.log"
    if log_path.is_file():
        try:
            log_content = log_path.read_text(encoding="utf-8", errors="ignore").lower()
            keywords = [
                "timeout", "timed out", "connection error", "network error",
                "network unreachable", "host unreachable", "dns resolution",
                "connection reset", "broken pipe", "bad gateway",
                "service unavailable", "gateway timeout", "502", "503", "504",
                "relay error", "read timeout", "connect timeout", "connection timed out"
            ]
            for kw in keywords:
                if kw in log_content:
                    return True, f"日志含网络或超时特征: {kw}"
        except Exception as exc:
            logger.warning("读取日志判断重试失败: %s (%s)", log_path, exc)

    return False, ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine",
        description="CCC Engine 薄驱动核心（负责真实派发/收单）",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次扫描 + 派发 + 收单后退出")
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


def _worktree_has_new_commit(worktree_path: str) -> bool:
    """worktree 内相对 origin/main 是否有 ≥1 个未合入新 commit（产物证据之一）。

    命令失败（目录/分支不存在、非 git 等）一律视为无新 commit；不抛异常。
    """
    if not worktree_path or not os.path.isdir(worktree_path):
        return False
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "log", "origin/main..HEAD", "--oneline"],
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
    """卡头「状态」段是否已为「已回写」（另一个产物证据）。

    OpenCode/Claude Code 在 worktree 内回写共享任务卡到「已回写」即视为有产物。
    """
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
                return seg[len("状态："):].strip() == "已回写"
    return False


def _dispatch_and_collect(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> tuple[bool, list[str]]:
    """真实派发单个 work + 同步收单。

    Returns:
        (ok, problems)：ok=True → 已回写；ok=False → 打回（附问题清单）。
    """
    entry = None
    if work.executor:
        entry = registry.cli_entry_for_binding(work.executor, project=work.project)
    if entry is None:
        entry = registry.cli_entry_for_role(work.role, project=work.project)

    if entry is None:
        return False, [f"无法为卡片找到对应的可后台 CLI 注册行 (role={work.role}, executor={work.executor}, project={work.project})"]

    default_workdir = cfg.get("DATA_DIR", "")
    worktree_path = ""
    worktree_base = getattr(entry, "worktree_base", "")

    if worktree_base:
        target_worktree = get_worktree_path(worktree_base, work.id)
        card_id_slug = Path(work.card_path).stem.lower() if work.card_path else work.id.lower()
        branch_name = f"codex/{card_id_slug}"

        try:
            target_path = Path(target_worktree).expanduser().resolve()
            if target_path.exists():
                logger.info("Worktree 目录已存在，重用: %s", target_worktree)
                worktree_path = str(target_path)
            else:
                # 尝试用新分支创建
                cmd_add = ["git", "worktree", "add", str(target_path), "-b", branch_name, "origin/main"]
                logger.info("正在创建 worktree: %s", " ".join(cmd_add))
                res = subprocess.run(cmd_add, capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    worktree_path = str(target_path)
                    logger.info("Worktree 创建成功: %s (分支 %s)", worktree_path, branch_name)
                else:
                    logger.warning("git worktree add -b 失败: %s. 尝试关联已存在分支...", res.stderr.strip())
                    # 尝试关联已存在的分支
                    cmd_add_existing = ["git", "worktree", "add", str(target_path), branch_name]
                    res_existing = subprocess.run(cmd_add_existing, capture_output=True, text=True, check=False)
                    if res_existing.returncode == 0:
                        worktree_path = str(target_path)
                        logger.info("Worktree 关联已有分支成功: %s", worktree_path)
                    else:
                        logger.warning("git worktree add 关联已有分支也失败: %s. 自动回退到默认工作目录行为。", res_existing.stderr.strip())
        except Exception as exc:
            logger.warning("创建/获取 worktree 过程发生异常: %s. 自动回退到默认工作目录行为。", exc)

    try:
        cmd = build_command(
            entry,
            work_id=work.id,
            role=work.role,
            card_path=work.card_path,
            default_workdir=default_workdir,
            worktree=worktree_path,
        )
    except ValueError as exc:
        return False, [f"命令构造失败: {exc}"]

    log_path = log_dir / f"{work.id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("拉起执行体: work=%s role=%s cmd=%s log=%s", work.id, work.role, cmd, log_path)

    logf = None
    try:
        child_env = os.environ.copy()
        # 减轻 Python 类执行体块缓冲；Node/Claude 仍可能块缓冲（非 TTY），见日志延迟。
        child_env.setdefault("PYTHONUNBUFFERED", "1")
        # 日志句柄必须保持到 wait 结束：过早 close 会导致子进程 stdout 断开、看板 log_tail 空白
        logf = log_path.open("w", encoding="utf-8", buffering=1)
        logf.write(
            f"[ccc.engine] start work={work.id} pid_pending cmd={' '.join(cmd)}\n"
        )
        logf.flush()
        proc = subprocess.Popen(  # noqa: S603 - 命令来自注册表配置，非用户输入
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=worktree_path or entry.workdir or default_workdir or None,
            env=child_env,
        )
        # 标记写入子进程 PID：Engine 重启时若 CLI 仍活，不得假打回
        _refresh_running_marker_child(log_dir, work.id, proc.pid)
        logf.write(f"[ccc.engine] child_pid={proc.pid}\n")
        logf.flush()
    except FileNotFoundError as exc:
        if logf is not None:
            logf.close()
        return False, [f"启动失败（命令不存在）: {exc}"]
    except OSError as exc:
        if logf is not None:
            logf.close()
        return False, [f"启动失败: {exc}"]

    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return False, [f"执行超时（{timeout}s 已 kill）"]
    finally:
        if logf is not None:
            try:
                logf.close()
            except OSError:
                pass

    if returncode == 0:
        # ccc003 收单防假成功：exit 0 后追加产物核验（worktree 派发路径）。
        # sandbox 假成功 —— OpenCode exit 0 却无产物，不得回写。产物证据二选一：
        #   · worktree 内相对 origin/main 有 ≥1 新 commit；
        #   · 卡头已回写为「已回写」。
        # 仅 worktree 存在时核验（Claude Code/OpenCode 派发必经 worktree）；无 worktree
        # 的简单执行体不回写卡头，走旧行为，避免误伤。
        if worktree_path:
            has_product = _worktree_has_new_commit(worktree_path) or _card_is_written_back(work.card_path)
            if not has_product:
                logger.warning(
                    "exit 0 但无产物（疑似 sandbox 假成功）: work=%s worktree=%s → 打回",
                    work.id, worktree_path,
                )
                return False, [
                    f"exit 0 但无产物（疑似 sandbox 假成功）: worktree {worktree_path} 无新 commit "
                    f"（git log origin/main..HEAD 为空）且卡头未回写为已回写"
                ]
        return True, []
    return False, [f"退出码非 0: {returncode}（日志: {log_path}）"]


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


def reclaim_orphaned_running(store: BoardStore, log_dir: Path) -> int:
    """回收带 ``{work_id}.running`` 标记的「执行中」残留（AUTO 崩溃未收单）。

    manual 挂起等人不会写标记，故不被误打回。
    若标记含任一存活 PID（Engine 收单进程 **或** 子 CLI），**跳过回收**——
    避免 launchd KeepAlive / 手动 ``--once`` / Engine 重启误打回仍在跑的 CLI。
    返回打回张数。
    """
    n = 0
    for w in store.list_work(state=State.RUNNING):
        marker = log_dir / f"{w.id}.running"
        if not marker.is_file():
            continue
        try:
            raw = marker.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        owner_pids = _parse_running_marker_pids(raw)
        alive = [p for p in owner_pids if _pid_alive(p)]
        if alive:
            logger.info(
                "跳过孤儿回收: work=%s 存活 pid=%s（标记=%s）",
                w.id,
                alive,
                owner_pids,
            )
            continue
        try:
            w.transition(
                State.REJECTED,
                problems=["Engine 中断未收单，自动打回"],
            )
            store.save_work(w)
            n += 1
            logger.warning("回收孤儿执行中: work=%s → 打回", w.id)
        except Exception:
            logger.exception("回收孤儿执行中失败: work=%s", w.id)
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass
    return n


def _write_running_marker(
    log_dir: Path,
    work_id: str,
    *,
    engine_pid: int,
    child_pid: int | None = None,
) -> Path:
    """写运行标记：主 ``pid=`` 优先子进程，否则 Engine；并保留 engine/child 字段。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    marker = log_dir / f"{work_id}.running"
    primary = child_pid if child_pid is not None else engine_pid
    lines = [f"engine_pid={engine_pid}\n", f"pid={primary}\n"]
    if child_pid is not None:
        lines.append(f"child_pid={child_pid}\n")
    marker.write_text("".join(lines), encoding="utf-8")
    return marker


def _claim_running_marker(log_dir: Path, work_id: str) -> Path:
    """AUTO 派发起写运行标记（先记 Engine PID；子进程拉起后 refresh）。"""
    return _write_running_marker(log_dir, work_id, engine_pid=os.getpid())


def _refresh_running_marker_child(log_dir: Path, work_id: str, child_pid: int) -> None:
    """子 CLI 已 Popen → 标记改写为 child_pid（防 Engine 重启假打回）。"""
    _write_running_marker(
        log_dir, work_id, engine_pid=os.getpid(), child_pid=child_pid
    )


def _clear_running_marker(log_dir: Path, work_id: str) -> None:
    try:
        (log_dir / f"{work_id}.running").unlink(missing_ok=True)
    except OSError:
        pass


def _parent_blocks_dispatch(work: Work, by_id: dict[str, Work]) -> str | None:
    """父卡未关闭则阻断 AUTO 派发（保持待分派）；无父卡/父卡已关闭 → None。"""
    parent_id = (work.parent or "").strip()
    if not parent_id:
        return None
    parent = by_id.get(parent_id)
    if parent is None:
        return None
    if parent.state is State.CLOSED:
        return None
    return f"父卡 {parent_id} 状态={parent.state.value}（须已关闭后才派发）"


def run_once(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any] | None = None,
) -> dict[str, int]:
    """单次扫描 + 派发 + 收单。

    1. 扫描「待分派」work；
    2. 按卡头执行体绑定优先决策（T39）：可后台 CLI → 真实拉起执行体 + 同步/并发收单；
       手动 GUI → 挂起等人；管理席/验收席/未知角色 → 不派发；
    3. 收单：按退出码 + 输出判定 → 状态机流转（执行中 → 已回写/打回/待分派重试）。
    """
    cfg = cfg or {}
    timeout = int(cfg.get("EXECUTOR_TIMEOUT_SECONDS") or DEFAULT_EXECUTOR_TIMEOUT)
    log_dir_str = cfg.get("EXECUTOR_LOG_DIR", "").strip()
    if not log_dir_str:
        raise ConfigError("EXECUTOR_LOG_DIR 未配置（必填，执行体日志目录）")
    log_dir = Path(log_dir_str)
    default_workdir = cfg.get("DATA_DIR", "")

    max_concurrent = int(cfg.get("EXECUTOR_MAX_CONCURRENT") or 2)
    parallel_enabled = max_concurrent > 1
    probe_url = cfg.get("EXECUTOR_PROBE_URL")
    if probe_url is None:
        probe_url = os.environ.get("EXECUTOR_PROBE_URL", "http://127.0.0.1:6100/")

    # 回收上次崩溃残留的 AUTO「执行中」（有 .running 标记；manual 挂起无标记）
    reclaimed = reclaim_orphaned_running(store, log_dir)

    git_sync_ok = True
    git_sync_detail = ""
    # 生产仓自动对齐 origin/main（人只 push；2017 自 pull，老板不参与中间运维）
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

    pending = store.list_work(state=State.TODO)
    by_id = {w.id: w for w in store.list_work()}
    dispatched = 0
    collected = 0
    timed_out = 0
    probe_skips = 0
    parent_skips = 0
    none_skips = 0

    if parallel_enabled:
        threads = []
        results = {"collected": 0, "timed_out": 0}
        semaphore = threading.Semaphore(max_concurrent)
        lock = threading.Lock()

        def worker(w: Work):
            marker: Path | None = None
            try:
                with semaphore:
                    # 获锁后再标执行中，避免排队期虚高「执行中」
                    w.transition(State.RUNNING)
                    store.save_work(w)
                    marker = _claim_running_marker(log_dir, w.id)
                    ok, problems = _dispatch_and_collect(w, registry, cfg, log_dir, timeout)
                    with lock:
                        if ok:
                            w.transition(State.DONE)
                            store.save_work(w)
                            results["collected"] += 1
                            logger.info("收单成功: work=%s → 已回写", w.id)
                        else:
                            retry_enabled = cfg.get("EXECUTOR_RETRY_ONCE", "true").lower() in ("true", "1")
                            is_retryable = False
                            retry_reason = ""
                            if retry_enabled and w.retry_count == 0:
                                is_retryable, retry_reason = is_retryable_failure(w.id, problems, log_dir)

                            if is_retryable:
                                logger.info("自动续作重派: work=%s 上次重试=%d，发现上游/网络波动 (%s)，自动重回待分派", w.id, w.retry_count, retry_reason)
                                w.retry_count = 1
                                w.transition(State.TODO, problems=[retry_reason])
                                store.save_work(w)
                            else:
                                if any("超时" in p for p in problems):
                                    results["timed_out"] += 1
                                w.transition(State.REJECTED, problems=problems)
                                store.save_work(w)
                                logger.warning("收单失败: work=%s → 打回 %s", w.id, problems)
            except Exception as exc:
                logger.exception("Worker thread encountered unexpected error for work %s: %s", w.id, exc)
                try:
                    if w.state is State.RUNNING:
                        w.transition(State.REJECTED, problems=[f"worker 异常: {exc}"])
                        store.save_work(w)
                except Exception:
                    logger.exception("Worker 异常后打回失败: work=%s", w.id)
            finally:
                _clear_running_marker(log_dir, w.id)

        for work in pending:
            # T67 防线 2：已验收卡（## 验收区 后 20 行内 ✅/判定：通过）不派发，保持原状态
            if is_card_accepted(work.card_path):
                logger.warning("已验收卡不派发: work=%s", work.id)
                continue
            block = _parent_blocks_dispatch(work, by_id)
            if block:
                parent_skips += 1
                logger.info("父卡未关闭，跳过派发: work=%s (%s)", work.id, block)
                continue
            decision = decide_work(work, registry)
            if decision is DispatchDecision.AUTO:
                if probe_url and not probe_relay(probe_url):
                    probe_skips += 1
                    logger.warning("探活失败，跳过该卡（保持待分派）: work=%s", work.id)
                    continue

                dispatched += 1
                t = threading.Thread(target=worker, args=(work,))
                threads.append(t)
                t.start()
            elif decision is DispatchDecision.MANUAL:
                logger.info(
                    "挂起等人接单: work=%s role=%s executor=%s",
                    work.id, work.role, work.executor or "(未指定)",
                )
                work.transition(State.RUNNING)
                store.save_work(work)
                dispatched += 1
            else:
                none_skips += 1
                logger.warning(
                    "不参与派发: work=%s role=%s executor=%s",
                    work.id, work.role, work.executor or "(未指定)",
                )

        # Wait for all threads to complete
        for t in threads:
            t.join()

        collected = results["collected"]
        timed_out = results["timed_out"]

    else:
        # Serial Mode (max_concurrent <= 1)
        for work in pending:
            # T67 防线 2：已验收卡（## 验收区 后 20 行内 ✅/判定：通过）不派发，保持原状态
            if is_card_accepted(work.card_path):
                logger.warning("已验收卡不派发: work=%s", work.id)
                continue
            block = _parent_blocks_dispatch(work, by_id)
            if block:
                parent_skips += 1
                logger.info("父卡未关闭，跳过派发: work=%s (%s)", work.id, block)
                continue
            decision = decide_work(work, registry)
            if decision is DispatchDecision.AUTO:
                if probe_url and not probe_relay(probe_url):
                    probe_skips += 1
                    logger.warning("探活失败，跳过该卡（保持待分派）: work=%s", work.id)
                    continue

                work.transition(State.RUNNING)
                store.save_work(work)
                dispatched += 1
                _claim_running_marker(log_dir, work.id)

                try:
                    ok, problems = _dispatch_and_collect(work, registry, cfg, log_dir, timeout)
                    if ok:
                        work.transition(State.DONE)
                        store.save_work(work)
                        collected += 1
                        logger.info("收单成功: work=%s → 已回写", work.id)
                    else:
                        retry_enabled = cfg.get("EXECUTOR_RETRY_ONCE", "true").lower() in ("true", "1")
                        is_retryable = False
                        retry_reason = ""
                        if retry_enabled and work.retry_count == 0:
                            is_retryable, retry_reason = is_retryable_failure(work.id, problems, log_dir)

                        if is_retryable:
                            logger.info("自动续作重派: work=%s 上次重试=%d，发现上游/网络波动 (%s)，自动重回待分派", work.id, work.retry_count, retry_reason)
                            work.retry_count = 1
                            work.transition(State.TODO, problems=[retry_reason])
                            store.save_work(work)
                        else:
                            if any("超时" in p for p in problems):
                                timed_out += 1
                            work.transition(State.REJECTED, problems=problems)
                            store.save_work(work)
                            logger.warning("收单失败: work=%s → 打回 %s", work.id, problems)
                except Exception as exc:
                    logger.exception("串行派发异常: work=%s: %s", work.id, exc)
                    try:
                        if work.state is State.RUNNING:
                            work.transition(State.REJECTED, problems=[f"派发异常: {exc}"])
                            store.save_work(work)
                    except Exception:
                        logger.exception("串行异常后打回失败: work=%s", work.id)
                finally:
                    _clear_running_marker(log_dir, work.id)
            elif decision is DispatchDecision.MANUAL:
                logger.info(
                    "挂起等人接单: work=%s role=%s executor=%s",
                    work.id, work.role, work.executor or "(未指定)",
                )
                work.transition(State.RUNNING)
                store.save_work(work)
                dispatched += 1
            else:
                none_skips += 1
                logger.warning(
                    "不参与派发: work=%s role=%s executor=%s",
                    work.id, work.role, work.executor or "(未指定)",
                )

    in_flight = len(store.list_work(state=State.RUNNING))
    summary: dict[str, int] = {
        "mode": "once",
        "scanned": len(pending),
        "dispatched": dispatched,
        "in_flight": in_flight,
        "collected": collected,
        "timed_out": timed_out,
        "reclaimed": reclaimed,
        "probe_skips": probe_skips,
        "parent_skips": parent_skips,
        "none_skips": none_skips,
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
                "none_skips": none_skips,
                "reclaimed": reclaimed,
                "dispatched": dispatched,
                "in_flight": in_flight,
                "scanned": len(pending),
            },
        )
    except Exception:
        logger.exception("写管道状态失败（不影响本轮）")
    return summary


def run_loop(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    heartbeat_interval: int,
) -> None:
    """持续模式：每轮扫描 + 派发 + 收单，心跳 + 催单日志（超时未回写任务）。"""
    logger.info("Engine 持续模式启动（真实派发/收单）")
    while True:
        summary = run_once(registry, store, cfg)
        summary = {**summary, "mode": "loop"}
        logger.info("heartbeat: %s", json.dumps(summary, ensure_ascii=False))
        if summary["timed_out"] > 0:
            logger.warning("催单: 本轮 %d 个任务超时未回写", summary["timed_out"])
        time.sleep(heartbeat_interval)


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

    dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
    store: BoardStore = FileBoardStore(dispatch_dir, registry)
    if args.once:
        summary = run_once(registry, store, cfg)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    run_loop(registry, store, cfg, args.heartbeat_interval)
    return 0  # 持续模式不返回（Ctrl-C 终止）


if __name__ == "__main__":
    sys.exit(main())
