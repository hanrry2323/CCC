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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
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
from server.engine.metrics import ProcessSampler, record_slot_snapshot, record_worker_event
from server.engine.pool import get_audit_pool, get_dispatch_pool
from server.engine.store import BoardStore, FileBoardStore
from server.engine.task import State, Work
from server.board.roles import normalize_tool

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
    """历史辅助：识别超时/网络特征（现失败默认均可回待分派重试，本函数仅供摘要）。"""
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


def max_retries_from_cfg(cfg: dict[str, Any]) -> int:
    """失败回待分派上限。``EXECUTOR_RETRY_ONCE=false`` → 0（首次即打回）。"""
    retry_enabled = str(cfg.get("EXECUTOR_RETRY_ONCE", "true")).lower() in ("true", "1", "yes")
    if not retry_enabled:
        return 0
    try:
        return max(0, int(cfg.get("EXECUTOR_MAX_RETRIES") or 3))
    except (TypeError, ValueError):
        return 3


def _fail_retry_or_reject(
    work: Work,
    store: BoardStore,
    problems: list[str],
    cfg: dict[str, Any],
) -> bool:
    """失败：写原因；未达上限 → 待分派并 ``retry_count+=1``；否则打回。

    Returns:
        True 若已回待分派（将再派）；False 若已打回。
    """
    max_r = max_retries_from_cfg(cfg)
    reasons = list(problems) if problems else ["失败（未附原因）"]
    if work.retry_count < max_r:
        work.retry_count += 1
        work.transition(State.TODO, problems=reasons)
        store.save_work(work)
        logger.info(
            "失败回待分派重试: work=%s retry=%d/%d problems=%s",
            work.id,
            work.retry_count,
            max_r,
            reasons[:2],
        )
        return True
    work.transition(State.REJECTED, problems=reasons)
    store.save_work(work)
    logger.warning(
        "重试用尽打回: work=%s retry=%d/%d problems=%s",
        work.id,
        work.retry_count,
        max_r,
        reasons[:2],
    )
    return False


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


def _audit_pending_path(log_dir: Path, work_id: str) -> Path:
    return log_dir / f"{work_id}.audit-pending"


def _mark_audit_pending(log_dir: Path, work_id: str) -> None:
    """执行收单成功 → 打「待机审」标记；机审池按标记捞卡（跨重启可恢复）。"""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        _audit_pending_path(log_dir, work_id).touch()
    except OSError:
        logger.exception("写待机审标记失败: work=%s", work_id)


def _clear_audit_pending(log_dir: Path, work_id: str) -> None:
    try:
        _audit_pending_path(log_dir, work_id).unlink(missing_ok=True)
    except OSError:
        pass


def _audit_marker_alive(log_dir: Path, work_id: str) -> bool:
    """``{id}-audit.running`` 标记含任一存活 PID → 机审在途（跨重启防双审）。"""
    marker = log_dir / f"{work_id}-audit.running"
    try:
        raw = marker.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    return any(_pid_alive(p) for p in _parse_running_marker_pids(raw))


