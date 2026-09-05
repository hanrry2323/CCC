"""server/engine/phase2.py — 后半段自动闭环（rebuild/phase1 · Phase 1）

链路：卡「已回写」 → 引擎自动触发（server.engine.main.run_loop 每轮调用 /
      phase2 --daemon 兜底轮询） → 后段验收插件（现役绑定见 executors.json）审核 → 合入 → 提交 → 部署 → 探活 → 终态。

规则（老板定稿架构 · 后半段）：
- 审核 = 调用注册表「验收席」命令（现役后段审核插件 = Claude Code CLI cc-auditor.sh；
  通道经 M1 中转 3456 → Code，绑定见 executors.json，插座单源）；命令读取失败回退默认；
  调用失败重试 >= 3 次退避；耗尽 → ledger 告警 + 卡保留「已回写」（禁止无声丢卡）。
- 结论「不通过」→ 自动打回 + ledger 记录 + 控制台告警，不阻塞其他卡。
- 结论「通过」→ 合入 main → 门禁 → 提交 push → 部署 web → /health 探活 → 卡置「已关闭」。
- 部署探活失败 → 卡回「已回写（部署失败）」+ ledger 告警，下轮自动重试（分支已在 main 时跳过重复审核）。

用法：
    python -m server.engine.phase2 --config server/config/config.env --once
    python -m server.engine.phase2 --config server/config/config.env --daemon --interval 20
    # 测试隔离（不碰真实 LLM）：--audit-driver mock:pass / mock:reject / mock:error
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from server.engine.card_state_store import CardStateStore
from server.engine.dsh_gateway import ANTHROPIC_BASE_URL, ANTHROPIC_MODEL, cli_env, preflight_gateway

logger = logging.getLogger("ccc.engine.phase2")

_PHASE2_STORE_CACHE: dict[str, CardStateStore] = {}

_WRITTEN = "已回写"
_CLOSED = "已关闭"
_REJECTED = "打回"

_BRANCH_PREFIX = "codex/"

# 卡头「状态：X」字段改写（与 engine main.py 同口径）
_STATE_RE = re.compile(r"(状态\s*[:：]\s*)([^\n·]+?)(?=\s*·|\s*$)")

# Claude Code 结论机器可读标记（规避历史「机审正则坑」）
_PASS_MARKER = "PHASE2_VERDICT: PASS"
_REJECT_MARKER = "PHASE2_VERDICT: REJECT"

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF_BASE = 5.0          # 5s / 10s / 20s ...
_DEFAULT_AUDIT_TIMEOUT = 900
_DEFAULT_HEALTH_TIMEOUT = 30
_DEFAULT_DEPLOY_WAIT = 45


# ───────────────────────── 基础设施 ─────────────────────────


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_env(cfg: dict) -> None:
    """loader / web 依赖 env 定位数据根；与生产（config.env DATA_DIR）对齐。"""
    data_dir = str(cfg.get("DATA_DIR") or "")
    dispatch = str(cfg.get("DISPATCH_DIR") or "docs/dispatch")
    os.environ.setdefault("DATA_DIR", data_dir)
    os.environ.setdefault("CCC_DATA_DIR", data_dir)
    os.environ.setdefault("DISPATCH_DIR", dispatch)


def load_cfg(config_path: str | Path) -> dict:
    from server.config.loader import load_config

    return load_config(config_path)


def git(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """只读/受控 git 调用；超时 120s。"""
    return subprocess.run(
        ["git", *cmd],
        cwd=cwd or _repo_root(),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _current_branch() -> str:
    r = git(["rev-parse", "--abbrev-ref", "HEAD"])
    return (r.stdout or "").strip() or "HEAD"


def _branch_in_main(branch: str, *, base_ref: str = "origin/main") -> bool:
    """判定分支是否已并入远端 main（origin/main 为权威；可测试注入）。

    C-7：原对本地 main 判定——merge 已落本地 main 但 push 失败时误判「已消费」，
    卡 CLOSED→CLOSED 非法转移永久 error。改对 origin/main 判定后，本地领先提交
    由下轮补推收敛。
    """
    r = git(["merge-base", "--is-ancestor", f"origin/{branch}", base_ref])
    return r.returncode == 0


# ───────────────────────── 卡扫描 / 路径 ─────────────────────────


def list_written_cards(dispatch_dir: str | Path) -> list[dict]:
    """扫描「已回写」卡：工作区 dispatch + origin/codex/* 分支信封两路合并去重。

    真实流：DSH 在 `codex/<stem>` 分支上把卡置「已回写」并 push（分支信封），
    引擎消费的「已回写」事实源 = 分支信封；工作区卡兜底（部署重试场景）。
    """
    from server.board.card_header import is_task_card_text  # noqa: F401
    from server.board.loader import load_dispatch_cards, load_index_file
    from server.board.models import base_state

    cards: dict[str, dict] = {}
    d = Path(dispatch_dir)
    idx = load_index_file(d)
    for item in load_dispatch_cards(d, include_archived=False):
        if base_state(item.state) != _WRITTEN:
            continue
        path = idx.get(item.id, {}).get("path", "")
        cards[item.id] = {
            "id": item.id,
            "state": item.state,
            "title": item.title,
            "project": item.project,
            "path_rel": path,
            "path": str(_repo_root() / path) if path and not os.path.isabs(path) else path,
            "branch": "",
            "worktree": _worktree_for(item.project, item.id) or "",
        }
    for bc in _list_branch_written_cards():
        cards.setdefault(bc["id"], bc)
    return list(cards.values())


def _worktree_for(project: str, work_id: str) -> str:
    """按注册表隔离根计算该项目卡的实际 worktree 路径（与 _audit_worktree_path 同源）。

    解决机审误报根因：磁盘上业务 worktree 存在，但 card 对象缺少 worktree 键，
    _run_dsh_auditor 因此在调用 wrapper 前提前判定「worktree 缺失」。
    """
    try:
        from server.board.registry import load_projects

        for entry in load_projects():
            if entry.prefix == project and entry.isolation_worktree_root:
                return str(Path(entry.isolation_worktree_root).expanduser() / work_id.lower())
    except Exception:
        return ""
    return ""


def _list_branch_written_cards() -> list[dict]:
    """扫 origin/codex/* 分支：分支卡状态=已回写 且 main 未关闭 且分支未合入 → 待消费。"""
    from server.board.card_header import CardHeader
    from server.board.models import base_state

    r = git(["for-each-ref", "--format=%(refname)", "refs/remotes/origin/codex/*"])
    cards: list[dict] = []
    for ref in (r.stdout or "").splitlines():
        ref = ref.strip()
        if not ref:
            continue
        branch = ref.replace("refs/remotes/origin/", "")  # codex/<stem>（fetch/show 内部再加 origin/ 前缀）
        diff = git(["diff", "--name-only", "origin/main", ref, "--", "docs/dispatch"])
        for cp in (diff.stdout or "").splitlines():
            cp = cp.strip()
            if not cp.endswith(".md"):
                continue
            show = git(["show", f"{ref}:{cp}"])
            if show.returncode != 0:
                continue
            try:
                hdr = CardHeader.from_text(show.stdout, fallback_id=Path(cp).stem)
            except Exception:  # noqa: BLE001
                continue
            if base_state(hdr.state) != _WRITTEN:
                continue
            mshow = git(["show", f"origin/main:{cp}"])
            if mshow.returncode == 0:
                try:
                    mhdr = CardHeader.from_text(mshow.stdout, fallback_id=Path(cp).stem)
                except Exception:  # noqa: BLE001
                    mhdr = None
                if mhdr is not None and base_state(mhdr.state) in (_CLOSED, _REJECTED):
                    # main 已消费：已关闭，或已打回（打回后分支信封不得重捞）。
                    continue
            if _branch_in_main(branch):
                continue  # 分支已合入 main → 已消费（重试场景由工作区卡接管）
            cards.append(
                {
                    "id": hdr.id,
                    "state": hdr.state,
                    "title": hdr.title,
                    "project": hdr.project,
                    "path_rel": cp,
                    "path": str(_repo_root() / cp),
                    "branch": branch,
                    "worktree": _worktree_for(hdr.project, hdr.id) or "",
                }
            )
    return cards


def resolve_card_file(card: dict) -> Path | None:
    p = Path(card.get("path") or card.get("path_rel") or "")
    if p and p.is_file():
        return p
    return None


def _materialize_card(card: dict) -> None:
    """分支卡落工作区（打回/门禁需在 main 工作区改卡），经统一门面原子物化。"""
    branch = card.get("branch", "")
    rel = card.get("path_rel", "")
    if not branch or not rel:
        return
    show = git(["show", f"origin/{branch}:{rel}"])
    if show.returncode != 0 or not isinstance(show.stdout, str):
        return
    target = _repo_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        _phase2_store().materialize(target, show.stdout, actor="phase2-materialize")
    except Exception as exc:  # noqa: BLE001
        logger.warning("phase2 分支卡物化失败（保留原文）: %s (%s)", target, exc)



def _refresh_index(cfg: dict) -> None:
    """终态写回唯一索引（单一事实源收敛 · rebuild/phase2 打回修复）。

    phase2 关闭/打回/部署失败会直接改卡文件并 push main，但唯一索引
    （~/.ccc/data/cards/cards.index.jsonl）是派生缓存——卡 mtime 变更后需重扫
    才能让索引反映终态。调用 loader 重扫即同步（写点唯一在 loader）。
    """
    _ensure_env(cfg)
    try:
        from server.board.loader import load_dispatch_cards

        dispatch = str(cfg.get("DISPATCH_DIR") or "docs/dispatch")
        load_dispatch_cards(dispatch, include_archived=False)
    except Exception:  # noqa: BLE001
        logger.exception("phase2 索引刷新失败（不阻断）")


def branch_for(card_file: Path) -> str:
    return f"{_BRANCH_PREFIX}{card_file.stem.lower()}"


# ───────────────────────── CC 审核（重试退避）─────────────────────────


def build_audit_prompt(card: dict, card_file: Path, branch: str) -> str:
    return (
        "你是 CCC 平台终审席（Claude Code）。请审核任务卡 {id} 的合入申请。\n\n"
        "仓库：{repo}\n"
        "任务卡：{card}\n"
        "分支：{branch}（相对 origin/main 的改动）\n\n"
        "审核要点：\n"
        "1. 卡头元数据合法（状态应为「已回写」，编号/项目正确）。\n"
        "2. 分支相对 main 的 diff 与卡「范围」一致；无越界、无密钥泄漏、无危险命令。\n"
        "3. 卡「门禁」要求可满足（实现/测试/编译类）。\n"
        "4. 维护区/回写区已如实填写。\n\n"
        "输出格式（严格，机器解析）：\n"
        "第一行必须是：{pass_marker}  或  {reject_marker}\n"
        "随后给 2-5 行理由（中文，标注 severity：严重/中/轻）。\n"
        "不要输出其他格式。"
    ).format(
        id=card["id"],
        repo=_repo_root(),
        card=card_file,
        branch=branch,
        pass_marker=_PASS_MARKER,
        reject_marker=_REJECT_MARKER,
    )


def _claude_verdict_from_output(out: str) -> str | None:
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(_PASS_MARKER):
            return "PASS"
        if line.startswith(_REJECT_MARKER):
            return "REJECT"
    for line in out.splitlines():
        line = line.strip()
        if re.search(r"^结论[:：]\s*(通过|PASS)\b", line, re.I):
            return "PASS"
        if re.search(r"^结论[:：]\s*(不通过|REJECT)\b", line, re.I):
            return "REJECT"
    return None


def _extract_reasons(out: str, verdict: str) -> str:
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    body = []
    for ln in lines:
        if ln.startswith((_PASS_MARKER, _REJECT_MARKER)):
            continue
        body.append(ln)
    text = " | ".join(body)
    return text[:500] or ("通过" if verdict == "PASS" else "不通过")


def _dsh_auditor_path(cfg: dict) -> Path:
    """解析后段验收席 wrapper 命令（插座单源：注册表「验收席」行命令）。

    命令来源=执行体注册表（EXECUTOR_REGISTRY_PATH，角色「验收席」行的「命令」），
    2026-09-04 重构批E：后段验收席换 Claude Code CLI wrapper（cc-auditor.sh）。
    优先级：DSH_AUDITOR_BIN 显式覆盖（测试注入）→ 注册表「验收席」命令 →
    回退仓内 dsh-auditor.sh（读取失败/缺失时 warning，不硬断）。
    """
    configured = str(cfg.get("DSH_AUDITOR_BIN") or os.environ.get("DSH_AUDITOR_BIN") or "").strip()
    if configured:
        return Path(configured).expanduser()
    registry_path = str(cfg.get("EXECUTOR_REGISTRY_PATH") or "").strip()
    if registry_path:
        try:
            from server.engine.dispatch import load_registry

            reg = load_registry(registry_path)
            entry = reg.cli_entry_for_role("验收席")
            if entry is not None and entry.command.strip():
                cmd = entry.command.strip()
                p = Path(cmd).expanduser()
                return p if p.is_absolute() else _repo_root() / p
        except Exception as exc:  # noqa: BLE001
            logger.warning("注册表「验收席」命令读取失败，回退默认 auditor: %s", exc)
    logger.warning("未从注册表读到验收席命令，回退 %s", _repo_root() / "scripts" / "dsh-auditor.sh")
    return _repo_root() / "scripts" / "dsh-auditor.sh"


def _audit_log_dir(cfg: dict) -> Path:
    """机审前置工件目录；与 Engine 执行体日志目录保持同源。"""
    raw = cfg.get("EXECUTOR_LOG_DIR") or cfg.get("LOG_DIR") or os.environ.get("EXECUTOR_LOG_DIR")
    return Path(str(raw)).expanduser() if raw else Path.home() / ".ccc" / "logs" / "exec"


def _audit_verdict_path(cfg: dict, work_id: str) -> Path:
    return _audit_log_dir(cfg) / f"{work_id}-audit-verdict.md"


def _audit_result_artifact(card: dict, cfg: dict) -> Path:
    return _audit_log_dir(cfg) / f"{card.get('id')}-ccc-result.md"


def _audit_cooldown_active(card_id: str, cfg: dict) -> bool:
    """同卡机审基础设施失败冷却未到期时跳过本轮。"""
    from datetime import datetime, timezone
    from server.engine.runtime_state import read_card_state

    record = read_card_state(_audit_log_dir(cfg)).get(card_id) or {}
    raw = record.get("infra_cooldown_until")
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return until > datetime.now(timezone.utc)


def _card_is_written(card_file: Path) -> bool:
    if not card_file.is_file():
        return False
    try:
        return _phase2_store(card_file).read_snapshot(card_file).state == _WRITTEN
    except Exception:  # noqa: BLE001
        return False


def _audit_prerequisites(card: dict, card_file: Path, cfg: dict) -> tuple[bool, str]:
    """校验新机审契约：主仓卡已回写 + 执行结果工件存在。

    前置缺失 = 明确原因 fail-fast（熔断路径），不再重试。
    """
    if not _card_is_written(card_file):
        return False, f"机审前置失败：主仓卡不是已回写: {card_file}"
    result = _audit_result_artifact(card, cfg)
    if not result.is_file():
        return False, f"机审前置失败：执行结果工件缺失: {result}"
    return True, ""


def _read_audit_verdict(verdict_file: Path, output: str = "") -> tuple[str | None, str]:
    """从 log_dir 机审工件读取整行结论；stdout 仅作诊断，不作为结论来源。"""
    if not verdict_file.is_file():
        return None, ""
    text = verdict_file.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^机审：通过(?:\s*（([^）]*)）)?\s*$", line)
        if match:
            return "PASS", match.group(1) or ""
        match = re.match(r"^机审：不通过(?:（([^\n）]*)）)?\s*$", line)
        if match:
            return "REJECT", match.group(1) or ""
    return None, ""


def _run_dsh_auditor(card: dict, card_file: Path, branch: str, cfg: dict, timeout: int) -> tuple[int, str, str]:
    """调用后段验收席 wrapper 审计主仓卡；verdict 由 wrapper 写入 log_dir 工件。

    命令来源=注册表（_dsh_auditor_path 读「验收席」行），历史函数名 _run_dsh_auditor
    保留（避免大面改名；2026-09-04 批E 起现役绑定为 Claude Code CLI cc-auditor.sh）。
    业务 worktree 退出机审契约：审计目标 = 主仓卡（只读），不创建/校验 worktree。
    """
    auditor = _dsh_auditor_path(cfg)
    if not auditor.is_file():
        return 127, "", f"机审 wrapper 不存在: {auditor}（当前模型通道={ANTHROPIC_BASE_URL} · {ANTHROPIC_MODEL}）"
    work_id = str(card.get("id") or card_file.stem.split("-", 1)[0])
    # 主仓分支保护（A4 加固）：机审前记录主仓分支，机审后校验未漂移。
    prev_branch = _current_branch()
    # 第 3 位保持 card worktree 原值；第 5 位单独传业务 worktree，供证据检查使用。
    audit_worktree = str(card.get("worktree") or "__CCC_EMPTY__")
    audit_biz_worktree = str(
        card.get("worktree")
        or _worktree_for(str(card.get("project") or ""), work_id)
        or "__CCC_EMPTY__"
    )
    cmd = [str(auditor), str(card_file), work_id, audit_worktree, "验收席", audit_biz_worktree]
    child_env = cli_env()
    audit_log_dir = _audit_log_dir(cfg)
    child_env.setdefault("EXECUTOR_LOG_DIR", str(audit_log_dir))
    child_env.setdefault("LOG_DIR", str(cfg.get("LOG_DIR") or audit_log_dir.parent))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            env=child_env,
            cwd=str(_repo_root()),
        )
        after_branch = _current_branch()
        if after_branch != prev_branch:
            logger.warning("机审后主仓分支漂移: %s -> %s，自动恢复 %s，机审判失败", prev_branch, after_branch, prev_branch)
            git(["checkout", prev_branch])
            return 127, "", f"机审后主仓分支漂移（{prev_branch} -> {after_branch}），已恢复 {prev_branch}，机审失败"
        stdout = proc.stdout or b""
        stderr = proc.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"验收席 wrapper 超时（{timeout}s，当前模型通道={ANTHROPIC_BASE_URL} · {ANTHROPIC_MODEL}）"
    except OSError as exc:
        return 127, "", f"验收席 wrapper 启动失败: {exc}（当前模型通道={ANTHROPIC_BASE_URL} · {ANTHROPIC_MODEL}）"
    except Exception as exc:  # noqa: BLE001
        return 127, "", f"验收席 wrapper 调用异常: {exc}（当前模型通道={ANTHROPIC_BASE_URL} · {ANTHROPIC_MODEL}）"


def _write_audit_verdict(card_file: Path, cfg: dict, verdict: str, reasons: str) -> bool:
    """经 CardStateStore 门面把机审结论写入主仓卡（CAS/锁，禁旁路直写）。"""
    try:
        store = _phase2_store(card_file)
        push = (store.repo_root / ".git").exists()
        store.write_audit_verdict(card_file, verdict=verdict, reasons=reasons, push=push)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("机审区经统一门面落主卡失败: %s (%s)", card_file, exc)
        return False


def _clear_audit_strikes(card_id: str, cfg: dict) -> None:
    """真实机审成功后清零该卡基础设施 strikes 与冷却标记。"""
    from server.engine.runtime_state import write_card_state

    write_card_state(
        _audit_log_dir(cfg),
        card_id,
        infra_count=0,
        infra_cooldown_until="1970-01-01T00:00:00Z",
    )


def _record_audit_failure(
    card: dict,
    card_file: Path,
    cfg: dict,
    reason: str,
    *,
    count_strike: bool = True,
) -> str:
    """记录机审失败；仅真实审计运行失败计入 strikes，其他故障只冷却。"""
    from server.board.audit_ledger import record_action
    from server.engine.runtime_state import clear_card_state, read_card_state
    from server.engine.task import State, Work

    card_id = str(card.get("id") or card_file.stem)
    log_dir = _audit_log_dir(cfg)
    current = read_card_state(log_dir).get(card_id, {})
    # 冷却期内直接跳过：strikes 与冷却均不动，等待冷却自然到期再重试。
    if _audit_cooldown_active(card_id, cfg):
        return "cooldown"
    strikes = int(current.get("infra_count") or 0) + (1 if count_strike else 0)
    try:
        max_strikes = max(
            1,
            int(cfg.get("PHASE2_AUDIT_MAX_STRIKES")
                or cfg.get("EXECUTOR_INFRA_MAX_STRIKES")
                or 3),
        )
    except (TypeError, ValueError):
        max_strikes = 3
    if count_strike and strikes >= max_strikes:
        detail = f"机审基础设施连续失败 {strikes} 次，已挂起待人工处理：{reason}"
        if set_card_state(card_file, f"{_REJECTED}（机审基础设施熔断）", "REJECT", detail):
            clear_card_state(log_dir, card_id)
        record_action("phase2_audit_circuit_open", card_id, source="phase2", detail=detail)
        return "circuit_open"

    # 与派发侧共用同一冷却/sidecar 语义；audit 阶段不改变卡的业务状态。
    from server.engine.main import _hold_infra_failure

    work = Work(id=card_id, role="验收席", state=State.DONE, card_path=str(card_file))

    class _NoopStore:
        def save_work(self, _work: Work) -> None:
            return None

    _hold_infra_failure(
        _NoopStore(),
        work,
        log_dir,
        [reason],
        cfg,
        phase="audit",
        infra_count=strikes if count_strike else 0,
        cooldown_seconds=480 if not count_strike else None,
    )
    return "cooldown"


# 新契约下不创建/校验业务 worktree；旧 helper 已删除。




def audit_card(card: dict, card_file: Path, branch: str, cfg: dict, audit_driver: str = "real") -> dict:
    """CC 审核（mock 驱动仅供测试闭环）。返回 {verdict, reasons, transcript, attempts}。"""
    if audit_driver.startswith("mock:"):
        v = audit_driver.split(":", 1)[1]
        if v == "pass":
            return {"verdict": "PASS", "reasons": "mock-pass（测试隔离）", "transcript": _PASS_MARKER, "attempts": 1}
        if v == "reject":
            return {"verdict": "REJECT", "reasons": "mock-reject（测试隔离）：结论不通过", "transcript": _REJECT_MARKER, "attempts": 1}
        if v == "error":
            return {"verdict": "ERROR", "reasons": "mock-error（测试隔离）", "transcript": "", "attempts": 3}

    try:
        max_attempts = max(1, int(cfg.get("PHASE2_AUDIT_MAX_ATTEMPTS") or _DEFAULT_MAX_ATTEMPTS))
    except (TypeError, ValueError):
        max_attempts = _DEFAULT_MAX_ATTEMPTS
    backoff_base = float(cfg.get("PHASE2_AUDIT_BACKOFF_BASE") or _DEFAULT_BACKOFF_BASE)
    try:
        timeout = max(
            900,
            int(
                cfg.get("PHASE2_AUDIT_TIMEOUT")
                or cfg.get("EXECUTOR_AUDIT_TIMEOUT_SECONDS")
                or _DEFAULT_AUDIT_TIMEOUT
            ),
        )
    except (TypeError, ValueError):
        timeout = _DEFAULT_AUDIT_TIMEOUT

    work_id = str(card.get("id") or card_file.stem.split("-", 1)[0])
    # 预检/探针属于瞬态基础设施故障：冷却期内整卡跳过，不计 strikes。
    if _audit_cooldown_active(work_id, cfg):
        return {
            "verdict": "ERROR",
            "reasons": "机审基础设施冷却中，跳过本轮",
            "transcript": "",
            "attempts": 0,
            "infra": True,
            "cooldown": True,
        }

    # 审核前强制配额预检；3456/Code 是 DSH auditor 的统一出口。
    pf_ok, pf_detail = preflight_gateway(source="phase2")
    if not pf_ok:
        from server.board.audit_ledger import record_action

        record_action("phase2_alert", card["id"], source="phase2", detail=f"网关预检拒单: {pf_detail}")
        logger.error("phase2 网关预检拒单（卡保留已回写待重试）: %s: %s", card["id"], pf_detail)
        return {
            "verdict": "ERROR",
            "reasons": f"网关预检拒单: {pf_detail}",
            "transcript": "",
            "attempts": 0,
            "infra": True,
            # 预检未启动 auditor，所有拒单原因均只冷却，不计真实运行 strikes。
            "transient_probe": True,
        }

    # 新契约前置工件校验：主仓卡已回写 + log_dir 执行结果工件存在。缺失 → fail-fast。

    ok_prereq, prereq_reason = _audit_prerequisites(card, card_file, cfg)
    if not ok_prereq:
        logger.error("phase2 机审前置不满足（仅冷却，不计 strikes）: %s %s", card["id"], prereq_reason)
        return {
            "verdict": "ERROR",
            "reasons": prereq_reason,
            "transcript": "",
            "attempts": 0,
            "infra": True,
            "transient_probe": True,
        }

    work_id = str(card.get("id") or card_file.stem.split("-", 1)[0])
    if _audit_cooldown_active(work_id, cfg):
        return {
            "verdict": "ERROR",
            "reasons": "机审基础设施冷却中，跳过本轮",
            "transcript": "",
            "attempts": 0,
            "infra": True,
            "cooldown": True,
        }
    verdict_file = _audit_verdict_path(cfg, work_id)
    transcript = ""
    reasons = ""
    for attempt in range(1, max_attempts + 1):
        try:
            verdict_file.unlink(missing_ok=True)
        except OSError:
            pass
        rc, out, err = _run_dsh_auditor(card, card_file, branch, cfg, timeout)
        transcript = out
        # verdict 以 log_dir 审计工件为准；exit 2 的 verdict 文件内容视为 REJECT。
        verdict, card_reason = _read_audit_verdict(verdict_file, out)
        if rc == 2 and verdict is not None:
            verdict = "REJECT"
        if rc == 0 and verdict in ("PASS", "REJECT"):
            _clear_audit_strikes(work_id, cfg)
            return {
                "verdict": verdict,
                "reasons": card_reason or _extract_reasons(out, verdict),
                "transcript": out + ("\n" + err if err else ""),
                "attempts": attempt,
            }
        if rc != 0 and verdict == "REJECT":
            reasons = card_reason or f"验收席 wrapper 退出码 {rc}，机审不通过"
            if rc == 2:
                _clear_audit_strikes(work_id, cfg)
                return {
                    "verdict": "REJECT",
                    "reasons": reasons,
                    "transcript": out + ("\n" + err if err else ""),
                    "attempts": attempt,
                }
            reasons = f"验收席 wrapper 基础设施失败（rc={rc}），但工件含不通过：{reasons}"
        else:
            reasons = f"验收席 wrapper 基础设施失败（rc={rc}）: {err or out}"
        logger.warning("后段机审失败重试 %d/%d: %s", attempt, max_attempts, reasons)
        if attempt < max_attempts:
            time.sleep(backoff_base * (2 ** (attempt - 1)))
        continue
    return {"verdict": "ERROR", "reasons": reasons, "transcript": transcript, "attempts": max_attempts, "infra": True}


# ───────────────────────── 门禁 / 状态 / 合入 / 部署 ─────────────────────────


def run_card_gates(card_file: Path) -> list[str]:
    """解析卡「## 门禁」块 `测试：<cmd>` 行并逐个执行；返回失败列表（空=全过）。"""
    if not card_file.is_file():
        return ["卡文件缺失，无法跑门禁"]
    text = card_file.read_text(encoding="utf-8")
    m = re.search(r"##\s*门禁\s*(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not m:
        return []
    cmds = re.findall(r"^\s*[*-]\s*(?:测试|门禁)\s*[:：]\s*(.+)$", m.group(1), re.M)
    failures: list[str] = []
    for i, cmd in enumerate(cmds, 1):
        logger.info("跑门禁 %d: %s", i, cmd)
        try:
            proc = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                failures.append(f"门禁{i} 失败(rc={proc.returncode}): {cmd}\n{(proc.stdout + proc.stderr)[-400:]}")
        except subprocess.TimeoutExpired:
            failures.append(f"门禁{i} 超时: {cmd}")
    return failures


def set_card_state(card_file: Path, state_text: str, verdict: str, reasons: str) -> bool:
    """改写卡头「状态：X」+ 追加机审区结论（经 CardStateStore 统一门面，幂等）。"""
    if not card_file.is_file():
        return False
    try:
        store = _phase2_store(card_file)
        text = card_file.read_text(encoding="utf-8")
        target = _base_state_of(text)
        audit_section = _audit_section(verdict, reasons)
        # 真实 Git 仓走受保护提交+push；无 .git 的测试夹具只验证原子落盘
        push = store.repo_root.joinpath(".git").exists()

        def _mutator(current_text: str) -> str:
            new_text, n = _STATE_RE.subn(rf"\g<1>{state_text}", current_text, count=1)
            if n == 0:
                raise ValueError("卡头缺少状态字段，无法写入状态")
            if "## 机审区" in new_text:
                return re.sub(
                    r"## 机审区\s*\n.*?(?=\n## |\Z)",
                    audit_section.rstrip("\n") + "\n",
                    new_text,
                    flags=re.S,
                    count=1,
                )
            return new_text.rstrip("\n") + "\n\n" + audit_section.rstrip("\n") + "\n"

        store.transition(
            card_file,
            target=state_text,
            expected_state=target,
            expected_version=_version_of(text),
            expected_commit=None,
            actor="phase2",
            reason=f"机审{'通过' if verdict == 'PASS' else '不通过'}: {reasons[:120]}",
            mutator=_mutator,
            push=push,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("set_card_state 统一门面失败（保留原文）: %s (%s)", card_file, exc)
        return False
    return True


def _phase2_store(card_file: Path | None = None) -> CardStateStore:
    """按卡所在仓库构造统一 store（进程级缓存）。"""
    dispatch_dir = os.environ.get("DISPATCH_DIR") or "docs/dispatch"
    from server.git_sync import resolve_repo_root

    repo_root = resolve_repo_root(card_file.parent if card_file is not None else dispatch_dir)
    key = str(repo_root.resolve())
    cached = _PHASE2_STORE_CACHE.get(key)
    if cached is not None:
        return cached
    store = CardStateStore(
        repo_root,
        dispatch_dir=dispatch_dir if (repo_root / dispatch_dir).is_dir() else repo_root,
        data_dir=os.environ.get("DATA_DIR") or (repo_root / ".ccc-state"),
    )
    _PHASE2_STORE_CACHE[key] = store
    return store








def _base_state_of(text: str) -> str:
    from server.board.models import base_state

    m = re.search(r"状态\s*[:：]\s*([^\n·]+?)(?=\s*·|\s*$)", text)
    return base_state(m.group(1).strip()) if m else ""


def _version_of(text: str) -> int:
    m = re.search(r"状态版本\s*[:：]\s*(\d+)", text)
    return int(m.group(1)) if m else 0


def _audit_section(verdict: str, reasons: str) -> str:
    verdict_cn = "通过" if verdict == "PASS" else "不通过"
    return (
        "## 机审区\n\n"
        "- 审核方：Claude Code（phase2 自动）\n"
        f"- 结论：{verdict_cn}\n"
        f"- 理由：{reasons}\n"
    )


def _conflict_strikes(card_id: str, cfg: dict, *, increment: bool = False) -> int:
    """读取（或递增）同卡 merge 冲突 strikes（复用 sidecar 语义）。

    与批二 infra strikes 同源：冲突连犯 ≥2 次 → C-5 熔断打回，不再重审烧 token。
    """
    from server.engine.runtime_state import read_card_state, write_card_state

    log_dir = _audit_log_dir(cfg)
    current = read_card_state(log_dir).get(str(card_id), {})
    strikes = int(current.get("conflict_strikes") or 0)
    if increment:
        strikes += 1
        write_card_state(log_dir, str(card_id), conflict_strikes=strikes)
    return strikes


def merge_branch_to_main(branch: str, *, card_id: str = "", cfg: dict | None = None) -> tuple[bool, str]:
    """fetch + 合入 origin/<branch> 到本地 main + 立即补推（C-7）。

    失败自动回滚回原分支。冲突 → 递增 conflict strikes；≥2 → 返回带
    `CONFLICT_CIRCUIT_OPEN` 的失败原因（调用方据此打回），避免无界重审循环。
    push 失败：merge 已落本地 main，返回失败原因含 `PUSH_NEEDS_RETRY`，
    调用方保留卡「已回写」+infra 冷却，下轮补推（杜绝 CLOSED→CLOSED 死锁）。
    """
    r = git(["fetch", "origin", branch])
    if r.returncode != 0:
        return False, f"fetch origin/{branch} 失败: {r.stderr.strip()[:200]}"
    prev = _current_branch()
    r = git(["checkout", "main"])
    if r.returncode != 0:
        return False, f"checkout main 失败: {r.stderr.strip()[:200]}"
    r = git(["merge", "--no-edit", f"origin/{branch}"])
    if r.returncode != 0:
        merge_err = r.stderr.strip()[:200] or r.stdout.strip()[:200]
        conflicts = _conflict_files()
        git(["merge", "--abort"])
        git(["checkout", prev])
        strikes = _conflict_strikes(card_id, cfg or {}, increment=True) if cfg else 1
        detail = f"merge origin/{branch} 冲突（第 {strikes} 次）: {merge_err}"
        if conflicts:
            detail += f"；冲突文件: {', '.join(conflicts[:8])}"
        if strikes >= 2:
            return False, f"{detail}; CONFLICT_CIRCUIT_OPEN"
        return False, detail
    # C-7：merge 落本地 main 后、状态推进前先补推一次。push 失败保留本地提交，
    # 下轮重试补推（_branch_in_main 对 origin/main 判定 → 不会误判已消费）。
    push = git(["push", "origin", "main"])
    if push.returncode != 0:
        return False, f"merge 已落本地 main，push 失败: {push.stderr.strip()[:200]}; PUSH_NEEDS_RETRY"
    return True, ""


def _conflict_files() -> list[str]:
    """读取 merge 冲突文件名（合并状态下 git status --porcelain 的 UU/AA/DD 行）。"""
    r = git(["status", "--porcelain"])
    out: list[str] = []
    if r.returncode != 0:
        return out
    for ln in (r.stdout or "").splitlines():
        if len(ln) > 2 and ln[:2].strip() == "UU":
            out.append(ln[3:].strip())
    return out


def delete_merged_branch(branch: str) -> tuple[bool, list[str]]:
    """合入收尾：清理执行分支（本地 + 远端）。失败逐条返回明细，禁止静默。

    安全顺序：先确认 origin/<branch> 已并入本地 main（此刻 main 已含合入提交），
    再删远端、后删本地（本地分支另验「无未并入 main 的提交」才删，防丢未推工作）。
    """
    problems: list[str] = []
    if not branch:
        # wrapper 型卡没有代码分支；无分支即无需清理，不视为失败。
        return True, []

    remote_ref = f"origin/{branch}"
    r = git(["rev-parse", "--verify", "--quiet", remote_ref])
    if r.returncode == 0:
        ra = git(["merge-base", "--is-ancestor", remote_ref, "main"])
        if ra.returncode != 0:
            return False, [f"{remote_ref} 未确认并入 main，保守保留"]
        rd = git(["push", "origin", "--delete", branch])
        if rd.returncode != 0:
            problems.append(f"远端分支删除失败: {rd.stderr.strip()[:200]}")
    r = git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"])
    if r.returncode == 0:
        la = git(["merge-base", "--is-ancestor", f"refs/heads/{branch}", "main"])
        if la.returncode != 0:
            problems.append("本地分支含未并入 main 的提交，保守保留")
        else:
            rl = git(["branch", "-d", branch])
            if rl.returncode != 0:
                problems.append(f"本地分支删除失败: {rl.stderr.strip()[:200]}")
    return (not problems), problems


def _clear_rejected_branch_envelope(card: dict) -> tuple[bool, list[str]]:
    """机审判不通过打回时同步清理该卡 codex 分支信封（复用 delete_merged_branch 安全校验）。

    若分支已并入 main（合入后门禁失败场景），按合入收尾规则删除；否则分支信封
    只是打回前的已回写镜像，直接删除（main 已置打回，_list_branch_written_cards 不再重捞）。
    """
    branch = str(card.get("branch") or "")
    if not branch:
        return True, []
    if _branch_in_main(branch):
        return delete_merged_branch(branch)
    # 未合入的残信封：远端指向旧已回写镜像，删除即可，无需本地分支操作。
    r = git(["rev-parse", "--verify", "--quiet", f"origin/{branch}"])
    if r.returncode != 0:
        return True, []
    rd = git(["push", "origin", "--delete", branch])
    if rd.returncode != 0:
        return False, [f"打回信封远端分支删除失败: {rd.stderr.strip()[:200]}"]
    return True, []


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:  # noqa: BLE001
        return False


def _web_host(cfg: dict) -> str:
    """web 探活主机单一同源：WEB_HOST 配置优先（经 plist 注入 192.168.3.116）。

    本地/测试模式（无 WEB_HOST）回落 127.0.0.1，127.0.0.1 语义不破坏。
    WEB_HOST 走 launchd 环境变量（plist EnvironmentVariables）注入，config.env 保持只读。
    """
    env_host = os.environ.get("WEB_HOST", "").strip()
    if env_host:
        return env_host
    return str(cfg.get("WEB_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def deploy_and_probe(cfg: dict) -> tuple[bool, str]:
    """启动 web（若未在听）+ /health 探活；端口响应正常才视为部署完成。"""
    host = _web_host(cfg)
    try:
        port = int(cfg.get("WEB_PORT") or cfg.get("BOARD_PORT") or 7788)
    except (TypeError, ValueError):
        port = 7788
    url = f"http://{host}:{port}/health"
    if not _port_open(host, port):
        env = dict(os.environ)
        env.setdefault("DISPATCH_DIR", cfg.get("DISPATCH_DIR") or "docs/dispatch")
        data_dir = str(cfg.get("DATA_DIR") or "")
        if data_dir:
            env.setdefault("CCC_DATA_DIR", data_dir)
            env.setdefault("DATA_DIR", data_dir)
        log_dir = Path(cfg.get("LOG_DIR") or str(Path.home() / ".ccc" / "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "server.web.server", "--host", host, "--port", str(port)]
        with open(log_dir / "phase2-web.stdout.log", "ab") as out, open(log_dir / "phase2-web.stderr.log", "ab") as err:
            subprocess.Popen(cmd, cwd=_repo_root(), env=env, stdout=out, stderr=err, start_new_session=True)
        logger.info("phase2 已拉起 web: %s", " ".join(cmd))
    deadline = time.time() + _DEFAULT_HEALTH_TIMEOUT
    while time.time() < deadline:
        if _http_ok(url):
            return True, f"web :{port} /health 响应正常"
        time.sleep(2)
    return False, f"web :{port} /health 未就绪（{int(_DEFAULT_HEALTH_TIMEOUT)}s 内无响应）"


# ───────────────────────── 单卡处理 / 批量消费 ─────────────────────────


def process_one(card: dict, cfg: dict, audit_driver: str = "real") -> dict:
    from server.board.audit_ledger import record_action

    card_file = resolve_card_file(card)
    branch = card.get("branch") or ""
    # wrapper 型卡无代码分支；机审通过后直接在主仓走门禁/关闭路径。
    has_merge_branch = bool(branch)
    if not card_file:
        record_action("phase2_alert", card["id"], source="phase2", detail="主仓卡文件缺失，无法消费")
        return {"id": card["id"], "result": "error", "reason": "card file missing"}
    prev_branch = _current_branch()
    try:
        # 已合入但部署失败的重试守卫：分支已在 main → 跳过重复审核，直接门禁+部署。
        # wrapper 型卡无分支信封，按主仓卡与 log_dir 工件执行机审。
        if not has_merge_branch or not _branch_in_main(branch):
            audit = audit_card(card, card_file, branch, cfg, audit_driver)
            if audit["verdict"] == "ERROR":
                if audit.get("infra"):
                    if audit.get("cooldown"):
                        logger.warning("phase2 机审仍在基础设施冷却期，跳过计数: %s", card["id"])
                        return {"id": card["id"], "result": "audit_failed", "reason": audit["reasons"], "attempts": audit["attempts"]}
                    failure_mode = _record_audit_failure(
                        card,
                        card_file,
                        cfg,
                        audit["reasons"],
                        count_strike=not audit.get("transient_probe", False),
                    )
                    if failure_mode == "circuit_open":
                        return {"id": card["id"], "result": "rejected", "reason": audit["reasons"], "attempts": audit["attempts"]}
                    record_action("phase2_audit_fail", card["id"], source="phase2", detail=f"机审基础设施失败（冷却）: {audit['reasons']}")
                else:
                    record_action("phase2_audit_fail", card["id"], source="phase2", detail=f"CC 审核调用失败: {audit['reasons']}")
                logger.error("phase2 CC 审核失败，卡保留「已回写」: %s", card["id"])
                return {"id": card["id"], "result": "audit_failed", "reason": audit["reasons"], "attempts": audit["attempts"]}
            if audit["verdict"] == "REJECT":
                git(["checkout", "main"])
                if resolve_card_file(card) is None:
                    _materialize_card(card)
                card_file = resolve_card_file(card)
                if card_file is None:
                    record_action("phase2_alert", card["id"], source="phase2", detail="无法落打回卡文件")
                    return {"id": card["id"], "result": "error", "reason": "card file missing on reject"}
                if not set_card_state(card_file, f"{_REJECTED}（CC 审核不通过）", "REJECT", audit["reasons"]):
                    record_action(
                        "phase2_alert", card["id"], source="phase2",
                        detail="机审打回落盘失败（保留原文，不覆盖）",
                    )
                    return {"id": card["id"], "result": "error", "reason": "机审打回落盘失败"}
                record_action("phase2_reject", card["id"], source="phase2", detail=f"CC 审核不通过自动打回: {audit['reasons']}")
                cleaned, cleanup_problems = _clear_rejected_branch_envelope(card)
                if not cleaned:
                    record_action(
                        "phase2_alert", card["id"], source="phase2",
                        detail=f"打回信封清理失败: {'; '.join(cleanup_problems)}",
                    )
                    logger.error("phase2 打回信封清理失败（卡已打回，分支保留）: %s %s", card["id"], cleanup_problems)
                _refresh_index(cfg)
                logger.warning("phase2 打回（不阻塞其他卡）: %s", card["id"])
                return {
                    "id": card["id"],
                    "result": "rejected",
                    "reason": audit["reasons"],
                    "branch_cleanup": "ok" if cleaned else "failed",
                }
            # PASS → 有代码分支才合入；wrapper 型卡直接进入主仓门禁。
            if has_merge_branch:
                ok, err = merge_branch_to_main(branch, card_id=str(card["id"]), cfg=cfg)
                if not ok:
                    # C-5：连续 merge 冲突两次熔断打回，不再重新跑 LLM 机审。
                    if "CONFLICT_CIRCUIT_OPEN" in err:
                        git(["checkout", "main"])
                        card_file = resolve_card_file(card) or card_file
                        if not set_card_state(card_file, f"{_REJECTED}（合入冲突熔断）", "REJECT", err):
                            record_action("phase2_alert", card["id"], source="phase2", detail="冲突熔断打回落盘失败")
                            return {"id": card["id"], "result": "error", "reason": err}
                        record_action("phase2_reject", card["id"], source="phase2", detail=f"连续合入冲突自动打回: {err}")
                        _refresh_index(cfg)
                        return {"id": card["id"], "result": "rejected", "reason": err}
                    # C-7：merge 已落本地但 push 失败，卡保持已回写并进入 infra 冷却，
                    # 下轮先补推/重试，不得推进到已关闭再触发 CLOSED→CLOSED 非法转移。
                    if "PUSH_NEEDS_RETRY" in err:
                        _record_audit_failure(card, card_file, cfg, err, count_strike=False)
                        record_action("phase2_alert", card["id"], source="phase2", detail=f"合入后补推待重试: {err}")
                        return {"id": card["id"], "result": "audit_failed", "reason": err, "infra": True}
                    record_action("phase2_alert", card["id"], source="phase2", detail=f"合入失败: {err}")
                    return {"id": card["id"], "result": "error", "reason": err}
        else:
            logger.info("phase2 分支已在 main（重试部署场景），跳过审核: %s", card["id"])
            git(["checkout", "main"])

        # 合入后卡文件应已在 main 工作区
        card_file = resolve_card_file(card)
        if card_file is None:
            _materialize_card(card)
            card_file = resolve_card_file(card)
        if card_file is None:
            record_action("phase2_alert", card["id"], source="phase2", detail="合入后卡文件缺失")
            return {"id": card["id"], "result": "error", "reason": "card file missing after merge"}

        # 门禁（main 工作区）
        gate_fails = run_card_gates(card_file)
        if gate_fails:
            if not set_card_state(card_file, f"{_REJECTED}（门禁失败）", "REJECT", "；".join(gate_fails)):
                record_action("phase2_alert", card["id"], source="phase2", detail="门禁失败状态落盘失败（保留原文，不覆盖）")
                return {"id": card["id"], "result": "error", "reason": "门禁失败状态落盘失败"}
            record_action("phase2_reject", card["id"], source="phase2", detail=f"门禁失败自动打回: {'; '.join(gate_fails)}")
            _refresh_index(cfg)
            logger.warning("phase2 门禁失败打回: %s", card["id"])
            return {"id": card["id"], "result": "gate_failed", "reason": gate_fails}


        # 部署 + 探活必须先于关闭：探活失败时卡保留「已回写」，下轮可重试。
        ok, detail = deploy_and_probe(cfg)
        if not ok:
            if not set_card_state(card_file, f"{_WRITTEN}（部署失败）", "PASS", f"合入成功但部署未就绪: {detail}"):
                record_action("phase2_alert", card["id"], source="phase2", detail="部署失败状态落盘失败（保留原文，不覆盖）")
                return {"id": card["id"], "result": "error", "reason": "部署失败状态落盘失败"}
            record_action("phase2_deploy_fail", card["id"], source="phase2", detail=f"部署探活失败: {detail}")
            _refresh_index(cfg)
            logger.error("phase2 部署探活失败（卡保留已回写待重试）: %s %s", card["id"], detail)
            return {"id": card["id"], "result": "deploy_failed", "reason": detail}

        # 探活成功后置已关闭 + 提交 push main（统一门面自带 commit/push）。
        if not set_card_state(card_file, _CLOSED, "PASS", "CC 审核通过，自动合入完成"):
            record_action("phase2_alert", card["id"], source="phase2", detail="合入后状态落盘失败（保留原文，不覆盖）")
            return {"id": card["id"], "result": "error", "reason": "合入后状态落盘失败"}
        record_action("phase2_pass", card["id"], source="phase2", detail=f"CC 审核通过自动合入+部署探活成功: {detail}")
        _refresh_index(cfg)
        # 分支清理（本地+远端，任务四）：失败留痕告警不静默，也不回滚已关闭终态
        cleaned, cleanup_problems = delete_merged_branch(branch)
        if not cleaned:
            record_action(
                "phase2_alert", card["id"], source="phase2",
                detail=f"分支清理失败: {'; '.join(cleanup_problems)}",
            )
            logger.error("phase2 分支清理失败（卡已关闭，分支保留）: %s %s", card["id"], cleanup_problems)
        logger.info("phase2 完成: %s → 已关闭（%s）", card["id"], detail)
        return {"id": card["id"], "result": "closed", "reason": detail, "branch_cleanup": "ok" if cleaned else "failed"}
    finally:
        if _current_branch() != prev_branch:
            git(["checkout", prev_branch])


def worktree_dirty_problems() -> list[str]:
    """工作区前置检查（任务五）：返回未提交的已跟踪文件改动清单（untracked 不算脏）。

    phase2 需 checkout/merge/reset --hard main：脏工作区下 merge 会拒绝（卡每轮 alert
    却永不前进＝静默卡死），门禁失败路径的 reset --hard 会静默吞掉未提交改动（数据丢失）。
    故消费前必须干净；untracked 文件不阻塞 checkout/merge，不列入。
    """
    r = git(["status", "--porcelain"])
    if r.returncode != 0:
        return [f"git status 失败（无法核实工作区状态）: {r.stderr.strip()[:200]}"]
    problems = [ln for ln in r.stdout.splitlines() if ln.strip() and not ln.startswith("??")]
    return problems


def consume_once(dispatch_dir: str | Path, cfg: dict, audit_driver: str = "real") -> dict:
    """消费全部「已回写」卡。逐卡 try/except，互不阻塞。"""
    _ensure_env(cfg)
    stats: dict = {"scanned": 0, "closed": 0, "rejected": 0, "audit_failed": 0, "deploy_failed": 0, "error": 0}
    cards = list_written_cards(dispatch_dir)
    stats["scanned"] = len(cards)
    # 前置加固（任务五）：工作区脏 → 本轮整轮跳过消费。显式 ledger 告警 + error 日志，
    # 禁止静默卡死；卡保留「已回写」，工作区干净后下轮自动恢复消费。
    dirty = worktree_dirty_problems()
    if dirty:
        from server.board.audit_ledger import record_action

        detail = f"工作区脏（未提交改动 {len(dirty)} 项）→ 本轮跳过消费，卡保留已回写待下轮: {'; '.join(dirty[:5])}"
        record_action("phase2_alert", "phase2-runtime", source="phase2", detail=detail)
        logger.error("phase2 前置检查失败: %s", detail)
        stats["skipped_dirty"] = len(cards)
        return stats
    key_map = {"closed": "closed", "rejected": "rejected", "gate_failed": "rejected",
               "audit_failed": "audit_failed", "deploy_failed": "deploy_failed", "error": "error"}
    for card in cards:
        try:
            res = process_one(card, cfg, audit_driver)
            key = key_map.get(res.get("result", "error"), "error")
            stats[key] = stats.get(key, 0) + 1
            logger.info("phase2 处理结果: %s", json.dumps(res, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            stats["error"] += 1
            logger.exception("phase2 处理卡异常: %s", card.get("id"))
    return stats


# ───────────────────────── CLI ─────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CCC Phase2 后半段自动闭环")
    parser.add_argument("--config", required=True, help="config.env 路径")
    parser.add_argument("--once", action="store_true", help="消费一轮后退出")
    parser.add_argument("--daemon", action="store_true", help="常驻轮询消费")
    parser.add_argument("--interval", type=int, default=20, help="daemon 轮询间隔秒")
    parser.add_argument("--audit-driver", default=os.environ.get("PHASE2_AUDIT_DRIVER", "real"),
                        help="审核驱动：real|mock:pass|mock:reject|mock:error（mock 仅测试）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    cfg = load_cfg(args.config)
    dispatch_dir = cfg.get("DISPATCH_DIR") or "docs/dispatch"
    if args.daemon:
        logger.info("phase2 daemon 启动（interval=%ss driver=%s）", args.interval, args.audit_driver)
        while True:
            try:
                stats = consume_once(dispatch_dir, cfg, args.audit_driver)
                logger.info("phase2 scan: %s", json.dumps(stats, ensure_ascii=False))
            except Exception:  # noqa: BLE001
                logger.exception("phase2 scan 异常")
            time.sleep(args.interval)
    stats = consume_once(dispatch_dir, cfg, args.audit_driver)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
