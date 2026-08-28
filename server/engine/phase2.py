"""server/engine/phase2.py — 后半段自动闭环（rebuild/phase1 · Phase 1）

链路：卡「已回写」 → 引擎自动触发（server.engine.main.run_loop 每轮调用 /
      phase2 --daemon 兜底轮询） → Claude Code 审核 → 合入 → 提交 → 部署 → 探活 → 终态。

规则（老板定稿架构 · 后半段）：
- 审核 = 调用 Claude Code（claude -p）；调用失败重试 >= 3 次退避；耗尽 → ledger 告警 +
  卡保留「已回写」（禁止无声丢卡）。
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

logger = logging.getLogger("ccc.engine.phase2")

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
_DEFAULT_AUDIT_TIMEOUT = 600
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


def _branch_in_main(branch: str) -> bool:
    r = git(["merge-base", "--is-ancestor", f"origin/{branch}", "main"])
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
        }
    for bc in _list_branch_written_cards():
        cards.setdefault(bc["id"], bc)
    return list(cards.values())


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
                if mhdr is not None and base_state(mhdr.state) == _CLOSED:
                    continue  # main 已关闭 → 已消费
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
                }
            )
    return cards


def resolve_card_file(card: dict) -> Path | None:
    p = Path(card.get("path") or card.get("path_rel") or "")
    if p and p.is_file():
        return p
    return None


def _materialize_card(card: dict) -> None:
    """分支卡落工作区（打回/门禁需在 main 工作区改卡）。"""
    branch = card.get("branch", "")
    rel = card.get("path_rel", "")
    if not branch or not rel:
        return
    show = git(["show", f"origin/{branch}:{rel}"])
    if show.returncode != 0:
        return
    target = _repo_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(show.stdout, encoding="utf-8")


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


def _run_claude(claude_bin: str, prompt: str, timeout: int) -> tuple[int, str, str]:
    cmd = [claude_bin, "-p", prompt, "--output-format", "text"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "claude 超时"
    except Exception as exc:  # noqa: BLE001
        return 127, "", f"claude 调用异常: {exc}"


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

    claude_bin = cfg.get("CCC_BRAIN_CLAUDE_BIN") or os.environ.get("CLAUDE_BIN") or "claude"
    try:
        max_attempts = max(1, int(cfg.get("PHASE2_AUDIT_MAX_ATTEMPTS") or _DEFAULT_MAX_ATTEMPTS))
    except (TypeError, ValueError):
        max_attempts = _DEFAULT_MAX_ATTEMPTS
    backoff_base = float(cfg.get("PHASE2_AUDIT_BACKOFF_BASE") or _DEFAULT_BACKOFF_BASE)
    timeout = int(cfg.get("PHASE2_AUDIT_TIMEOUT") or _DEFAULT_AUDIT_TIMEOUT)
    prompt = build_audit_prompt(card, card_file, branch)

    transcript = ""
    reasons = ""
    for attempt in range(1, max_attempts + 1):
        rc, out, err = _run_claude(claude_bin, prompt, timeout)
        transcript = out
        if rc == 0 and out.strip():
            verdict = _claude_verdict_from_output(out)
            if verdict in ("PASS", "REJECT"):
                return {"verdict": verdict, "reasons": _extract_reasons(out, verdict), "transcript": transcript, "attempts": attempt}
            reasons = f"claude 输出无法判定结论（attempt {attempt}）: {out[-300:]}"
        else:
            reasons = f"claude 调用失败 rc={rc}（attempt {attempt}）: {(err or out)[-300:]}"
        logger.warning("CC 审核失败重试 %d/%d: %s", attempt, max_attempts, reasons)
        if attempt < max_attempts:
            time.sleep(backoff_base * (2 ** (attempt - 1)))
    return {"verdict": "ERROR", "reasons": reasons, "transcript": transcript, "attempts": max_attempts}


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
    """改写卡头「状态：X」+ 追加机审区结论（幂等）。"""
    if not card_file.is_file():
        return False
    text = card_file.read_text(encoding="utf-8")
    new_text, n = _STATE_RE.subn(rf"\g<1>{state_text}", text, count=1)
    if n == 0:
        return False
    verdict_cn = "通过" if verdict == "PASS" else "不通过"
    audit_section = (
        "## 机审区\n\n"
        "- 审核方：Claude Code（phase2 自动）\n"
        f"- 结论：{verdict_cn}\n"
        f"- 理由：{reasons}\n"
    )
    if "## 机审区" in new_text:
        new_text = re.sub(r"## 机审区\s*\n.*?(?=\n## |\Z)", audit_section.rstrip("\n") + "\n", new_text, flags=re.S, count=1)
    else:
        new_text = new_text.rstrip("\n") + "\n\n" + audit_section.rstrip("\n") + "\n"
    card_file.write_text(new_text, encoding="utf-8")
    return True


def merge_branch_to_main(branch: str) -> tuple[bool, str]:
    """fetch + 合入 origin/<branch> 到本地 main（不 push）。失败自动回滚回原分支。"""
    r = git(["fetch", "origin", branch])
    if r.returncode != 0:
        return False, f"fetch origin/{branch} 失败: {r.stderr.strip()[:200]}"
    prev = _current_branch()
    r = git(["checkout", "main"])
    if r.returncode != 0:
        return False, f"checkout main 失败: {r.stderr.strip()[:200]}"
    r = git(["merge", "--no-edit", f"origin/{branch}"])
    if r.returncode != 0:
        git(["merge", "--abort"])
        git(["checkout", prev])
        return False, f"merge origin/{branch} 失败: {r.stderr.strip()[:200]}"
    return True, ""


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


def deploy_and_probe(cfg: dict) -> tuple[bool, str]:
    """启动 web（若未在听）+ /health 探活；端口响应正常才视为部署完成。"""
    host = "127.0.0.1"
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
    branch = card.get("branch") or (branch_for(card_file) if card_file else "")
    if not branch:
        record_action("phase2_alert", card["id"], source="phase2", detail="卡分支无法判定，无法消费")
        return {"id": card["id"], "result": "error", "reason": "branch unknown"}
    prev_branch = _current_branch()
    try:
        # 已合入但部署失败的重试守卫：分支已在 main → 跳过重复审核，直接门禁+部署
        if not _branch_in_main(branch):
            audit = audit_card(card, card_file or Path(card.get("path_rel", "card.md")), branch, cfg, audit_driver)
            if audit["verdict"] == "ERROR":
                record_action(
                    "phase2_audit_fail", card["id"], source="phase2",
                    detail=f"CC 审核调用失败（{audit['attempts']} 次重试后仍失败）: {audit['reasons']}",
                )
                logger.error("phase2 CC 审核失败，卡保留「已回写」（不静默丢卡）: %s", card["id"])
                return {"id": card["id"], "result": "audit_failed", "reason": audit["reasons"], "attempts": audit["attempts"]}
            if audit["verdict"] == "REJECT":
                git(["checkout", "main"])
                if resolve_card_file(card) is None:
                    _materialize_card(card)
                card_file = resolve_card_file(card)
                if card_file is None:
                    record_action("phase2_alert", card["id"], source="phase2", detail="无法落打回卡文件")
                    return {"id": card["id"], "result": "error", "reason": "card file missing on reject"}
                set_card_state(card_file, f"{_REJECTED}（CC 审核不通过）", "REJECT", audit["reasons"])
                git(["add", "--", str(card_file)])
                git(["commit", "-m", f"chore(phase2): {card['id']} CC 审核不通过自动打回"])
                git(["push", "origin", "main"])
                record_action("phase2_reject", card["id"], source="phase2", detail=f"CC 审核不通过自动打回: {audit['reasons']}")
                logger.warning("phase2 打回（不阻塞其他卡）: %s", card["id"])
                return {"id": card["id"], "result": "rejected", "reason": audit["reasons"]}
            # PASS → 合入
            ok, err = merge_branch_to_main(branch)
            if not ok:
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
            git(["reset", "--hard", "origin/main"])
            set_card_state(card_file, f"{_REJECTED}（门禁失败）", "REJECT", "；".join(gate_fails))
            git(["add", "--", str(card_file)])
            git(["commit", "-m", f"chore(phase2): {card['id']} 门禁失败自动打回"])
            git(["push", "origin", "main"])
            record_action("phase2_reject", card["id"], source="phase2", detail=f"门禁失败自动打回: {'; '.join(gate_fails)}")
            logger.warning("phase2 门禁失败打回: %s", card["id"])
            return {"id": card["id"], "result": "gate_failed", "reason": gate_fails}

        # 置已关闭 + 提交 push main
        set_card_state(card_file, _CLOSED, "PASS", "CC 审核通过，自动合入完成")
        git(["add", "--", str(card_file)])
        git(["commit", "-m", f"chore(phase2): {card['id']} CC 审核通过自动合入关闭"])
        r = git(["push", "origin", "main"])
        if r.returncode != 0:
            record_action("phase2_alert", card["id"], source="phase2", detail=f"push main 失败: {r.stderr.strip()[:200]}")
            return {"id": card["id"], "result": "error", "reason": f"push main 失败: {r.stderr.strip()[:200]}"}

        # 部署 + 探活
        ok, detail = deploy_and_probe(cfg)
        if ok:
            record_action("phase2_pass", card["id"], source="phase2", detail=f"CC 审核通过自动合入+部署探活成功: {detail}")
            logger.info("phase2 完成: %s → 已关闭（%s）", card["id"], detail)
            return {"id": card["id"], "result": "closed", "reason": detail}
        # 部署未就绪：卡回「已回写（部署失败）」+ 告警，下轮自动重试（不静默）
        set_card_state(card_file, f"{_WRITTEN}（部署失败）", "PASS", f"合入成功但部署未就绪: {detail}")
        git(["add", "--", str(card_file)])
        git(["commit", "-m", f"chore(phase2): {card['id']} 部署未就绪，待重试"])
        git(["push", "origin", "main"])
        record_action("phase2_deploy_fail", card["id"], source="phase2", detail=f"部署探活失败: {detail}")
        logger.error("phase2 部署探活失败（卡保留已回写待重试）: %s %s", card["id"], detail)
        return {"id": card["id"], "result": "deploy_failed", "reason": detail}
    finally:
        if _current_branch() != prev_branch:
            git(["checkout", prev_branch])


def consume_once(dispatch_dir: str | Path, cfg: dict, audit_driver: str = "real") -> dict:
    """消费全部「已回写」卡。逐卡 try/except，互不阻塞。"""
    _ensure_env(cfg)
    stats: dict = {"scanned": 0, "closed": 0, "rejected": 0, "audit_failed": 0, "deploy_failed": 0, "error": 0}
    cards = list_written_cards(dispatch_dir)
    stats["scanned"] = len(cards)
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