def _cleanup_closed_worktrees(
    store: BoardStore,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
) -> int:
    """合入批准后自动清理：已关闭 + worktree 干净 + 分支已合入 → remove + prune。

    有未提交改动 / 仍有执行或机审标记 / 分支未合入 main 的一律跳过，绝不强删。
    顺带清已关闭卡的残留「待机审」标记。返回清理张数。
    """
    cleaned = 0
    try:
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

    for work in store.list_work(state=State.CLOSED):
        if (log_dir / f"{work.id}.running").is_file() or (
            log_dir / f"{work.id}-audit.running"
        ).is_file():
            continue
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
                timeout=30,
                check=False,
            )
            if status.returncode != 0 or status.stdout.strip():
                logger.info("worktree 未清理（有未提交改动或非 git 仓）: %s", wt)
                continue
            merged = subprocess.run(
                ["git", "-C", str(wt), "log", "origin/main..HEAD", "--oneline"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if merged.returncode != 0 or merged.stdout.strip():
                logger.info("worktree 未清理（分支未合入 main）: %s", wt)
                continue
            remove = subprocess.run(
                ["git", "-C", str(main_repo), "worktree", "remove", str(wt)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if remove.returncode != 0:
                logger.warning("worktree remove 失败（跳过）: %s (%s)", wt, remove.stderr.strip())
                continue
            subprocess.run(
                ["git", "-C", str(main_repo), "worktree", "prune"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            _clear_audit_pending(log_dir, work.id)
            cleaned += 1
            logger.info("worktree 已清理（卡已关闭）: %s", wt)
        except Exception as exc:
            logger.warning("worktree 清理异常（跳过）: %s (%s)", wt, exc)
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
                return seg[len("状态："):].strip() == "已回写"
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
    return cand if cand.is_file() else None


def _extract_machine_audit_section(text: str) -> str:
    """取出 ``## 机审区`` 起至下一 ``## `` 或文末。"""
    lines = text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("## 机审区"):
            start = i
            break
    if start < 0:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ") and not lines[j].strip().startswith("## 机审区"):
            end = j
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def _sync_machine_audit_from_worktree(work: Work, worktree_path: str) -> bool:
    """若生产卡无机审通过、worktree 卡有 → 把 ## 机审区 合并进生产卡。"""
    if not work.card_path or _card_machine_audit_passed(work.card_path):
        return _card_machine_audit_passed(work.card_path)
    wt_card = _worktree_card_candidate(worktree_path, work.card_path)
    if wt_card is None or not _card_machine_audit_passed(str(wt_card)):
        return False
    try:
        section = _extract_machine_audit_section(wt_card.read_text(encoding="utf-8"))
        if not section.strip():
            return False
        prod = Path(work.card_path)
        prod_text = prod.read_text(encoding="utf-8")
        # 仅当存在「标题行」机审区才替换；正文「禁止写 ## 机审区」不算
        if re.search(r"^##\s*机审区\s*$", prod_text, flags=re.MULTILINE):
            prod_text = re.sub(
                r"^##\s*机审区[^\n]*\n.*?(?=^##\s|\Z)",
                section,
                prod_text,
                count=1,
                flags=re.MULTILINE | re.DOTALL,
            )
        else:
            prod_text = prod_text.rstrip() + "\n\n" + section
        prod.write_text(prod_text, encoding="utf-8")
        logger.info("机审区已从 worktree 同步到生产卡: %s ← %s", work.card_path, wt_card)
        return _card_machine_audit_passed(work.card_path)
    except OSError as exc:
        logger.warning("同步机审区失败: %s", exc)
        return False


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

    body = text
    for marker in ("pid_pending cmd=", "[ccc.engine] start work="):
        idx = text.find(marker)
        if idx >= 0:
            nl = text.find("\n", idx)
            body = text[nl + 1 :] if nl >= 0 else ""
            break

    if machine_audit_passed_text(body):
        return True
    if "机审：不通过" in body or "机审不通过" in body:
        return False
    return ("机审：通过" in body) or ("机审通过" in body) or ("判定：通过" in body)


def _read_text_best_effort(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return ""


def _append_machine_audit_pass(card_path: str, *, source: str, evidence: str) -> bool:
    """生产卡尚无 ## 机审区时，写入通过机审区（已有机审区则不覆盖）。"""
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
    if re.search(r"^##\s*机审区\s*$", text, flags=re.MULTILINE):
        # 已有机审区：不覆盖（可能是不通过或其他结论）
        return _card_machine_audit_passed(card_path)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    snippet = re.sub(r"\s+", " ", (evidence or "").strip())[:400]
    section = (
        "\n\n## 机审区\n\n"
        "机审：通过\n"
        f"来源：engine 自动落盘（{source}）· {stamp}\n"
        f"证据：{snippet or '见 audit.log'}\n"
    )
    try:
        prod.write_text(text.rstrip() + section, encoding="utf-8")
    except OSError as exc:
        logger.warning("写入机审区失败: %s (%s)", card_path, exc)
        return False
    ok = _card_machine_audit_passed(card_path)
    if ok:
        logger.info("机审区已自动落盘到生产卡: %s (%s)", card_path, source)
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
) -> tuple[bool, list[str]]:
    """真实派发单个 work + 同步收单。

    Args:
        entry_override: 指定注册表行（机审复用派发时传入验收席 CLI，避免命中开发模板）。
        skip_product_gate: 机审路径跳过「新 commit+diff」门禁（机审不改业务码）。
        log_phase: ``run`` → ``{id}.log``（覆盖前归档）；``audit`` → ``{id}.audit.log``（不碰开发日志）。

    Returns:
        (ok, problems)：ok=True → 已回写；ok=False → 打回（附问题清单）。
    """
    entry = entry_override
    if entry is None and work.executor:
        entry = registry.cli_entry_for_binding(work.executor, project=work.project)
    if entry is None:
        entry = registry.cli_entry_for_role(work.role, project=work.project)

    if entry is None:
        return False, [f"无法为卡片找到对应的可后台 CLI 注册行 (role={work.role}, executor={work.executor}, project={work.project})"]

    _t_start = time.monotonic()
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

    phase = (log_phase or "run").strip().lower() or "run"

    sampler: ProcessSampler | None = None

    def _emit(
        ok: bool,
        returncode: int | None,
        exit_kind: str,
        problems: list[str] | None = None,
    ) -> None:
        try:
            record_worker_event(
                log_dir,
                work_id=work.id,
                phase=phase,
                ok=ok,
                returncode=returncode,
                duration_s=time.monotonic() - _t_start,
                exit_kind=exit_kind,
                peak_rss_mb=sampler.peak_rss_mb if sampler else None,
                peak_cpu_pct=sampler.peak_cpu_pct if sampler else None,
                problems=problems,
            )
        except Exception:
            logger.exception("worker 事件埋点失败（不影响流程）: work=%s", work.id)

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
        logf.write(
            f"[ccc.engine] start work={work.id} phase={phase} pid_pending cmd={' '.join(cmd)}\n"
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
            proc.kill()
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
            # 机械门禁（worktree 派发）：必须有新 commit 且相对 origin/main 非空 diff。
            # 不再承认「仅卡头已回写」为产物（防未写码假成功）。机审路径 skip_product_gate。
            if worktree_path and not skip_product_gate:
                has_commit = _worktree_has_new_commit(worktree_path)
                has_diff = _worktree_has_nonempty_diff(worktree_path)
                if not (has_commit and has_diff):
                    logger.warning(
                        "exit 0 但无有效产物: work=%s worktree=%s commit=%s diff=%s → 打回",
                        work.id, worktree_path, has_commit, has_diff,
                    )
                    _emit(False, 0, "ok", [
                        f"exit 0 但无有效产物（机械门禁）: worktree {worktree_path} "
                        f"须同时满足 origin/main..HEAD 有新 commit 且 diff 非空 "
                        f"(commit={has_commit}, diff={has_diff})"
                    ])
                    return False, [
                        f"exit 0 但无有效产物（机械门禁）: worktree {worktree_path} "
                        f"须同时满足 origin/main..HEAD 有新 commit 且 diff 非空 "
                        f"(commit={has_commit}, diff={has_diff})"
                    ]
            _emit(True, 0, "ok")
            return True, []
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

    manual 挂起等人不会写标记，故不被误回收。
    若标记含任一存活 PID（Engine 收单进程 **或** 子 CLI），**跳过回收**——
    避免 launchd KeepAlive / 手动 ``--once`` / Engine 重启误杀仍在跑的 CLI。
    死标记 → 回「待分派」自动重派（不进打回）。返回重派张数。
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


def _write_running_marker(
    log_dir: Path,
    work_id: str,
    *,
    engine_pid: int,
    child_pid: int | None = None,
) -> Path:
    """写运行标记：主 ``pid=`` 优先子进程，否则 Engine；并保留 engine/child 字段。

    原子写（tmp → rename）：``reclaim_orphaned_running`` 每轮心跳读取标记，
    非原子写入的半截文件会被误判为无存活 PID → 把仍在执行的卡假孤儿回收。
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    marker = log_dir / f"{work_id}.running"
    primary = child_pid if child_pid is not None else engine_pid
    lines = [f"engine_pid={engine_pid}\n", f"pid={primary}\n"]
    if child_pid is not None:
        lines.append(f"child_pid={child_pid}\n")
    tmp = marker.with_suffix(marker.suffix + ".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    os.replace(tmp, marker)
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


def _audit_cli_entry(registry: ExecutorRegistry, acceptor: str) -> ExecutorEntry | None:
    """验收席可后台 CLI 行（机审）；按绑定名匹配。"""
    name = normalize_tool(acceptor)
    if not name:
        return None
    for e in registry.entries:
        if (
            e.role == "验收席"
            and e.category == "可后台 CLI"
            and normalize_tool(e.binding) == name
        ):
            return e
    return None


def _run_machine_audit_after_writeback(
    work: Work,
    registry: ExecutorRegistry,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> tuple[bool, list[str]]:
    """开发收单已回写后：拉起卡头验收方做机审（写 ## 机审区）；已通过则跳过。

    注册表无验收席 CLI → 跳过机审（仅打日志），不阻断已回写。
    """
    if _card_machine_audit_passed(work.card_path):
        logger.info("机审已通过，跳过: work=%s", work.id)
        return True, []
    acceptor = normalize_tool(work.acceptance) or "Claude Code"
    entry = _audit_cli_entry(registry, acceptor)
    if entry is None:
        logger.warning(
            "机审跳过（无验收席可后台 CLI 绑定 %s）: work=%s",
            acceptor,
            work.id,
        )
        return True, []
    logger.info("拉起机审: work=%s acceptor=%s", work.id, acceptor)
    _claim_running_marker(log_dir, f"{work.id}-audit")
    worktree_hint = ""
    wt_base = getattr(entry, "worktree_base", "") or ""
    if wt_base:
        worktree_hint = get_worktree_path(wt_base, work.id)
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
        )
    finally:
        _clear_running_marker(log_dir, f"{work.id}-audit")

    audit_log = log_dir / f"{work.id}.audit.log"
    audit_text = _read_text_best_effort(audit_log)

    def _try_backfill(reason: str) -> bool:
        """worktree 同步失败后：若 audit 输出判定通过则自动落盘（ccc006）。"""
        if worktree_hint and _sync_machine_audit_from_worktree(work, worktree_hint):
            logger.info("机审区已从 worktree 同步通过: work=%s (%s)", work.id, reason)
            return True
        if _card_machine_audit_passed(work.card_path):
            return True
        if not _audit_output_indicates_pass(audit_text):
            return False
        return _append_machine_audit_pass(
            work.card_path,
            source=reason,
            evidence=audit_text[-800:],
        )

    if not ok:
        # 退出非0也可能已写机审区到 worktree / 或日志已判定通过
        if _try_backfill("audit-exit-nonzero"):
            return True, []
        return False, problems or ["机审执行失败"]
    if _card_machine_audit_passed(work.card_path):
        return True, []
    if _try_backfill("audit-log-pass"):
        return True, []
    return False, ["机审结束但卡上无 ## 机审区 通过标记（机审：通过 / ✅ / 判定：通过）"]


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


def _run_auto_worker(
    work: Work,
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> dict[str, int]:
    """单卡 AUTO 执行：派发 → 回写/打回 → 打「待机审」标记（机审走独立槽位池）。"""
    outcome = {"collected": 0, "timed_out": 0}
    try:
        ok, problems = _dispatch_and_collect(work, registry, cfg, log_dir, timeout)
        if ok:
            work.transition(State.DONE)
            store.save_work(work)
            logger.info("收单成功: work=%s → 已回写", work.id)
            _mark_audit_pending(log_dir, work.id)
            outcome["collected"] = 1
        else:
            # 补一句可读原因（超时/网络特征优先）
            _, hint = is_retryable_failure(work.id, problems, log_dir)
            reasons = list(problems) if problems else ["执行失败"]
            if hint and hint not in reasons[0]:
                reasons = [hint, *reasons]
            retried = _fail_retry_or_reject(work, store, reasons, cfg)
            # 催单计数：仅最终打回时记 timed_out（回待分派不算）
            if (not retried) and any("超时" in p for p in reasons):
                outcome["timed_out"] = 1
    except Exception as exc:
        logger.exception("Worker 异常: work=%s: %s", work.id, exc)
        try:
            if work.state in (State.RUNNING, State.DONE):
                _fail_retry_or_reject(work, store, [f"worker 异常: {exc}"], cfg)
        except Exception:
            logger.exception("Worker 异常后失败流转失败: work=%s", work.id)
    finally:
        _clear_running_marker(log_dir, work.id)
    return outcome


def _run_audit_worker(
    work: Work,
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    log_dir: Path,
    timeout: int,
) -> dict[str, int]:
    """单卡机审（独立槽位池）：拉起验收席 CLI 写 ``## 机审区``。

    通过/跳过 → ``collected=1``；不通过 → 清标记、走 ``_fail_retry_or_reject``
    （回待分派重试，用尽才打回）→ ``failed=1``。
    """
    outcome = {"collected": 0, "failed": 0}
    try:
        if _card_machine_audit_passed(work.card_path):
            logger.info("机审已通过，跳过: work=%s", work.id)
            outcome["collected"] = 1
            return outcome
        ok, problems = _run_machine_audit_after_writeback(
            work, registry, cfg, log_dir, timeout
        )
        if ok:
            outcome["collected"] = 1
        else:
            reasons = list(problems) if problems else ["机审：不通过"]
            _fail_retry_or_reject(work, store, reasons, cfg)
            outcome["failed"] = 1
            logger.warning("机审失败: work=%s → %s", work.id, work.state.value)
    except Exception as exc:
        logger.exception("机审 worker 异常: work=%s: %s", work.id, exc)
        try:
            if work.state in (State.RUNNING, State.DONE):
                _fail_retry_or_reject(work, store, [f"机审 worker 异常: {exc}"], cfg)
            outcome["failed"] = 1
        except Exception:
            logger.exception("机审异常后失败流转失败: work=%s", work.id)
    finally:
        _clear_running_marker(log_dir, f"{work.id}-audit")
        _clear_audit_pending(log_dir, work.id)
    return outcome


def run_once(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any] | None = None,
    *,
    wait: bool = True,
    config_path: str | Path | None = None,
) -> dict[str, int]:
    """收割 + 补位：执行槽与机审槽独立派发。

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
        probe_url = os.environ.get("EXECUTOR_PROBE_URL", "http://127.0.0.1:6100/")

    pool = get_dispatch_pool()
    audit_pool = get_audit_pool()
    reclaimed = reclaim_orphaned_running(store, log_dir)

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
    dispatched = 0
    probe_skips = 0
    parent_skips = 0
    none_skips = 0
    slots = pool.free_slots(max_concurrent, store, log_dir)

    for work in pending:
        if is_card_accepted(work.card_path):
            logger.warning("已验收卡不派发: work=%s", work.id)
            continue
        block = _parent_blocks_dispatch(work, by_id)
        if block:
            parent_skips += 1
            logger.info("父卡未关闭，跳过派发: work=%s (%s)", work.id, block)
            continue
        decision = decide_work(work, registry)
        if decision is DispatchDecision.MANUAL:
            logger.info(
                "挂起等人接单: work=%s role=%s executor=%s",
                work.id,
                work.role,
                work.executor or "(未指定)",
            )
            work.transition(State.RUNNING)
            store.save_work(work)
            dispatched += 1
            continue
        if decision is not DispatchDecision.AUTO:
            none_skips += 1
            logger.warning(
                "不参与派发: work=%s role=%s executor=%s",
                work.id,
                work.role,
                work.executor or "(未指定)",
            )
            continue
        if slots <= 0:
            continue
        if probe_url and not probe_relay(probe_url):
            probe_skips += 1
            logger.warning("探活失败，跳过该卡（保持待分派）: work=%s", work.id)
            continue

        # 占槽：先标执行中 + marker，再 submit（空位已按 occupancy 核算）
        work.transition(State.RUNNING)
        store.save_work(work)
        _claim_running_marker(log_dir, work.id)

        def _make_fn(w: Work = work) -> Any:
            def _fn() -> dict[str, int]:
                return _run_auto_worker(w, registry, store, cfg, log_dir, timeout)

            return _fn

        try:
            pool.submit(work.id, _make_fn())
        except RuntimeError as exc:
            logger.warning("submit 跳过: work=%s (%s)", work.id, exc)
            # 回滚占槽
            try:
                work.transition(State.TODO, problems=[str(exc)])
                store.save_work(work)
            except Exception:
                logger.exception("submit 失败回滚待分派失败: work=%s", work.id)
            _clear_running_marker(log_dir, work.id)
            continue

        dispatched += 1
        slots -= 1

    # ── 机审池（独立槽位）：扫「已回写 + 待机审标记 + 未通过」填槽 ──
    def _audit_round() -> tuple[int, int, int, int, int]:
        """一次机审扫描：返回 (dispatched, collected, failed, pending, in_flight)。"""
        audit_alive = audit_pool.alive_ids()
        reaped = audit_pool.reap()
        a_collected = reaped.get("collected", 0)
        a_failed = reaped.get("failed", 0)
        occupied = len(audit_alive)
        for w in store.list_work(state=State.DONE):
            if w.id not in audit_alive and _audit_marker_alive(log_dir, w.id):
                occupied += 1
        a_slots = max(0, int(max_audit_concurrent) - occupied)

        candidates: list[Work] = []
        for work in store.list_work(state=State.DONE):
            if work.id in audit_alive or _audit_marker_alive(log_dir, work.id):
                continue
            if not _audit_pending_path(log_dir, work.id).is_file():
                continue
            if _card_machine_audit_passed(work.card_path):
                _clear_audit_pending(log_dir, work.id)
                continue
            candidates.append(work)
        a_pending = len(candidates)
        a_dispatched = 0
        for work in candidates:
            if a_slots <= 0:
                break

            def _mk_audit(w: Work = work) -> Any:
                def _fn() -> dict[str, int]:
                    return _run_audit_worker(w, registry, store, cfg, log_dir, timeout)

                return _fn

            try:
                audit_pool.submit(work.id, _mk_audit())
            except RuntimeError as exc:
                logger.warning("机审 submit 跳过: work=%s (%s)", work.id, exc)
                continue
            a_dispatched += 1
            a_slots -= 1
        return a_dispatched, a_collected, a_failed, a_pending, len(audit_pool.alive_ids())

    audit_dispatched, audit_collected, audit_failed, audit_pending, audit_in_flight = (
        _audit_round()
    )

    if wait:
        drained = pool.drain()
        collected += drained["collected"]
        timed_out += drained["timed_out"]
        # 执行收单可能新产生「待机审」标记：wait 模式再扫一轮机审并 drain（--once 完整闭环）
        extra = _audit_round()
        audit_dispatched += extra[0]
        audit_collected += extra[1]
        audit_failed += extra[2]
        audit_pending = extra[3]
        audit_in_flight = extra[4]
        audit_drained = audit_pool.drain()
        audit_collected += audit_drained.get("collected", 0)
        audit_failed += audit_drained.get("failed", 0)
        audit_in_flight = len(audit_pool.alive_ids())

    # 看板 in_flight = 全部执行中（含 manual 挂起）；CLI 空位另用 pool.occupancy
    in_flight = len(store.list_work(state=State.RUNNING))
    worktrees_cleaned = _cleanup_closed_worktrees(store, registry, cfg, log_dir)
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
        "audit_dispatched": audit_dispatched,
        "audit_in_flight": audit_in_flight,
        "audit_pending": audit_pending,
        "audit_collected": audit_collected,
        "audit_failed": audit_failed,
        "worktrees_cleaned": worktrees_cleaned,
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
                "audit_dispatched": audit_dispatched,
                "audit_in_flight": audit_in_flight,
                "audit_pending": audit_pending,
                "audit_collected": audit_collected,
                "audit_failed": audit_failed,
                "worktrees_cleaned": worktrees_cleaned,
            },
        )
    except Exception:
        logger.exception("写管道状态失败（不影响本轮）")
    try:
        record_slot_snapshot(
            log_dir,
            exec_used=len(pool.alive_ids()),
            exec_max=max_concurrent,
            audit_used=len(audit_pool.alive_ids()),
            audit_max=max_audit_concurrent,
            pending_exec=len(pending),
            audit_pending=audit_pending,
            dispatched=dispatched,
            collected=collected,
            timed_out=timed_out,
            audit_dispatched=audit_dispatched,
            audit_collected=audit_collected,
            audit_failed=audit_failed,
            reclaimed=reclaimed,
            worktrees_cleaned=worktrees_cleaned,
        )
    except Exception:
        logger.exception("写槽位快照失败（不影响本轮）")
    return summary


def run_loop(
    registry: ExecutorRegistry,
    store: BoardStore,
    cfg: dict[str, Any],
    heartbeat_interval: int,
    config_path: str | Path | None = None,
) -> None:
    """持续模式：收割 + 补位心跳（不等待在途收单）。"""
    logger.info("Engine 持续模式启动（收割+补位，真实派发/收单）")
    while True:
        summary = run_once(registry, store, cfg, wait=False, config_path=config_path)
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
            ok, problems = _run_machine_audit_after_writeback(
                work, registry, cfg, log_dir, timeout
            )
            if ok:
                results["audited"].append(cid)
            else:
                results["failed"].append({"id": cid, "error": problems})
        print(json.dumps(results, ensure_ascii=False))
        return 0 if not results["failed"] else 1
    if args.once:
        summary = run_once(registry, store, cfg)
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
