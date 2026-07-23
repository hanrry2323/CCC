#!/usr/bin/env python3
"""CCC Desktop local Agent Sidecar — loop-code on localhost.

Hot path: Desktop → 127.0.0.1:7788 → ClaudeSDKClient → vendor/loop-code/cli → MiniMax
Hub remains for threads sync / transfer / flow SSE (not on the chat hot path).

Security (2026-07-19):
  - /api/chat + /warm require CCC_AGENT_TOKEN (Bearer or X-CCC-Agent-Token)
  - project_path 必须落在 allowlist 根下
  - /health 不暴露完整 cli 路径

Usage:
  CCC_AGENT_PORT=7788 CCC_AGENT_TOKEN=... ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic \\
    .venv-hub/bin/python scripts/ccc-agent-sidecar.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Ensure loop-code before chat_server config resolves CLI
os.environ.setdefault("CCC_EXECUTOR", "loop-code")
os.environ.setdefault(
    "CLAUDE_CONFIG_DIR",
    str(Path.home() / ".ccc" / "loop-code"),
)
# 默认直连 MiniMax；仅当显式设 CCC_AGENT_ROUTER 时走中转
os.environ.setdefault(
    "ANTHROPIC_BASE_URL",
    os.environ.get("CCC_AGENT_ROUTER")
    or os.environ.get("CCC_ANTHROPIC_BASE_URL")
    or "https://api.minimaxi.com/anthropic",
)


def _bootstrap_anthropic_auth_from_file() -> None:
    """从 0600 文件加载 ANTHROPIC_AUTH_TOKEN，避免 launchd plist 落地明文。

    优先序：已有环境变量 > CCC_ANTHROPIC_TOKEN_FILE > ~/.ccc/minimax-api-key
    """
    if (os.environ.get("ANTHROPIC_AUTH_TOKEN") or "").strip():
        return

    raw_path = (
        os.environ.get("CCC_ANTHROPIC_TOKEN_FILE")
        or str(Path.home() / ".ccc" / "minimax-api-key")
    )
    path = Path(raw_path).expanduser()
    if path.is_file():
        try:
            tok = path.read_text(encoding="utf-8").strip()
        except OSError:
            tok = ""
        if tok and tok != "sk-trae-real-token-not-needed":
            os.environ["ANTHROPIC_AUTH_TOKEN"] = tok


_bootstrap_anthropic_auth_from_file()

from _claude_cli import (  # noqa: E402
    ensure_loop_code_config_dir,
    loop_code_sha256_prefix,
    loop_code_version,
    resolve_claude_cli,
)

# Phase1：私有配置家种子（与个人 ~/.claude 切割）；须在 chat_server import 前
ensure_loop_code_config_dir(Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser())

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
import uvicorn  # noqa: E402

from chat_server.services.claude_client import (  # noqa: E402
    resolve_chat_timeouts,
    resolve_model,
    stream_chat,
)
from chat_server.hub_voice import wrap_hub_prompt  # noqa: E402
HOST = os.environ.get("CCC_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CCC_AGENT_PORT", "7788"))
DEFAULT_CWD = os.environ.get("CCC_AGENT_CWD", str(ROOT))
_TURN_LEDGER = Path.home() / "Library" / "Logs" / "CCC" / "agent-sidecar-turns.jsonl"
_TURN_LEDGER_MAX_BYTES = 2_000_000


def _safe_turn_id(value: Any) -> str:
    raw = str(value or "").strip()
    if raw and len(raw) <= 80 and all(ch.isalnum() or ch in "-_." for ch in raw):
        return raw
    return uuid.uuid4().hex


def _slot_key_hash(project_path: str, session_id: str) -> str:
    raw = f"{Path(project_path).expanduser()}::{session_id}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:16]


def _append_turn_ledger(record: dict[str, Any]) -> None:
    """Write bounded metadata-only diagnostics; never record prompts or credentials."""
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        **record,
    }
    try:
        from _jsonl_rotate import append_jsonl

        append_jsonl(
            _TURN_LEDGER,
            row,
            max_bytes=_TURN_LEDGER_MAX_BYTES,
            backup_count=2,
        )
    except Exception:
        # Diagnostics must never break the chat hot path.
        pass


_OUTBOX_STOP: asyncio.Event | None = None
_OUTBOX_TASK: asyncio.Task | None = None


@asynccontextmanager
async def _sidecar_lifespan(_app: FastAPI):
    """常驻冲刷 Desktop transfer-outbox（关 App 也投 Hub）。"""
    global _OUTBOX_STOP, _OUTBOX_TASK
    from chat_server.services.transfer_outbox_flush import flush_loop

    _OUTBOX_STOP = asyncio.Event()
    _OUTBOX_TASK = asyncio.create_task(
        flush_loop(_OUTBOX_STOP), name="ccc-transfer-outbox-flush"
    )
    try:
        yield
    finally:
        if _OUTBOX_STOP is not None:
            _OUTBOX_STOP.set()
        if _OUTBOX_TASK is not None:
            _OUTBOX_TASK.cancel()
            try:
                await _OUTBOX_TASK
            except (asyncio.CancelledError, Exception):
                pass
        _OUTBOX_TASK = None
        _OUTBOX_STOP = None


app = FastAPI(
    title="CCC Agent Sidecar",
    docs_url=None,
    redoc_url=None,
    lifespan=_sidecar_lifespan,
)


# 对话 SPA 在本机 :7788；若 Hub 页跨域打 sidecar，允许内网 Origin
_cors_regex = os.environ.get(
    "CCC_AGENT_CORS_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CCC-Agent-Token"],
)

FRONTEND_DIR = SCRIPTS / "chat_server" / "frontend"


def _load_token_file() -> str:
    p = Path.home() / ".ccc" / "agent-token"
    try:
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _effective_token() -> str:
    return (os.environ.get("CCC_AGENT_TOKEN") or "").strip() or _load_token_file()


def _check_agent_auth(request: Request) -> JSONResponse | None:
    """Require shared secret for mutating/chat endpoints."""
    expected = _effective_token()
    if not expected:
        return JSONResponse(
            {
                "detail": "CCC_AGENT_TOKEN unset — run: bash scripts/install-agent-sidecar-plist.sh --start",
            },
            status_code=503,
        )
    auth = (request.headers.get("authorization") or "").strip()
    got = ""
    if auth.lower().startswith("bearer "):
        got = auth[7:].strip()
    if not got:
        got = (request.headers.get("x-ccc-agent-token") or "").strip()
    if not got or not hmac.compare_digest(got, expected):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return None


def _allowed_roots() -> list[Path]:
    """project_path 白名单根。

    默认 ~/program + CCC 根 + Desktop Support（非整 $HOME）。
    收窄：export CCC_AGENT_ALLOWED_ROOTS=/path1:/path2
    """
    roots: list[Path] = []
    raw = os.environ.get("CCC_AGENT_ALLOWED_ROOTS", "").strip()
    if raw:
        for part in raw.split(":"):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    else:
        home = Path.home()
        roots.extend(
            [
                (home / "program").resolve(),
                Path(DEFAULT_CWD).expanduser().resolve(),
                ROOT.resolve(),
            ]
        )
        # Desktop Application Support sessions cwd sometimes under Library
        roots.append((home / "Library" / "Application Support" / "CCCDesktop").resolve())
    return roots


def _path_allowed(project_path: str) -> bool:
    try:
        cand = Path(project_path).expanduser().resolve()
    except OSError:
        return False
    if not cand.is_dir():
        return False
    for root in _allowed_roots():
        try:
            cand.relative_to(root)
            return True
        except ValueError:
            continue
    return False


@app.get("/health")
async def health():
    cli = resolve_claude_cli(require=False) or ""
    # 最小化暴露：只回 basename，不回完整路径
    cli_name = Path(cli).name if cli else ""
    cfg = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    cfg_mark = ""
    if cfg:
        try:
            cfg_mark = str(Path(cfg).expanduser().resolve())
        except OSError:
            cfg_mark = cfg
        # 验收用：只暴露是否落在 ~/.ccc/loop-code，完整家目录可含用户名
        if ".ccc/loop-code" in cfg_mark.replace("\\", "/"):
            cfg_mark = "~/.ccc/loop-code"
    return {
        "ok": True,
        "product": "CCC Agent Sidecar",
        "agent_runtime": "loop-code" if "loop-code" in cli.replace("\\", "/") else "claude",
        "agent_cli": cli_name,
        "config_dir": cfg_mark or None,
        "loop_code_version": loop_code_version() or None,
        "loop_code_sha256_prefix": loop_code_sha256_prefix() or None,
        "auth_required": bool(_effective_token()),
        "default_cwd": DEFAULT_CWD,
        "shell": "dialogue",
        "hub_base": (os.environ.get("CCC_HUB_URL") or "http://127.0.0.1:17777").rstrip("/"),
        "outbox_flush": True,
        # Desktop 能力契约（不暴露密钥/完整路径）
        "model": (os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CCC_AGENT_MODEL") or "flash").strip(),
        # Desktop Phase17：请求级 model；plist 定上游出口。标签供 UI/运维对照。
        "models": ["flash", "code", "sonnet", "haiku"],
        "model_labels": {
            "flash": "MiniMax-M3",
            "code": "MiniMax · code",
            "sonnet": "MiniMax · sonnet",
            "haiku": "MiniMax · haiku",
        },
        "tool_modes": ["discuss", "engineer"],
        "compact": True,
        "supports_attachments": True,
        "capabilities": {
            "compact": True,
            "attachments": True,
            "model_per_request": True,
            "resume": True,
            "outbox_flush": True,
        },
    }


@app.post("/api/outbox/flush")
async def outbox_flush(request: Request):
    """手动冲刷一次 transfer-outbox（运维/烟测；常驻 loop 已在 lifespan 跑）。"""
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    from chat_server.services.transfer_outbox_flush import flush_once

    summary = await asyncio.to_thread(flush_once)
    return summary


def _workspace_map() -> dict[str, str]:
    out: dict[str, str] = {}
    raw = (os.environ.get("CCC_DESKTOP_WORKSPACE_MAP") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                out.update({str(k): str(v) for k, v in parsed.items()})
        except json.JSONDecodeError:
            pass
    map_file = Path.home() / ".ccc" / "desktop-workspace-map.json"
    if map_file.is_file():
        try:
            data = json.loads(map_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out.update({str(k): str(v) for k, v in data.items()})
        except (json.JSONDecodeError, OSError):
            pass
    return out


@app.get("/api/shell-config")
async def shell_config():
    """对话 SPA 启动配置（无密钥）；Hub base 供 transfer/board 跨机调用。"""
    hub = (os.environ.get("CCC_HUB_URL") or "http://127.0.0.1:17777").rstrip("/")
    return {
        "ok": True,
        "shell": "dialogue",
        "agent_base": "",
        "hub_base": hub,
        "workspace_map": _workspace_map(),
    }


@app.post("/warm")
async def warm(request: Request):
    """Keep-warm：预连 ClaudeSDKClient live slot（真正省掉首条 15–30s 冷启动）。

    body 可选：project_path / session_id / tool_mode / model
    无 project_path 时只检查 cli（兼容旧客户端）。
    """
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    import time

    t0 = time.perf_counter()
    cli = resolve_claude_cli(require=False) or ""
    cli_ok = bool(cli) and Path(cli).exists()
    body: dict = {}
    try:
        raw = await request.json()
        if isinstance(raw, dict):
            body = raw
    except Exception:
        body = {}

    project_path = str(body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "conversation").strip() or "conversation"
    project_id = str(body.get("project") or body.get("project_id") or "").strip()
    from chat_server import config as _agent_cfg

    tool_mode = _agent_cfg.resolve_tool_mode(
        body.get("tool_mode") or body.get("toolMode") or "discuss",
        project_id=project_id,
    )
    model = str(body.get("model") or "flash").strip().lower() or "flash"
    resume_session_id = str(body.get("claude_session_id") or "").strip() or None

    slot_info: dict = {}
    if project_path and _path_allowed(project_path) and cli_ok:
        from chat_server.services.claude_session import session_manager

        try:
            slot_info = await session_manager.warm(
                project_path,
                session_id,
                model=model,
                resume_session_id=resume_session_id,
                tool_mode=tool_mode,
            )
        except Exception as exc:
            slot_info = {"ok": False, "error": str(exc), "connected": False}

    ms = int((time.perf_counter() - t0) * 1000)
    ok = cli_ok and (not project_path or bool(slot_info.get("ok")))
    return {
        "ok": ok,
        "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "ttfb_ms": ms,
        "agent_cli": Path(cli).name if cli else "",
        "slot": slot_info or None,
    }


@app.post("/api/session/drop")
async def session_drop(request: Request):
    """丢弃 ClaudeSDKClient live slot（取消生成 / 重置 / 自愈）。

    不删 loop-code 的 claude_session_id 历史，只回收 live 进程与锁。
    body.reason 写入日志（cancel | user-reset | heal | …）。
    """
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    body = await request.json()
    project_path = (body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "local")
    reason = str(body.get("reason") or "user-reset").strip() or "user-reset"
    if not project_path or not _path_allowed(project_path):
        return JSONResponse(
            {"detail": "project_path required and must be allowed"},
            status_code=400,
        )
    from chat_server.services.claude_session import session_manager, _slot_key

    tool_mode = str(body.get("tool_mode") or "discuss").strip().lower() or "discuss"
    key = _slot_key(project_path, session_id, tool_mode)
    dropped = await session_manager._drop_slot(key, reason=reason)
    # 兼容旧 key（曾含 ::discuss / ::engineer）：一并清掉，防幽灵槽串台
    legacy_dropped = []
    for legacy_mode in ("discuss", "engineer"):
        legacy_key = f"{project_path}::{session_id}::{legacy_mode}"
        if legacy_key == key:
            continue
        if await session_manager._drop_slot(legacy_key, reason=f"{reason}-legacy"):
            legacy_dropped.append(legacy_key)
    return {
        "ok": True,
        "dropped": bool(dropped) or bool(legacy_dropped),
        "key": key,
        "reason": reason,
        "legacy_dropped": legacy_dropped,
    }


@app.post("/api/session/compact")
async def session_compact(request: Request):
    """压缩 agent session：drop slot + 存摘要待下次 query 注入。"""
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied
    body = await request.json()
    project_path = (body.get("project_path") or "").strip()
    session_id = str(body.get("session_id") or "local")
    summary = body.get("summary")
    tool_mode = str(body.get("tool_mode") or "discuss").strip().lower() or "discuss"
    model = str(body.get("model") or "flash").strip().lower() or "flash"
    if not project_path or not _path_allowed(project_path):
        return JSONResponse(
            {"detail": "project_path required and must be allowed"},
            status_code=400,
        )
    from chat_server.services.claude_session import session_manager

    used = await session_manager.compact_session(
        project_path=project_path,
        hub_session_id=session_id,
        summary=summary,
        tool_mode=tool_mode,
        model=model,
    )
    return {"ok": True, "summary": used, "session_id": session_id}


_LIVE_BOARD_RE = re.compile(
    r"看板|在飞|in[_\s-]?progress|planned|正在跑|board|扇出|有没有任务|刷新看板",
    re.I,
)
_LIVE_REPO_RE = re.compile(
    r"读一下|这个文件|目录结构|仓库里|grep|搜代码|树状|tree|git\s*(status|log)|权威仓",
    re.I,
)


def _hub_base() -> str:
    return (
        os.environ.get("CCC_HUB_URL")
        or os.environ.get("CCC_HUB_BASE")
        or "http://127.0.0.1:17777"
    ).rstrip("/")


# 透镜 board + L1 digest：短缓存，避免每轮双 HTTP 串行打满隧道
_HUB_CTX_TTL_S = 20.0
_hub_board_cache: dict[str, tuple[float, tuple[bool, str]]] = {}
_hub_mind_cache: dict[str, tuple[float, tuple[bool, str]]] = {}


def _hub_auth_headers() -> dict[str, str]:
    """与 ccc-hub-lens 同一套 Hub Basic 默认（ccc:ccc）。"""
    import base64

    explicit = (os.environ.get("CCC_HUB_AUTH") or "").strip()
    if explicit:
        auth = explicit
    else:
        user = (os.environ.get("CCC_CHAT_USER") or "ccc").strip() or "ccc"
        passwd = (os.environ.get("CCC_CHAT_PASS") or "ccc").strip() or "ccc"
        auth = f"{user}:{passwd}"
    token = base64.b64encode(auth.encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _fetch_hub_lens_board(project_id: str) -> tuple[bool, str]:
    """Return (ok, text). On failure text explains not to invent."""
    import time
    import urllib.request

    now = time.monotonic()
    hit = _hub_board_cache.get(project_id)
    if hit and now - hit[0] < _HUB_CTX_TTL_S:
        return hit[1]

    url = f"{_hub_base()}/api/desktop/lens/{project_id}/board"
    try:
        req = urllib.request.Request(url, method="GET", headers=_hub_auth_headers())
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        from chat_server.services.hub_lens import format_board_for_prompt

        out = (True, format_board_for_prompt(data))
    except Exception as exc:
        out = (
            False,
            "【Hub live board 不可达】"
            f"project={project_id} err={type(exc).__name__}: {exc}\n"
            "禁止根据会话记忆编造看板/在飞；可说明不可达，并引用更早对齐基线的 as_of（若有）。",
        )
    _hub_board_cache[project_id] = (now, out)
    return out


def _fetch_hub_mind_digest(project_id: str) -> tuple[bool, str]:
    """Return (ok, digest_or_error_block)."""
    import time
    import urllib.request

    pid = (project_id or "").strip()
    if not pid:
        return False, ""
    now = time.monotonic()
    hit = _hub_mind_cache.get(pid)
    if hit and now - hit[0] < _HUB_CTX_TTL_S:
        return hit[1]

    url = f"{_hub_base()}/api/desktop/mind/{pid}/digest"
    try:
        req = urllib.request.Request(url, method="GET", headers=_hub_auth_headers())
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        digest = str((data or {}).get("digest") or "").strip()
        if digest:
            out = (True, digest)
        else:
            out = (
                False,
                "【项目心智 L1】digest 为空；进度以 live board / 透镜为准，禁止瞎编。",
            )
    except Exception as exc:
        out = (
            False,
            "【项目心智 L1 不可达】"
            f"project={pid} err={type(exc).__name__}: {exc}\n"
            "禁止根据会话记忆编造在飞/进度；可说明不可达，并引用对齐基线 as_of（若有）。",
        )
    _hub_mind_cache[pid] = (now, out)
    return out


def _lens_context_for_turn(project_id: str, user_text: str) -> str:
    """Inject Hub lens discipline for discuss/Plan turns（常驻，不限 board 关键词）。"""
    pid = (project_id or "").strip()
    if not pid or pid == "ccc":
        # 平台仓以本机为准；仍可提示勿 ssh
        return (
            "【平台仓 ccc · Plan】本机 CCC 可 Read/git；"
            "业务仓事实仍须 Hub 透镜，禁止 ssh mac2017。"
        )
    lens_cli = (
        f"python3 {SCRIPTS / 'ccc-hub-lens.py'} "
        f"board|locate|grep|tree|file|git|repair {pid} …"
    )
    mind_cli = f"python3 {SCRIPTS / 'ccc-mind-update.py'} {pid} --constraint '…'"
    repair_cli = (
        f"python3 {SCRIPTS / 'ccc-hub-lens.py'} repair {pid} "
        "clear_blockers|status|archive|purge_flow|reopen"
    )
    parts = [
        f"【Hub 透镜+板务 · Plan · project_id={pid}】",
        f"业务权威在 2017；探查用：{lens_cli}",
        f"板堵/残卡：{repair_cli}（禁止默认投卫生 epic）",
        f"决策脑写入（可选）：{mind_cli}",
        "禁止 ssh / 本机业务路径 Read/git。优先透镜，勿假装有第二树。",
        "扫风险/定稿：board → locate（或 grep）定点收窄 → file 核实 1～3 个相对路径；禁止只读文档交差。",
        "续查只用相对 path；禁止写死盘符、禁止把绝对路径抄回本机 Read。",
        "Hub 经本机隧道 :17777；勿改指 LAN :7777。",
    ]
    # board + mind 并行，缩短每轮首包前等待
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_board = pool.submit(_fetch_hub_lens_board, pid)
        fut_mind = pool.submit(_fetch_hub_mind_digest, pid)
        _ok, block = fut_board.result()
        _mok, mblock = fut_mind.result()
    parts.append(block)
    if mblock:
        parts.append(mblock)
    text = user_text or ""
    if _LIVE_REPO_RE.search(text) or re.search(
        r"(扫风险|定稿|核实|审查|locate|实现|代码)", text, re.I
    ):
        parts.append(
            "本轮需代码核实：先 Bash `ccc-hub-lens.py locate` 再 `file`；勿凭记忆编路径。"
        )
    if re.search(r"(记住|记下来|写入心智|约束是|我们约定)", text):
        parts.append(
            f"若用户要求沉淀决策：Bash `{mind_cli}` 写 L1b；禁止 invent 投 backlog。"
        )
    if re.search(r"对齐(项目)?基线|任务：对齐项目基线", text):
        parts.append(
            "【对齐基线 · 强制】深对齐可选、非硬门槛；作答前必须 Bash 跑 "
            f"`ccc-hub-lens.py board {pid}` 与 `ccc-hub-lens.py git {pid}`；"
            "若 ready=false / abnormal / failed 残卡：先 "
            f"`ccc-hub-lens.py repair {pid} clear_blockers`（或 status→archive），"
            "禁止默认逼用户投卫生 epic；禁止零工具只复述注入快照。"
        )
    # 定稿 / 转任务 / 看仓况：不依赖用户点「对齐基线」，强制 live 核实；板堵优先 repair
    if re.search(
        r"(下一步|看仓况|规划下一步|最佳下一步|帮我规划|定稿|ccc-transfer|转任务契约|转任务)",
        text,
        re.I,
    ):
        parts.append(
            "【定稿/转任务 · 强制核实】作答前必须 Bash 跑 "
            f"`ccc-hub-lens.py board {pid}` 与 `ccc-hub-lens.py git {pid}`；"
            "再按目标 locate/file 定点 1～3 路径。"
            "内化 ready_for_task / inflight / dirty_kind；"
            "ready=false 或 inflight>0 → 先 "
            f"`ccc-hub-lens.py repair {pid} clear_blockers` 板务，"
            "禁止默认投卫生 epic；仅业务脏/真在飞冲突时禁新产品 epic（人可 override）。"
            "digest/STATUS 勾选不作终局；脚本+报告已在仅文档未勾 → S/同步，勿 stamp 重开。"
            "定稿后二级卡仅 title/human_note 可改，方案字段已锁。"
        )
    return "\n".join(parts)


@app.post("/api/chat")
async def chat(request: Request):
    denied = _check_agent_auth(request)
    if denied is not None:
        return denied

    body = await request.json()
    session_id = str(body.get("session_id") or body.get("thread_id") or "local")
    turn_id = _safe_turn_id(body.get("turn_id"))
    model = resolve_model(body.get("model"))
    project_path = (
        (body.get("project_path") or "").strip()
        or DEFAULT_CWD
    )
    if not _path_allowed(project_path):
        return JSONResponse(
            {
                "detail": (
                    f"project_path not allowed: {project_path}. "
                    "Must be under CCC_AGENT_ALLOWED_ROOTS (default ~/program)."
                )
            },
            status_code=403,
        )

    # 优先使用 prompt 字段（Desktop 发来的最后一条 user message content）
    # 避免解析完整 messages 数组只为取最后一行
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        # 兼容旧版 Desktop：回退到 messages 解析
        messages = body.get("messages") or []
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return JSONResponse({"detail": "messages required"}, status_code=400)
        prompt = (user_msgs[-1].get("content") or "").strip()
    if not prompt:
        return JSONResponse({"detail": "prompt required"}, status_code=400)
    # 防恶意超大 prompt 撑爆内存 / 下游 OOM
    _max_prompt = int(os.environ.get("CCC_AGENT_MAX_PROMPT_CHARS", "200000"))
    if len(prompt) > _max_prompt:
        return JSONResponse(
            {"detail": f"prompt too long (max {_max_prompt} chars)"},
            status_code=413,
        )

    from chat_server import config as _agent_cfg
    from chat_server.hub_voice import resolve_prompt_mode as _resolve_prompt_mode

    project_id = (
        str(body.get("project") or body.get("project_id") or body.get("projectId") or "")
        .strip()
    )
    prompt_mode_raw = str(body.get("prompt_mode") or body.get("promptMode") or "").strip()
    # 用用户原文判定 light/full（wrap 后会很长，不能再按长度猜）
    prompt_mode = _resolve_prompt_mode(prompt, requested=prompt_mode_raw or None)
    user_text_for_tools = prompt
    prompt = wrap_hub_prompt(prompt, mode=prompt_mode)

    tool_mode = _agent_cfg.resolve_tool_mode(
        body.get("tool_mode") or body.get("toolMode"),
        user_text=user_text_for_tools,
        project_id=project_id,
    )
    # discuss：保留联网工具能力，但注入纪律，降低「首轮就 WebFetch 挂死」概率
    if tool_mode == "discuss":
        disc = (_agent_cfg.DISCUSS_TOOL_DISCIPLINE or "").strip()
        if disc and disc not in prompt[:500]:
            prompt = f"{disc}\n---\n{prompt}"
        # 业务仓：注入 Hub 只读透镜纪律 + 看板问句自动附带 live board
        lens_block = _lens_context_for_turn(project_id, user_text_for_tools)
        if lens_block:
            prompt = f"{lens_block}\n---\n{prompt}"
    idle_s, max_s = resolve_chat_timeouts(body.get("timeout"))
    client_gone = {"v": False}
    turn_started = time.perf_counter()
    slot_hash = _slot_key_hash(project_path, session_id)

    async def _watch():
        try:
            while not client_gone["v"]:
                if await request.is_disconnected():
                    client_gone["v"] = True
                    return
                await asyncio.sleep(0.35)
        except asyncio.CancelledError:
            return

    async def generate():
        watch = asyncio.create_task(_watch(), name="ccc-agent-disconnect")
        event_counts: dict[str, int] = {}
        final_code = ""
        final_partial = False
        try:
            async for event in stream_chat(
                prompt,
                project_path,
                lambda: client_gone["v"],
                timeout=body.get("timeout"),
                model=model,
                resume_session_id=body.get("claude_session_id"),
                idle_timeout=idle_s,
                max_timeout=max_s,
                hub_session_id=session_id,
                tool_mode=tool_mode,
                prompt_mode=prompt_mode,
                user_text_for_tools=user_text_for_tools,
            ):
                evt = str(event.get("type") or "message")
                event_counts[evt] = event_counts.get(evt, 0) + 1
                event["turn_id"] = turn_id
                if evt == "error":
                    final_code = str(event.get("code") or "stream_error")
                if evt == "ping":
                    yield f": ping {event.get('ts', '')}\n\n"
                    yield f"data: {json.dumps(event)}\n\n"
                    continue
                if evt == "done":
                    partial = bool(event.get("partial")) or client_gone["v"]
                    final_partial = partial
                    payload = {
                        "type": "done",
                        "session_id": session_id,
                        "claude_session_id": event.get("claude_session_id") or "",
                        "partial": partial,
                        "via": "local-agent",
                        "turn_id": turn_id,
                        "metrics": {
                            "duration_ms": int((time.perf_counter() - turn_started) * 1000),
                            "events": event_counts,
                        },
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            client_gone["v"] = True
            final_code = final_code or "client_disconnect"
            final_partial = True
            raise
        except Exception as exc:
            final_code = final_code or "sidecar_exception"
            final_partial = True
            _append_turn_ledger(
                {
                    "event": "turn_exception",
                    "turn_id": turn_id,
                    "session_id": session_id,
                    "slot_key_hash": slot_hash,
                    "code": final_code,
                    "error_type": type(exc).__name__,
                    "duration_ms": int((time.perf_counter() - turn_started) * 1000),
                    "events": event_counts,
                }
            )
            raise
        finally:
            _append_turn_ledger(
                {
                    "event": "turn_end",
                    "turn_id": turn_id,
                    "session_id": session_id,
                    "slot_key_hash": slot_hash,
                    "code": final_code,
                    "partial": final_partial or client_gone["v"],
                    "client_gone": client_gone["v"],
                    "duration_ms": int((time.perf_counter() - turn_started) * 1000),
                    "events": event_counts,
                }
            )
            watch.cancel()
            try:
                await watch
            except (asyncio.CancelledError, Exception):
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-CCC-Agent": "local-sidecar",
        },
    )


def main() -> None:
    cfg = ensure_loop_code_config_dir(
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".ccc" / "loop-code")).expanduser()
    )
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
    cli = resolve_claude_cli(require=True)
    tok = _effective_token()
    if not tok:
        # 启动时自动生成，避免未装 plist 时裸奔
        tok = secrets.token_hex(32)
        token_path = Path.home() / ".ccc" / "agent-token"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        # 原子创建 + 0600，避免 write_text 后再 chmod 的权限窗口
        fd = os.open(
            str(token_path),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            os.write(fd, (tok + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.environ["CCC_AGENT_TOKEN"] = tok
        print(f"[ccc-agent] generated token → {token_path}", flush=True)
    # 对话 SPA 静态页（与 Hub 共用 frontend；API 路由已先注册）
    if FRONTEND_DIR.is_dir() and not any(
        getattr(r, "path", None) == "/" for r in app.routes
    ):
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="dialogue-ui")
    print(f"[ccc-agent] cli={cli}", flush=True)
    print(f"[ccc-agent] config_dir={cfg}", flush=True)
    print(f"[ccc-agent] router={os.environ.get('ANTHROPIC_BASE_URL')}", flush=True)
    print(f"[ccc-agent] auth=required listen=http://{HOST}:{PORT}", flush=True)
    print(f"[ccc-agent] dialogue_ui={FRONTEND_DIR if FRONTEND_DIR.is_dir() else 'missing'}", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
