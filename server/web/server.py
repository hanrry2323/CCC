"""server/web/server.py — HTTP API 服务端（零依赖，Python stdlib 实现）。

提供 5 个 GET 接口 + 对话/会话接口 + Bearer token 鉴权。

用法:
    $PYTHON_BIN -m server.web.server --port 9999

    # 使用默认端口（仅测试用）
    $PYTHON_BIN -m server.web.server

API:
    GET  /health              → {"status": "ok"}（无鉴权）
    POST /session             → 账号密码换 token（无鉴权）
    GET  /board/realtime      → 实时视图（需 Bearer token）
    GET  /board/recent        → 7 天回写视图（需 Bearer token）
    GET  /board/by_project    → 按项目分类（需 Bearer token）
    GET  /board/roadmap       → 线路图聚合（需 Bearer token）
    GET  /board/states        → 卡头五态计数 + columns 看板列计数（需 Bearer token）
    GET  /board/ready_for_merge → 已回写且机审通过（可合入批准）
    GET  /plans/list           → 方案列表（需 Bearer token；?project=&status=&q=）
    GET  /plans/detail         → 方案详情（需 Bearer token；?path=...）
    POST /plans/create         → 新建方案（需 Bearer token；{project,title,content,author,tool}）
    POST /plans/update         → 更新方案（需 Bearer token；{path,status?,content?,cards?}）
    POST /plans/convert        → 转任务卡（需 Bearer token；{path}）
    POST /conversation        → 对话（调用 2017 Claude Code 大脑 Agent，需 Bearer token）
    GET  /conversation        → 对话历史（需 Bearer token；T43 支持长轮询增量同步）

流式对话（T41）: POST /conversation 请求体带 ``"stream": true`` → 返回 SSE
      （text/event-stream），逐事件转发 meta / thinking / tool_use / text /
      tool_result / done / error；错误以 ``event: error`` 流式返回（HTTP 200）。
      body 不带 stream 或为 false → 同步 JSON（向后兼容）。

长轮询增量同步（T43）: ``GET /conversation`` 以 ``len(_conversations)`` 作为单调
      seq 光标（append-only 列表）。不带 ``after`` → 返回全量 ``{messages, seq}``
      （向后兼容）；带 ``after=<seq>&timeout=<s>`` → 挂起等待：新消息到达立即返回
      增量 ``{messages:[...新消息], seq:<最新>}``；超时返回 ``{messages:[], seq:<不变>}``；
      客户端断开（连接 readable/EOF）退出等待释放线程。历史写入处与 ``_conv_cond``
      同锁并 ``notify_all()``，保证「看到 seq 必见消息」。服务端为
      ``ThreadingHTTPServer``（并发），长轮询挂起不再阻塞 /health、/board/* 等。

会话维度（T44）: ``POST /conversation`` body 与 ``GET /conversation`` query 均可带
      ``thread_id``：历史按会话分桶（``_thread_conversations``），大脑按会话分锁
      （同会话串行、跨会话可并发，上限 ``CCC_BRAIN_MAX_CONCURRENCY``）；缺省走
      全局历史与全局锁（向后兼容）。body 可带 ``model`` 做档位覆盖（缺省走
      ``CCC_BRAIN_MODEL``）。

鉴权: 默认免登录（T45，``CCC_WEB_AUTH_REQUIRED=0``，单用户局域网直连即用）；
      设置 ``CCC_WEB_AUTH_REQUIRED=1`` 恢复账号密码鉴权（Bearer token 经 POST /session 获取）。
      环境变量: CCC_WEB_USERNAME, CCC_WEB_PASSWORD_HASH, CCC_WEB_TOKEN_TTL。
      长轮询超时默认值: CCC_WEB_LONGPOLL_TIMEOUT（秒，见 server/config/config.example.env）。

对话大脑（T29）: /conversation 调用本机 Claude Code CLI（走 6100 Anthropic 出口），
      携带 CCC 大脑人格 + 历史上下文，返回真实 Agent 输出。配置见 server/web/brain.py：
      CCC_BRAIN_MODEL / CCC_BRAIN_BASE_URL / CCC_BRAIN_AUTH_TOKEN / CCC_BRAIN_TIMEOUT；
      缺配置返回 503，忙返回 503，超时返回 504，失败返回 502（均不落历史）。

流式对话（T41）: POST /conversation 请求体带 ``"stream": true`` → 返回 SSE
      （text/event-stream），逐事件转发 meta / thinking / tool_use / text /
      tool_result / done / error；错误以 ``event: error`` 流式返回（HTTP 200）。
      body 不带 stream 或为 false → 同步 JSON（向后兼容）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import re
import select
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.web.server")

# ── 项目根路径探测 ──
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.board.loader import load_dispatch_cards
from server.board.plans import (
    convert_plan,
    create_plan,
    get_plan,
    list_plans,
    update_plan,
)
from server.board.queries import (
    ready_for_merge,
    states_response,
    view_by_project,
    view_recent,
    view_realtime,
)
from server.board.models import BOARD_COLUMNS, UNKNOWN, BoardItem, base_state, board_column
from server.engine.cluster import (
    check_service_status,
    check_tcp_reachable,
    parse_cluster_services,
    parse_cluster_targets,
)
from server.web.brain import call_brain, stream_brain_events
from server.web import session_store

# ── 默认参数（仅测试用，生产禁止使用） ──
_DEFAULT_PORT = int(os.environ.get("WEB_PORT", "0"))  # 0=随机端口，仅测试用
_DISPATCH_DIR = _PROJECT_ROOT / "docs" / "dispatch"

# ── 鉴权配置（从环境变量读取；支持运行时刷新，测试可覆盖） ──
_AUTH_USERNAME = os.environ.get("CCC_WEB_USERNAME", "")
_AUTH_PASSWORD_HASH = os.environ.get("CCC_WEB_PASSWORD_HASH", "")
_SERVER_SECRET = os.urandom(32).hex()


def _auth_required() -> bool:
    """免登录开关（T45）：``CCC_WEB_AUTH_REQUIRED=1`` 启用账号密码鉴权，默认 0 免登录。

    单用户局域网默认直连即用；恢复登录只改配置（``CCC_WEB_AUTH_REQUIRED=1``），
    不物理删除鉴权代码（安全可回退）。运行时读取，测试可覆盖。
    """
    return os.environ.get("CCC_WEB_AUTH_REQUIRED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _get_token_ttl() -> int:
    """读取 token 有效期（秒），支持运行时环境变量注入。"""
    return int(os.environ.get("CCC_WEB_TOKEN_TTL", "3600"))


def _get_longpoll_timeout() -> int:
    """长轮询默认超时（秒，CCC_WEB_LONGPOLL_TIMEOUT，默认 30，封顶 60）。"""
    try:
        raw = max(0, int(os.environ.get("CCC_WEB_LONGPOLL_TIMEOUT", "30")))
    except ValueError:
        raw = 30
    return min(raw, 60)


def _conv_list_for(thread_id: str) -> list[dict[str, Any]]:
    """取会话维度对话历史（T44）：thread_id 为空 → 全局列表（向后兼容）。"""
    if thread_id:
        return _thread_conversations.setdefault(thread_id, [])
    return _conversations


def _project_of_thread_id(thread_id: str) -> str:
    """从 thread_id 派生项目：``{project}::{suffix}`` 格式取前缀；否则空。"""
    if "::" in thread_id:
        return thread_id.split("::", 1)[0].strip()
    return ""


def _persist_thread_messages(project: str, thread_id: str, messages: list[dict[str, Any]]) -> None:
    """对话落盘（T47 会话持久化）+ 更新会话索引（标题/时间/消息数）。

    消息 JSONL 追加写，索引整文件更新。落盘失败尽力而为，不阻断对话主流程。
    切项目/会话不中断活跃流——落盘是内存历史的旁路。
    """
    session_store.append_messages(project, thread_id, messages)
    session_store.touch_thread(project, thread_id)


def _get_model_tiers() -> list[str]:
    """模型档位列表（CCC_MODEL_TIERS，逗号分隔，默认 flash,code）。"""
    raw = os.environ.get("CCC_MODEL_TIERS", "flash,code")
    return [m.strip() for m in raw.split(",") if m.strip()]


# 内存 token 存储: {token: {"username": str, "expires_at": float}}
_tokens: dict[str, dict[str, Any]] = {}
# 对话历史（内存列表，append-only；len 即单调 seq 光标，T43）
_conversations: list[dict[str, Any]] = []
# 会话维度对话历史（T44：thread_id 分桶；缺省走全局 _conversations）
_thread_conversations: dict[str, list[dict[str, Any]]] = {}
# 长轮询唤醒条件（T43：与历史写入同锁，保证「看到 seq 必见消息」）
_conv_cond = threading.Condition()

# 项目元数据种子文件（T47：真实业务项目来源，替代 /board/summaries 任务卡分组）
_PROJECT_METADATA_PATH = _PROJECT_ROOT / "knowledge" / "seed" / "02-project-metadata.json"
# 会话持久化根目录（T47：DATA_DIR 优先，规避运行面依赖；缺省用项目内 data/）
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
# 会话持久化子目录：DATA_DIR/conversations/<project>/<thread>.jsonl
_CONVERSATIONS_RELDIR = "conversations"


def _conversations_dir() -> Path:
    """会话持久化根目录（session_store 内部亦有 _data_root 逻辑，保持一致）。"""
    raw = os.environ.get("CCC_DATA_DIR", "") or os.environ.get("DATA_DIR", "")
    if raw:
        return Path(raw).expanduser().resolve() / _CONVERSATIONS_RELDIR
    return _DEFAULT_DATA_DIR / _CONVERSATIONS_RELDIR


def _load_persisted_threads() -> None:
    """启动时把磁盘上已持久化的会话历史加载进内存（T47 会话恢复）。

    按项目遍历 DATA_DIR/conversations/<project>/：以 ``_index.json`` 里的
    **真实 thread_id** 为键，其文件名是清洗后的（``::`` 等被替换），故必须用索引
    恢复原 thread_id 注入 _thread_conversations。仅加载尚未在内存的线程。
    无索引的项目目录跳过（无持久化会话）。
    """
    root = _conversations_dir()
    if not root.is_dir():
        return
    for proj_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        index = session_store.load_index(proj_dir.name)
        for tid in index:
            if tid in _thread_conversations:
                continue
            try:
                _thread_conversations[tid] = session_store.load_thread(proj_dir.name, tid)
            except OSError:
                continue


# 启动加载已持久化的会话历史（T47 会话恢复）
_load_persisted_threads()


def _chat_bridge_url() -> str:
    """M1 对话桥地址（配置后 /conversation 与 threads 走代理）。"""
    return _env_or_config("CCC_CHAT_BRIDGE_URL", "").strip()


def _chat_bridge_token() -> str:
    return _env_or_config("CCC_CHAT_BRIDGE_TOKEN", "").strip()


def _ensure_chat_bridge() -> None:
    """M1 对话桥不可达时经 ssh 拉起（nohup 常驻；launchd 下 claude 子进程会挂起）。"""
    url = _chat_bridge_url()
    if not url:
        return
    m = re.match(r"http://([^:/]+):(\d+)", url)
    if not m:
        return
    host, port = m.group(1), int(m.group(2))
    import socket

    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return
    except OSError:
        pass
    remote = (
        f"cd ~/program/CCC && nohup env CCC_CHAT_BRIDGE_PORT={port} "
        f"CCC_CHAT_DATA_DIR=/Users/apple/.ccc-chat "
        f"/opt/homebrew/bin/python3 -m server.web.chat_bridge > /tmp/chat-bridge.log 2>&1 < /dev/null &"
    )
    try:
        subprocess.run(
            ["ssh", "-o", "ConnectTimeout=6", "-o", "BatchMode=yes", f"apple@{host}", remote],
            capture_output=True,
            text=True,
            timeout=12,
        )
        time.sleep(2)
    except Exception:
        logger.exception("chat-bridge 拉起失败")


# ── 免鉴权的路径前缀 ──
# /tasks/running 与 /projects 同组（T53：控制台后台任务进程面板数据源，免登录白名单）
_NO_AUTH_PATHS = frozenset({"/health", "/session", "/config", "/projects", "/tasks/running", "/cards", "/cards/search"})


# ── 静态托管（T23：浏览器直开 7788 看页面；T25：旧对话页 legacy-chat/） ──
# 白名单：仅这些路径免鉴权返回静态文件（页面本身是登录入口）。
_STATIC_WEB_ROOT = _PROJECT_ROOT / "server" / "web"
# 旧对话页根目录（T25：legacy-chat/ 下的文件通过前缀匹配自动托管）
_STATIC_LEGACY_CHAT_ROOT = _STATIC_WEB_ROOT / "legacy-chat"
# 路径 → 磁盘文件相对 web 根的映射（显式白名单，禁止目录穿越）
_STATIC_WHITELIST: dict[str, str] = {
    "/": "legacy-chat/index.html",
    "/index.html": "legacy-chat/index.html",
    "/js/app.js": "legacy-chat/js/app.js",
    "/data/board.js": "data/board.js",
    "/data/cluster.js": "data/cluster.js",
    # T44：favicon 免鉴权返回（否则浏览器自动请求触发 401 噪音）
    "/favicon.ico": "favicon.svg",
    "/favicon.svg": "favicon.svg",
}


def _resolve_static_file(path: str) -> tuple[Path, str] | None:
    """将请求路径解析为磁盘文件 + Content-Type；非白名单或穿越返回 None。

    防穿越策略：
    1. 白名单命中优先（显式映射）；
    2. 白名单未命中时尝试 legacy-chat/ 目录（T25：旧对话页资源）；
    3. resolve() 后必须仍在对应的根目录内；
    4. 必须是普通文件。
    """
    # 去 query + fragment，path 已是 do_GET 处理后的纯 path
    rel = _STATIC_WHITELIST.get(path)
    if rel:
        target = (_STATIC_WEB_ROOT / rel).resolve()
        try:
            target.relative_to(_STATIC_WEB_ROOT.resolve())
        except ValueError:
            return None
        if target.is_file():
            ctype, _ = mimetypes.guess_type(target.name)
            return target, ctype or "application/octet-stream"
        return None
    # 白名单未命中 → 尝试 legacy-chat/ 目录（T25）
    legacy_path = (_STATIC_LEGACY_CHAT_ROOT / path.lstrip("/")).resolve()
    try:
        legacy_path.relative_to(_STATIC_LEGACY_CHAT_ROOT.resolve())
    except ValueError:
        return None
    if legacy_path.is_file():
        ctype, _ = mimetypes.guess_type(legacy_path.name)
        return legacy_path, ctype or "application/octet-stream"
    return None


# ── 看板兼容接口辅助（T20：BoardSnapshot / BoardSummaries / TaskDetail） ──


def _item_to_board_task(item: BoardItem) -> dict[str, Any]:
    """BoardItem → 桌面端 BoardTask 兼容字典。

    字段映射：state→status；card_kind 统一 "work"（任务卡都是 work 卡）；
    parent_id/split_status/note。
    """
    card_kind = "epic" if item.type == "epic" else "work"

    split_status = ""
    if item.type == "epic":
        from server.board.models import base_state

        base = base_state(item.state)
        if base == "已回写" or base == "已关闭":
            split_status = "done"
        elif base == "执行中":
            split_status = "running"
        elif base == "待分派":
            split_status = "pending"
        elif base == "打回":
            split_status = "failed"

    note = ""

    return {
        "id": item.id,
        "title": item.title,
        "card_kind": card_kind,
        "parent_id": item.parent,
        "status": item.state,
        "state": item.state,
        "board_column": board_column(item.state, item.machine_audit_passed),
        "machine_audit_passed": item.machine_audit_passed,
        "note": note,
        "executor": item.executor,
        "split_status": split_status,
    }


def _build_snapshot(items: list[BoardItem], workspace: str = "") -> dict[str, Any]:
    """构造 BoardSnapshot：columns 按看板列（含「机审」）分组；已关闭最多 10 条最近。"""
    filtered = [i for i in items if not workspace or i.project == workspace]
    columns: dict[str, list[dict]] = {col: [] for col in BOARD_COLUMNS}
    for item in filtered:
        col = board_column(item.state, item.machine_audit_passed)
        bucket = col if col in columns else UNKNOWN
        columns.setdefault(bucket, []).append(_item_to_board_task(item))
    # 已关闭：按回写/关闭时间倒序，最多 10 条（避免历史卡淹没看板）
    closed = columns.get("已关闭") or []
    if closed:

        def _closed_key(row: dict) -> str:
            return str(row.get("written_at") or row.get("closed_at") or row.get("dispatched_at") or "")

        closed_sorted = sorted(closed, key=_closed_key, reverse=True)
        columns["已关闭"] = closed_sorted[:10]
    counts = {col: len(columns.get(col, [])) for col in BOARD_COLUMNS}
    return {
        "columns": columns,
        "counts": counts,
        "workspace": workspace or "all",
        "closed_capped": True,
        "closed_limit": 10,
    }


def _parse_task_acceptance(card_id: str) -> str:
    """从任务卡文件解析 `## 验收标准` section 文本（简单文本拼接，未找到返回空串）。"""
    import re

    # 任务卡命名：根目录 T19-xxx.md（旧卡）或 <前缀>/ccc001-xxx.md（新卡 T54 子目录）
    candidates = sorted(_DISPATCH_DIR.glob(f"{card_id}-*.md"))
    if not candidates:
        candidates = sorted(_DISPATCH_DIR.glob(f"*/{card_id}-*.md"))
    if not candidates:
        candidates = sorted(_DISPATCH_DIR.glob(f"*{card_id}*.md"))
    if not candidates:
        return ""
    try:
        text = candidates[0].read_text(encoding="utf-8")
    except OSError:
        return ""
    # 匹配 `## 验收标准...` 到下一个 `## ` 或文件末
    m = re.search(r"^##\s*验收标准[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


# ── 前端只读配置注入（T33：替代前端硬编码 IP/路径） ──
# 白名单字段：仅这些非敏感字段可经 /config 免鉴权返回给前端。
_PUBLIC_CONFIG_KEYS: tuple[str, ...] = (
    "WEB_PORT",
    "BOARD_PORT",
    "ENGINE_PORT",
    "RELAY_PORT",
)


def _build_public_config() -> dict[str, Any]:
    """构造前端可读的非敏感配置子集（替代前端硬编码 IP/路径/端口）。

    仅返回 _PUBLIC_CONFIG_KEYS 白名单字段；密钥/路径/上游地址等敏感字段一律不返回。
    workspace_map 默认空对象（前端不再硬编码本机路径，由用户在设置页填）。
    """
    return {
        "ports": {
            "web": os.environ.get("WEB_PORT", ""),
            "board": os.environ.get("BOARD_PORT", ""),
            "engine": os.environ.get("ENGINE_PORT", ""),
            "relay": os.environ.get("RELAY_PORT", ""),
        },
        # workspace_map 留空：业务仓路径由用户在设置页填，服务端不臆造
        "workspace_map": {},
        # 模型档位（T44：CCC_MODEL_TIERS，非敏感；档位选择器数据源）
        "models": _get_model_tiers(),
        # M1 对话桥（前端直连；空则走本机 /conversation）
        "chat_bridge_url": _chat_bridge_url(),
        "version": "v0.70.0",
    }


# ── 项目数据源（T47：GET /projects 返回真实业务项目，替代任务卡分组） ──


def _extract_workspace_path(raw_path: str) -> str:
    """从项目元数据 path 字段提取纯文件系统路径。

    元数据 path 形如 ``M1 /Users/apple/program/CCC/``、``Mac2017 /Users/fan/.../（SMB: ...）``，
    取首个空格后的路径段，去括号注释/尾部空白。
    """
    s = raw_path.strip()
    if " " in s:
        s = s.split(" ", 1)[1]
    s = s.split("（", 1)[0].strip()
    s = s.split("(", 1)[0].strip()
    return s.rstrip("/")


def _load_project_metadata() -> list[dict[str, Any]]:
    """读取项目元数据种子文件，扁平化为项目列表。

    结构：``priority.ccc_projects``（CCC 体系核心）+ ``projects``（其余业务/旧项目）。
    文件缺失/损坏 → 返回空列表（前端显示空态引导，不 500）。
    """
    try:
        data = json.loads(_PROJECT_METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    priority = data.get("priority", {})
    items = list(priority.get("ccc_projects", [])) + list(data.get("projects", []))
    return items


def _is_taskable_projects() -> set[str]:
    """可下达任务的项目名单（挂 CCC Engine 的业务仓）。

    真值：docs/projects/registry.yaml（taskable=true 且非 forbidden）。
    """
    from server.board.registry import taskable_names

    return set(taskable_names())


def _build_public_projects() -> list[dict[str, Any]]:
    """构造 GET /projects 响应：真实业务项目清单。

    字段：``id/name/kind/workspace_path/is_taskable/prefix``（T47 契约）。
    **注册即上页面**：主体来自 registry.yaml（唯一事实源，prefix/taskable/路径全由 registry 派生，
    新项目注册后无需同步任何种子文件）；种子文件仅补充 registry 未收录的旧项目（只读）。
    本接口不带任何任务卡分组名（INT-120 等只在看板筛选出现，不进入左栏）。
    """
    from server.board.registry import load_projects

    projects: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for p in load_projects():
        if not p.name:
            continue
        seen_names.add(p.name)
        taskable = bool(p.taskable and not p.forbidden)
        projects.append(
            {
                "id": p.name,  # 稳定 id（name 即业务仓稳定标识）
                "name": p.name,
                "kind": "base" if p.prefix == "ccc" else ("business" if taskable else "legacy"),
                "workspace_path": p.path_m1 or p.path_mac2017 or "",
                "is_taskable": taskable,
                "prefix": p.prefix or "",
            }
        )

    # 种子补充：registry 未收录的历史项目只读展示（不标记 taskable）
    prefix_map = {}
    for p in load_projects():
        for key in (p.name, p.id, p.display):
            if key:
                prefix_map[key] = p.prefix
    for item in _load_project_metadata():
        name = str(item.get("name") or "").strip()
        if not name or name in seen_names:
            continue
        projects.append(
            {
                "id": name,
                "name": name,
                "kind": _infer_project_kind(item),
                "workspace_path": _extract_workspace_path(str(item.get("path") or "")),
                "is_taskable": False,
                "prefix": prefix_map.get(name, ""),
            }
        )
    # 固定排序：taskable 业务项目在前，其余按 name
    projects.sort(key=lambda p: (not p["is_taskable"], p["name"].lower()))
    return projects


_ARCH_INDEX_PATH = _PROJECT_ROOT / "server" / "web" / "data" / "arch" / "index.json"

_STATIC_VERSION = ""


def _compute_static_version() -> str:
    """静态资源版本号 = 当前 git commit 短号（部署后自动变，浏览器强制拉新）。"""
    global _STATIC_VERSION
    if _STATIC_VERSION:
        return _STATIC_VERSION
    try:
        r = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        _STATIC_VERSION = r.stdout.strip() or "dev"
    except Exception:
        _STATIC_VERSION = "dev"
    return _STATIC_VERSION


def _load_arch_index() -> dict[str, Any]:
    """构造 GET /board/arch 响应：集群架构图图库（ARCH 体系）。

    读取 ``server/web/data/arch/index.json``；文件缺失/损坏返回空图库，
    不抛 500（图库为渐进式建设，看板不应因缺图崩溃）。
    """
    try:
        data = json.loads(_ARCH_INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "updated_at": None, "gallery": []}
    return data


def _infer_project_kind(item: dict[str, Any]) -> str:
    """由元数据推断项目种类：base（底座）/ business（业务）/ legacy（旧/退役）。"""
    role = str(item.get("role") or "").lower()
    nature = str(item.get("nature") or "").lower()
    name = str(item.get("name") or "").lower()
    last_act = str(item.get("last_activity") or "").lower()
    if (
        "退役" in role
        or "retired" in role
        or "旧" in role
        or "离线" in role
        or last_act == "retired"
        or "unknown" in last_act
    ):
        return "legacy"
    if "底座" in role or "base" in name or name == "ccc":
        return "base"
    return "business"


def _find_task_detail(items: list[BoardItem], task_id: str) -> dict[str, Any] | None:
    """按 id 查找任务卡详情；未找到返回 None。"""
    item = next((i for i in items if i.id == task_id), None)
    if item is None:
        return None
    # P1：打回原因从运行时 state 读（原始 items 无 reason——富化只发生在 _compose_board_items）
    reason = ""
    log_dir = _executor_log_dir()
    if log_dir:
        try:
            from server.engine.runtime_state import read_card_state

            rt = read_card_state(log_dir).get(item.id) or {}
            reason = str(rt.get("reason", ""))
        except Exception:
            pass
    return {
        "id": item.id,
        "title": item.title,
        "card_kind": "epic" if item.type == "epic" else "work",
        "parent_id": item.parent or "",
        "status": item.state,
        "note": "",
        "executor": item.executor,
        "split_status": "",
        "acceptance": _parse_task_acceptance(item.id),
        # P1 修复：详情补打回原因/人审批准（此前前端 taskCardDetail 读 t.reason 恒空）
        "reason": reason or item.reason or "",
        "approval": item.approval or "",
        "phases": [],
        "events": [],
    }


# ── 运维接口辅助（T21：/ops/summary，cluster 采集 + board 派生 severity） ──


_OPS_COLLECT_CACHE: dict[str, Any] = {"key": None, "ts": 0.0, "machines": None, "services": None}
_OPS_COLLECT_TTL = 10.0


def _ops_collect_cached() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """集群采集短缓存（10s TTL）：ops 15s / console 8s 轮询共享，避免重复 TCP 探活。

    缓存 key 含采集相关 env，env 变化（测试/重配）自动失效。
    """
    import time as _t

    cfg_key = (
        os.environ.get("CLUSTER_TARGETS", ""),
        os.environ.get("CLUSTER_PORT_NAMES", ""),
        os.environ.get("CLUSTER_SERVICES", ""),
    )
    now = _t.time()
    cached = _OPS_COLLECT_CACHE
    if cached["key"] == cfg_key and cached["machines"] is not None and now - cached["ts"] < _OPS_COLLECT_TTL:
        return cached["machines"], cached["services"]
    machines = _collect_ops_nodes()
    services = _collect_ops_services()
    cached.update(key=cfg_key, ts=now, machines=machines, services=services)
    return machines, services


def _collect_ops_nodes() -> list[dict[str, Any]]:
    """采集集群节点状态（TCP 可达性），并行探测，返回 OpsMachine 兼容字典列表。

    目标来自 CLUSTER_TARGETS env（逗号分隔 host:port）；空则返回空列表。
    """
    cfg = {"CLUSTER_TARGETS": os.environ.get("CLUSTER_TARGETS", "")}
    targets = parse_cluster_targets(cfg)
    if not targets:
        return []
    # 端口名走 env 映射（CLUSTER_PORT_NAMES=7788:web-server,6100:relay-anthropic），
    # 无配置则用通用名 port-{port}，避免硬编码端口到名称的映射
    port_names_env = os.environ.get("CLUSTER_PORT_NAMES", "")
    port_names: dict[int, str] = {}
    for pair in port_names_env.split(","):
        pair = pair.strip()
        if ":" in pair:
            k, v = pair.split(":", 1)
            try:
                port_names[int(k.strip())] = v.strip()
            except ValueError:
                continue

    def _probe(item: tuple[str, int]) -> dict[str, Any]:
        host, port = item
        ns = check_tcp_reachable(host, port)
        port_name = port_names.get(port, f"port-{port}")
        return {
            "name": port_name,
            "ip": host,
            "role": port_name,
            "reachable": ns.reachable,
            "alive_ports": 1 if ns.reachable else 0,
            "port_count": 1,
        }

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(targets)))) as ex:
        return list(ex.map(_probe, targets))


def _collect_ops_services() -> list[dict[str, Any]]:
    """采集本机服务进程状态（pgrep），返回服务状态字典列表。

    服务清单来自 CLUSTER_SERVICES env（逗号分隔 name:keyword）；零硬编码。
    未配置则返回空列表（运维页显示「服务清单未配置」）。
    """
    cfg = {"CLUSTER_SERVICES": os.environ.get("CLUSTER_SERVICES", "")}
    services_cfg = parse_cluster_services(cfg)
    services: list[dict[str, Any]] = []
    for name, keyword in services_cfg:
        ss = check_service_status(name, keyword)
        services.append(
            {
                "name": name,
                "running": ss.running,
                "pid": ss.pid,
            }
        )
    return services


def _parse_port_map(raw: str) -> dict[int, str]:
    """解析 'port:name,port:name' → {port: name}。"""
    out: dict[int, str] = {}
    for pair in (raw or "").split(","):
        pair = pair.strip()
        if ":" in pair:
            k, v = pair.split(":", 1)
            try:
                out[int(k.strip())] = v.strip()
            except ValueError:
                continue
    return out


_CONFIG_ENV_CACHE: dict[str, Any] = {"ts": 0.0, "cfg": None}


def _env_or_config(key: str, default: str = "") -> str:
    """env 优先，回退读 config.env（支持新键无需改 launchd plist）。"""
    import time as _t

    v = os.environ.get(key, "")
    if v:
        return v
    now = _t.time()
    cached = _CONFIG_ENV_CACHE
    if cached["cfg"] is None or now - cached["ts"] > 5:
        try:
            from server.config.loader import load_config

            cached["cfg"] = load_config(str(_PROJECT_ROOT / "server" / "config" / "config.env"))
        except Exception:
            cached["cfg"] = {}
        cached["ts"] = now
    return str((cached["cfg"] or {}).get(key, default))


def _scan_listening_ports() -> list[dict[str, Any]]:
    """lsof 全量扫描本机 TCP 监听端口（自动发现，零配置）。"""
    try:
        out = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout
    except Exception:
        return []
    ports: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        cmd, pid = parts[0], parts[1]
        addr = parts[8]
        port_s = addr.rsplit(":", 1)[-1]
        if not port_s.isdigit() or int(port_s) <= 0:
            continue
        port = int(port_s)
        if (cmd, port) in seen:
            continue
        seen.add((cmd, port))
        ports.append({"command": cmd, "pid": pid, "port": port})
    return ports


def _build_ports_payload() -> dict[str, Any]:
    """端口探索：监听全量 + 三态分类 + 业务映射 + 快照 diff。"""
    import datetime as _dt
    import json as _json

    listening = _scan_listening_ports()
    known = _parse_port_map(_env_or_config("CLUSTER_PORT_NAMES"))
    business = _parse_port_map(_env_or_config("CLUSTER_BUSINESS_PORTS"))
    all_maps = {**business, **known}
    by_port = {p["port"]: p for p in listening}

    ports: list[dict[str, Any]] = []
    for port in sorted(by_port):
        info = by_port[port]
        name = all_maps.get(port)
        ports.append(
            {
                "port": port,
                "pid": info["pid"],
                "command": info["command"],
                "name": name or "",
                "url": f"http://127.0.0.1:{port}",
                "status": "active_known" if name else "active_unknown",
            }
        )
    for port in sorted(set(all_maps) - set(by_port)):
        ports.append(
            {
                "port": port,
                "pid": None,
                "command": "",
                "name": all_maps[port],
                "url": f"http://127.0.0.1:{port}",
                "status": "registered_stale",
            }
        )

    # 快照 diff：今日 vs 昨日（消失端口 = 历史使用）
    data_dir = Path(_config_value("DATA_DIR", "data")).resolve()
    ports_dir = data_dir / "ports"
    today = _dt.date.today().isoformat()
    new_ports: list[int] = []
    gone_ports: list[int] = []
    try:
        ports_dir.mkdir(parents=True, exist_ok=True)
        prev = None
        for f in sorted(ports_dir.glob("*.json")):
            if f.stem != today:
                try:
                    prev = _json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    prev = None
        now_set = set(by_port)
        if prev is not None:
            prev_set = set(int(x) for x in prev.get("ports", []))
            new_ports = sorted(now_set - prev_set)
            gone_ports = sorted(prev_set - now_set)
        (ports_dir / f"{today}.json").write_text(
            _json.dumps({"date": today, "ports": sorted(now_set)}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass

    return {
        "ports": ports,
        "listening_count": len(listening),
        "scan_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "new_ports": new_ports,
        "gone_ports": gone_ports,
    }


def _build_hp_health() -> dict[str, Any]:
    """HP 知识库节点探活（CLUSTER_HP_TARGET=host:port，未配置返回 configured=false）。"""
    import time as _t

    target = _env_or_config("CLUSTER_HP_TARGET", "").strip()
    if not target:
        return {"configured": False, "reachable": None, "host": "", "port": None, "latency_ms": None, "url": ""}
    host, _, port_s = target.rpartition(":")
    try:
        port = int(port_s)
    except ValueError:
        return {"configured": True, "reachable": None, "host": host, "port": None, "latency_ms": None, "url": target}
    t0 = _t.time()
    ns = check_tcp_reachable(host, port)
    latency = round((_t.time() - t0) * 1000)
    return {
        "configured": True,
        "host": host,
        "port": port,
        "reachable": ns.reachable,
        "latency_ms": latency,
        "url": f"http://{host}:{port}",
    }


_KB_HEALTH_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_KB_HEALTH_TTL = 10.0


def _build_kb_health() -> dict[str, Any]:
    """知识库健康（P4）：ccc-kb 本地索引 + hp-kb 探活&深度状态。10s 缓存。"""
    import time as _t
    now = _t.time()
    if _KB_HEALTH_CACHE["data"] is not None and now - _KB_HEALTH_CACHE["ts"] < _KB_HEALTH_TTL:
        return _KB_HEALTH_CACHE["data"]

    out: dict[str, Any] = {"ccc_kb": {}, "hp_kb": {}}
    # ── ccc-kb（本地索引）──
    try:
        from server.kb import service as kb_service
        from server.kb.indexer import load_mtimes
        idx = str(kb_service.default_index_dir().resolve())
        h = kb_service.health()
        out["ccc_kb"] = {
            "ok": bool(h.get("ok")), "documents": h.get("documents", 0),
            "sections": h.get("sections", {}), "index_dir": idx,
        }
        mtimes = load_mtimes(idx)
        if mtimes:
            newest = max(mtimes.values())
            out["ccc_kb"]["source_newest_mtime"] = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(newest))
            out["ccc_kb"]["lag_days"] = round(max(0.0, (now - newest) / 86400), 1)
    except Exception as e:  # noqa: BLE001
        out["ccc_kb"] = {"ok": False, "error": str(e)}

    # ── hp-kb（TCP 探活 + 深度状态）──
    hp = _build_hp_health()
    out["hp_kb"] = {k: hp.get(k) for k in ("configured", "host", "port", "reachable", "latency_ms", "url")}
    if hp.get("configured") and hp.get("reachable"):
        try:
            from server.kb import hp_client
            st = hp_client.kb_status()
            if st:
                out["hp_kb"]["documents"] = st.get("total_docs")
                out["hp_kb"]["chunks"] = st.get("total_chunks")
                ccc_sync: dict[str, Any] = {}
                for p in st.get("projects", []):
                    if not isinstance(p, dict):
                        continue
                    if p.get("domain") == "ccc" and p.get("project") not in ("core", "docs"):
                        ccc_sync[p.get("project")] = {
                            "docs": p.get("docs"), "chunks": p.get("chunks"),
                            "last_ingest": p.get("last_ingest"),
                        }
                out["hp_kb"]["ccc_sync"] = ccc_sync
        except Exception:  # noqa: BLE001
            out["hp_kb"]["deep"] = None
    _KB_HEALTH_CACHE.update(ts=now, data=out)
    return out


def _build_ops_summary() -> dict[str, Any]:
    """构造 OpsSummary 兼容子集（对齐桌面端可消费字段）。

    数据源：cluster 采集（nodes/services/collected_at）+ board 派生（severity/human_line）。
    字段缺失容错：旧 Hub 大字段（risks/workspaces/daily/...）一律置空/省略，桌面端容错。

    severity 派生规则：
    - 全部节点可达 + 关键服务运行 → green
    - 部分可达或部分服务运行 → amber
    - 全断或采集失败 → red
    """
    import datetime

    machines, services = _ops_collect_cached()
    collected_at = datetime.datetime.now().isoformat(timespec="seconds")

    # down_ports：不可达节点
    down_ports: list[dict[str, Any]] = []
    for m in machines:
        if not m.get("reachable"):
            down_ports.append(
                {
                    "port": 0,  # 节点级，无具体端口
                    "name": m.get("name", ""),
                    "host": m.get("ip", ""),
                }
            )

    # severity 派生
    total = len(machines)
    reachable = sum(1 for m in machines if m.get("reachable"))
    if total == 0:
        # 无采集配置 → amber（需配置，非故障）
        severity = "amber"
        human_line = "运维采集未配置（CLUSTER_TARGETS 为空），请配置后重启服务"
    elif reachable == total:
        severity = "green"
        human_line = f"集群全活（{reachable}/{total} 节点可达）"
    elif reachable == 0:
        severity = "red"
        human_line = f"集群全断（0/{total} 节点可达），请检查"
    else:
        severity = "amber"
        human_line = f"集群部分可达（{reachable}/{total} 节点可达）"

    # 服务运行情况补充到 human_line
    svc_running = sum(1 for s in services if s.get("running"))
    if services:
        human_line += f" · 服务 {svc_running}/{len(services)} 运行"

    # 派生看板计数（abnormal 卡数 → risk 提示）
    try:
        items = _load_board_items()
        abnormal = sum(1 for i in items if base_state(i.state) == "打回")
        if abnormal > 0:
            human_line += f" · {abnormal} 张打回卡"
    except OSError:
        pass

    # Engine 管道静默故障（探活跳过 / git sync）并入运维人话
    pipeline_alerts: list[str] = []
    try:
        from server.engine.pipeline_status import read_pipeline_status

        pipe = read_pipeline_status()
    except Exception:
        pipe = None
    if pipe:
        if pipe.get("git_sync_ok") is False:
            pipeline_alerts.append("git sync 失败")
            if severity == "green":
                severity = "amber"
        ps = int(pipe.get("probe_skips") or 0)
        if ps > 0:
            pipeline_alerts.append(f"探活跳过 {ps}")
            if severity == "green":
                severity = "amber"
        ns = int(pipe.get("none_skips") or 0)
        if ns > 0:
            pipeline_alerts.append(f"未派发绑定 {ns}")
            if severity == "green":
                severity = "amber"
        if pipeline_alerts:
            human_line += " · " + " · ".join(pipeline_alerts)

    return {
        "overview": {
            "machines": machines,
            "services": services,
            "alert_count": len(down_ports) + len(pipeline_alerts),
            "down_ports": down_ports,
            "generated_at": collected_at,
        },
        "severity": severity,
        "human_line": human_line,
        "pipeline": pipe,
        # 旧 Hub 大字段置空，桌面端容错（OpsView 只读区降级显示）
        "risks": None,
        "workspaces": None,
        "daily": None,
        "quality": None,
        "docs": None,
        "kb": None,
        "deploy": None,
        "ports": None,
        "auto": None,
        "resources": None,
        "resources_history": None,
        "logistics": None,
        "control": None,
        "ready_to_dispatch": None,
        "recent_failures": None,
        "abnormal_cards": None,
        "alerts": None,
        "amber_notes": None,
        "domains": None,
        "agent_minds": None,
    }


def _password_hash(password: str) -> str:
    """计算密码的 SHA-256 哈希。"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _generate_token(username: str) -> str:
    """生成 Bearer token（HMAC-SHA256），存入内存。"""
    expires_at = time.time() + _get_token_ttl()
    raw = f"{username}:{expires_at}"
    token = hmac.new(
        _SERVER_SECRET.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    _tokens[token] = {"username": username, "expires_at": expires_at}
    return token


def _validate_token(token: str) -> dict[str, Any] | None:
    """校验 Bearer token：存在且未过期。返回 token 数据或 None。"""
    data = _tokens.get(token)
    if data is None:
        return None
    if time.time() > data["expires_at"]:
        _tokens.pop(token, None)
        return None
    return data


def _clean_expired_tokens():
    """清理过期 token（惰性，每次调用清除全部过期项）。"""
    now = time.time()
    expired = [t for t, d in _tokens.items() if now > d["expires_at"]]
    for t in expired:
        _tokens.pop(t, None)


def _json_response(data: Any, status: int = 200) -> tuple[str, str, bytes]:
    """构建 JSON 响应 (status_line, content_type, body)。"""
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return ("200 OK" if status == 200 else f"{status} Error", "application/json", body)


def _load_board_items(include_archived: bool = False):
    """加载任务卡数据 + 运行时合成（git 真相 + 运行时状态 + 分支信封证据）。"""
    global _BOARD_CACHE
    now = time.time()
    key = _board_cache_key() + ("|archived" if include_archived else "")
    if _BOARD_CACHE is not None and now - _BOARD_CACHE[0] < _BOARD_CACHE_TTL_S and _BOARD_CACHE[1] == key:
        return _BOARD_CACHE[2]

    items = load_dispatch_cards(_DISPATCH_DIR, include_archived=include_archived)
    try:
        composed = _compose_board_items(items)
        _BOARD_CACHE = (now, key, composed)
        return composed
    except Exception:
        logger.exception("看板合成失败，回退 git 真相")
        return items


_BOARD_CACHE_TTL_S = 20.0
_BOARD_CACHE: tuple[float, str, list] | None = None


def _board_cache_key() -> str:
    """看板缓存键：dispatch 目录 + 索引 + 运行时状态文件的 mtime。"""
    parts: list[str] = []
    for p in (_DISPATCH_DIR, _DISPATCH_DIR / "cards.index.jsonl"):
        try:
            parts.append(str(p.stat().st_mtime_ns))
        except OSError:
            pass
    log_dir = _executor_log_dir()
    if log_dir:
        try:
            parts.append(str((log_dir / "state" / "cards.jsonl").stat().st_mtime_ns))
        except OSError:
            pass
    return "|".join(parts)


_CLOSED_AT_CACHE: tuple[float, str, dict[str, str]] | None = None


def _closed_at_map(repo_root, ttl: float = 60.0) -> dict[str, str]:
    """卡路径 → main 合入时间（ISO）。git log 一次取全表，TTL 缓存。"""
    global _CLOSED_AT_CACHE
    now = time.time()
    root_key = str(Path(repo_root).expanduser().resolve())
    if _CLOSED_AT_CACHE is not None and now - _CLOSED_AT_CACHE[0] < ttl and _CLOSED_AT_CACHE[1] == root_key:
        return _CLOSED_AT_CACHE[2]
    out: dict[str, str] = {}
    try:
        res = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "origin/main",
                "--format=%cI",
                "--name-only",
                "--",
                "docs/dispatch",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            current: str | None = None
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                if re.match(r"^\d{4}-\d{2}-\d{2}T", line):
                    current = line
                elif current and line.startswith("docs/dispatch/"):
                    out.setdefault(line, current)
    except Exception:
        pass
    _CLOSED_AT_CACHE = (now, root_key, out)
    return out


_ENRICHED_CACHE: tuple[float, str, list[dict]] | None = None
_ENRICHED_TTL_S = 30.0


_RELAY_USAGE_FILE_DEFAULT = Path("/Users/fan/program/apps/ai-loop-router-ccc/logs/usage.json")
_RELAY_USAGE_API_DEFAULT = "http://127.0.0.1:6100/admin/usage"
_RELAY_STATS_CACHE: tuple[float, str, dict] | None = None
_RELAY_STATS_TTL_S = 2.0
_RELAY_LAST_SNAPSHOT: tuple[float, dict[str, int]] | None = None


def _relay_usage_file() -> Path:
    raw = os.environ.get("CCC_RELAY_USAGE_FILE", "").strip()
    return Path(raw).expanduser() if raw else _RELAY_USAGE_FILE_DEFAULT


def _relay_usage_api() -> str:
    raw = os.environ.get("CCC_RELAY_USAGE_API")
    if raw is None:
        return _RELAY_USAGE_API_DEFAULT
    return raw.strip()  # 显式设空 = 跳过 API，走用量文件


def _relay_counts_from_api(d: dict) -> dict[str, int]:
    """中转站 /admin/usage 实时响应 → pro/flash/code/total 分桶。

    by_tier 的 ``unknown`` = 未标 tier 的 Premium/Claude 模型 → 归 Pro；
    显式 ``pro`` tier 也归 Pro。
    """
    bt = d.get("by_tier") or {}
    return {
        "total": int(d.get("total") or 0),
        "pro": int((bt.get("unknown") or {}).get("n") or 0) + int((bt.get("pro") or {}).get("n") or 0),
        "flash": int((bt.get("flash") or {}).get("n") or 0),
        "code": int((bt.get("code") or {}).get("n") or 0),
    }


def _relay_bucket(model: str) -> str | None:
    """用量记录 model → 分桶（pro / flash / code）；未知模型只计入 total。"""
    m = (model or "").strip().lower()
    if not m:
        return None
    if "flash" in m:
        return "flash"
    if m == "code":
        return "code"
    if "pro" in m or "opus" in m or "sonnet" in m or m.startswith("claude"):
        return "pro"
    return None


def _relay_counts_from_records(records: list, now_ms: int, today_start_ms: int) -> dict[str, int]:
    counts = {"total": 0, "pro": 0, "flash": 0, "code": 0}
    for r in records:
        ts = r.get("timestamp")
        if not isinstance(ts, (int, float)) or ts <= 0:
            continue
        if int(ts) < today_start_ms:
            continue
        counts["total"] += 1
        b = _relay_bucket(r.get("model"))
        if b:
            counts[b] += 1
    return counts


def _compute_relay_stats() -> dict:
    """中转站今日请求 + 近 10s 增量 + 健康（实时 API 优先，文件兜底）。"""
    global _RELAY_STATS_CACHE, _RELAY_LAST_SNAPSHOT
    now = time.time()
    if _RELAY_STATS_CACHE is not None and now - _RELAY_STATS_CACHE[0] < _RELAY_STATS_TTL_S:
        return _RELAY_STATS_CACHE[1]

    now_ms = int(now * 1000)
    healthy = True
    alert = ""
    counts: dict[str, int] | None = None
    error = ""

    api = _relay_usage_api()
    if api:
        try:
            import urllib.error
            import urllib.request

            with urllib.request.urlopen(urllib.request.Request(api, method="GET"), timeout=3) as resp:
                d = json.loads(resp.read().decode("utf-8", errors="replace"))
            counts = _relay_counts_from_api(d)
        except Exception as exc:
            error = f"{exc}"

    if counts is None:
        # 兜底：用量文件（记录级，60s 落盘；仅 API 不可用时用）
        try:
            from datetime import datetime as _dt

            today_start_ms = int(_dt.combine(_dt.now().date(), _dt.min.time()).timestamp() * 1000)
            data = json.loads(_relay_usage_file().read_text(encoding="utf-8", errors="replace"))
            records = data if isinstance(data, list) else []
            counts = _relay_counts_from_records(records, now_ms, today_start_ms)
        except Exception as exc:
            healthy = False
            alert = f"中转站用量获取失败: {exc}"

    if counts is None:
        counts = {"total": 0, "pro": 0, "flash": 0, "code": 0}
        if _RELAY_LAST_SNAPSHOT is not None:
            counts = dict(_RELAY_LAST_SNAPSHOT[1])  # 保留上次数字
    elif error:
        healthy = False
        alert = f"中转站实时接口不可达: {error}"

    deltas = {"total": 0, "pro": 0, "flash": 0, "code": 0}
    if healthy and _RELAY_LAST_SNAPSHOT is not None and now - _RELAY_LAST_SNAPSHOT[0] <= 30:
        for k in counts:
            deltas[k] = max(0, int(counts[k]) - int(_RELAY_LAST_SNAPSHOT[1].get(k) or 0))
    if healthy:
        _RELAY_LAST_SNAPSHOT = (now, dict(counts))

    out = {
        "today": counts,
        "delta_10s": deltas,
        "healthy": healthy,
        "alert": alert or None,
        "ts": now,
    }
    _RELAY_STATS_CACHE = (now, out)
    return out


def _log_activity_key(log_dir) -> str:
    """运行/机审 marker 快照：派发与机审起止才变化，避免活跃期逐轮重算。"""
    if not log_dir:
        return ""
    parts: list[str] = []
    try:
        for pat in ("*.running", "*-audit.running"):
            for p in Path(log_dir).glob(pat):
                parts.append(f"{p.name}:{p.stat().st_mtime_ns}")
    except OSError:
        pass
    return "|".join(sorted(parts))


def _enriched_cards(include_archived: bool = False) -> list[dict]:
    """合成 + 逐卡运行时富化，整表缓存（运行 marker 变化才失效）。"""
    global _ENRICHED_CACHE
    from server.web.exec_metrics import card_wants_runtime, enrich_card_runtime

    key = _board_cache_key() + ("|archived" if include_archived else "") + "|" + _log_activity_key(_executor_log_dir())
    now = time.time()
    if _ENRICHED_CACHE is not None and now - _ENRICHED_CACHE[0] < _ENRICHED_TTL_S and _ENRICHED_CACHE[1] == key:
        return _ENRICHED_CACHE[2]

    cards_list = [i.to_dict() for i in _load_board_items(include_archived=include_archived)]
    cards_list.sort(key=lambda x: x["id"])
    log_dir = _executor_log_dir()
    # 富化收窄：非关闭卡 + 最新 10 张已关闭（看板只展示这 10 张的徽章），
    # 避免每轮对全部历史卡做日志/工作树计算（重建从 ~5s 降到 ~1s）。
    enrich_ids = {c["id"] for c in cards_list if base_state(c.get("state", "")) != "已关闭"}
    recent_closed = sorted(
        [c for c in cards_list if base_state(c.get("state", "")) == "已关闭"],
        key=lambda x: x.get("closed_at") or "",
        reverse=True,
    )[:10]
    enrich_ids.update(c["id"] for c in recent_closed)
    for c in cards_list:
        if c["id"] in enrich_ids and card_wants_runtime(c):
            enrich_card_runtime(
                c,
                log_dir,
                force=False,
            )
    _ENRICHED_CACHE = (now, key, cards_list)
    return cards_list


def _compose_board_items(items):
    """运行时状态覆盖 + 分支机审证据（TTL 缓存）；主树卡文件只读。"""
    from dataclasses import replace

    from server.engine.runtime_state import read_card_state
    from server.web.audit_evidence import branch_card_audit_passed, branch_card_state

    log_dir = _executor_log_dir()
    runtime = read_card_state(log_dir) if log_dir else {}
    path_by_id: dict[str, str] = {}
    try:
        from server.board.loader import load_index_file

        for entry in load_index_file(_DISPATCH_DIR).values():
            if entry.get("id") and entry.get("path"):
                path_by_id[str(entry["id"])] = str(entry["path"])
    except Exception:
        pass
    repo_root = None
    try:
        from server.git_sync import resolve_repo_root

        repo_root = resolve_repo_root(_DISPATCH_DIR)
    except Exception:
        pass

    out = []
    closed_map: dict[str, str] = {}
    if repo_root is not None:
        closed_map = _closed_at_map(repo_root)
    now_ts = time.time()
    for item in items:
        rt = runtime.get(item.id) or {}
        # 运行时状态仅覆盖磁盘为「待分派」「执行中」或「已回写」的卡；一旦卡在磁盘上是已关闭/打回，则不予覆盖
        if base_state(item.state) in ("已关闭", "打回"):
            new_state = item.state
        else:
            new_state = str(rt["state"]) if rt.get("state") else item.state
        # 分支信封状态（2026-08-12 · 与 engine store 同语义）：磁盘 main 镜像未合入前
        # 永远旧值 + sidecar 收单后清除 → 已回写/已关闭/打回终态从远端 codex/<slug> 分支卡读。
        if base_state(new_state) in ("待分派", "执行中") and not rt.get("state"):
            rel = path_by_id.get(item.id)
            if rel and repo_root is not None:
                branch_state = branch_card_state(repo_root, rel, "codex/" + Path(rel).stem.lower())
                if branch_state:
                    new_state = branch_state
        audited = item.machine_audit_passed
        closed_at = item.closed_at
        audit_status = item.audit_status
        if not closed_at and base_state(new_state) == "已关闭":
            rel = path_by_id.get(item.id)
            if rel:
                closed_at = closed_map.get(rel, "")
        if not audited and base_state(new_state) == "已回写":
            # 机审列状态标签：审核中 / 冷却中 / 修复中 / 待审
            if log_dir and _marker_alive_web(log_dir, item.id, audit=True):
                audit_status = "审核中"
            elif _infra_cooldown_active_web(rt, now_ts):
                audit_status = "冷却中"
            elif rt.get("state") in ("待分派", "执行中", "打回"):
                audit_status = "修复中"
            else:
                audit_status = "待审"
            rel = path_by_id.get(item.id)
            if rel and repo_root is not None:
                branch = "codex/" + Path(rel).stem.lower()
                passed = branch_card_audit_passed(repo_root, rel, branch)
                if passed is True:
                    audited = True
        out.append(
            replace(
                item,
                state=new_state,
                machine_audit_passed=audited,
                closed_at=closed_at,
                audit_status=audit_status,
                reason=rt.get("reason", ""),
            )
        )
    return out


def _marker_alive_web(log_dir, card_id: str, *, audit: bool = False) -> bool:
    """``{id}.running`` / ``{id}-audit.running`` 标记含存活 PID → 在途。

    只按文件存在判定会把引擎崩溃/部署后遗留的死标记当成「进行中」，
    污染 /tasks/running 与看板 live 徽章，并让每轮轮询对死卡做全套富化。
    """
    name = f"{card_id}-audit.running" if audit else f"{card_id}.running"
    marker = Path(log_dir) / name
    try:
        raw = marker.read_text(encoding="utf-8")
    except OSError:
        return False
    import re as _re

    pids = [int(m) for m in _re.findall(r"(?:pid|engine_pid|child_pid)=(\d+)", raw)]
    for pid in pids:
        if pid <= 1:
            continue
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            continue
        except OSError:
            return True
    return False


def _infra_cooldown_active_web(rt: dict, now_ts: float) -> bool:
    cd = rt.get("infra_cooldown_until")
    if not cd:
        return False
    try:
        from datetime import datetime as _dt

        parsed = _dt.fromisoformat(cd.replace("Z", "+00:00"))
        return parsed.timestamp() > now_ts
    except (ValueError, TypeError):
        return False


# ── T53：后台任务进程实时展示（GET /tasks/running） ──


def _executor_log_dir() -> Path | None:
    """执行体日志目录（EXECUTOR_LOG_DIR）；未配置返回 None。

    解析顺序与 worktree 指标一致：
    1. 环境变量 ``EXECUTOR_LOG_DIR``
    2. ``CCC_CONFIG_ENV`` 文件内同名键（web-server launchd 通常只注入 CCC_CONFIG_ENV）
    """
    raw = os.environ.get("EXECUTOR_LOG_DIR", "").strip()
    if not raw:
        cfg_path = os.environ.get("CCC_CONFIG_ENV", "").strip() or str(
            _PROJECT_ROOT / "server" / "config" / "config.env"
        )
        if cfg_path:
            try:
                for line in Path(cfg_path).expanduser().read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, _, v = s.partition("=")
                    if k.strip() == "EXECUTOR_LOG_DIR":
                        raw = v.strip().strip('"').strip("'")
                        break
            except OSError:
                raw = ""
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _finding_type_from_title(title: str) -> str:
    """从巡查发现标题推导 type（P1#10 机审返工）。

    observer 报告表无 id 列（8 列：权重|交叉确认|影响|频次|标题|项目|acting_on|证据），
    只能从标题关键字映射。前端 typeLabel 按此值显示分类徽章。
    """
    t = str(title or "")
    if "维护区" in t or "四问" in t:
        return "missing_four_questions"
    if "状态漂移" in t or "漂移" in t:
        return "drift"
    if "缺席" in t or "缺段落" in t:
        return "missing_section"
    if "断链" in t or "不存在" in t or "未全部关闭" in t or "关联了不存在" in t:
        return "broken_link"
    if "进度不一致" in t:
        return "consistency"
    if "死文件" in t or "人工批注" in t or "打回卡" in t or "审核引用" in t:
        return "tech"
    return "scan"


def _tail_lines(path: Path, n: int = 5) -> list[str]:
    """读文件末尾 n 行；文件不存在/读取失败 → 空列表。

    从文件末尾开 8KB 窗口倒读，避免整文件载入（执行日志可能很大）。
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            start = max(0, size - 8192)
            f.seek(start)
            chunk = f.read()
        lines = chunk.splitlines()
        return lines[-n:]
    except OSError:
        return []


def _config_value(key: str, default: str) -> str:
    """读取配置值：环境变量 → ``CCC_CONFIG_ENV`` 文件 → 默认值。"""
    raw = os.environ.get(key, "").strip()
    if raw:
        return raw
    cfg_path = os.environ.get("CCC_CONFIG_ENV", "").strip()
    if cfg_path:
        try:
            for line in Path(cfg_path).expanduser().read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
        except OSError:
            pass
    return default


def _severity_from_weight(weight_str: str) -> str:
    """weight → 风险等级（与 observer.score_finding 同规则）。
    红旗 ≥10 / 黄旗 ≥4 / 蓝旗 <4。非数字 → 蓝旗。
    """
    try:
        w = float(weight_str)
    except (TypeError, ValueError):
        return "蓝旗"
    if w >= 10.0:
        return "红旗"
    if w >= 4.0:
        return "黄旗"
    return "蓝旗"


def _try_json_line(line: str) -> dict | None:
    try:
        parsed = json.loads(line)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


_RUNNING_TASKS_CACHE: dict[str, Any] = {"ts": 0.0, "key": "", "data": None}
_RUNNING_TASKS_TTL = 3.0


def _load_running_tasks() -> dict[str, Any]:
    """GET /tasks/running：执行中 + 机审中任务进程视图 + worktree / 日志指标。

    - 数据源：卡头「执行中」，或看板列「机审」（已回写待审）；
    - 时长：``.running`` / ``-audit.running`` birthtime；
    - 调用：汇总各阶段日志 ``→`` 等 + metrics sidecar 高水位；
    - dirty / lines：worktree 落盘改动（force 刷新）。
    """
    now0 = time.time()
    key = _log_activity_key(_executor_log_dir())
    if (
        _RUNNING_TASKS_CACHE["data"] is not None
        and _RUNNING_TASKS_CACHE["key"] == key
        and now0 - _RUNNING_TASKS_CACHE["ts"] < _RUNNING_TASKS_TTL
    ):
        return _RUNNING_TASKS_CACHE["data"]
    from server.board.models import board_column as _board_column
    from server.web.exec_metrics import parse_work_call_counts, running_timing
    from server.web.worktree_dirty import get_worktree_metrics

    items = _load_board_items()
    log_dir = _executor_log_dir()
    now = time.time()
    tasks: list[dict[str, Any]] = []
    for item in items:
        base = base_state(item.state)
        col = _board_column(item.state, bool(getattr(item, "machine_audit_passed", False)))
        live_marker = False
        if log_dir is not None:
            live_marker = _marker_alive_web(log_dir, item.id) or _marker_alive_web(log_dir, item.id, audit=True)
        if base != "执行中" and col != "机审" and not live_marker:
            continue
        metrics = get_worktree_metrics(item.id, force=False)
        task: dict[str, Any] = {
            "work_id": item.id,
            "title": item.title,
            "executor": item.executor,
            "board_column": col,
            "started_at": None,
            "elapsed_s": None,
            "log_tail": [],
            "last_activity_at": None,
            "log_bytes": None,
            "tool_calls": None,
            "audit_runs": None,
            "shell_calls": None,
            "dirty_files": metrics.get("dirty_files"),
            "lines_insert": metrics.get("lines_insert"),
            "lines_delete": metrics.get("lines_delete"),
            "branch_insert": metrics.get("branch_insert"),
            "branch_delete": metrics.get("branch_delete"),
        }
        if log_dir is not None:
            timing = running_timing(log_dir, item.id, now=now)
            task.update(timing)
            task["metrics_live"] = _marker_alive_web(log_dir, item.id) or _marker_alive_web(
                log_dir, item.id, audit=True
            )
            counts = parse_work_call_counts(log_dir, item.id)
            task["tool_calls"] = int(counts["tool_calls"] or 0) + int(counts["shell_calls"] or 0)
            task["shell_calls"] = counts["shell_calls"]
            task["audit_runs"] = int(counts.get("audit_runs") or 0)
            # 尾部：优先当前阶段（audit 进行中看 audit.log，否则主 log）
            audit_log = log_dir / f"{item.id}.audit.log"
            main_log = log_dir / f"{item.id}.log"
            if (log_dir / f"{item.id}-audit.running").is_file() and audit_log.is_file():
                task["log_tail"] = _tail_lines(audit_log, 5)
            elif main_log.is_file():
                task["log_tail"] = _tail_lines(main_log, 5)
            elif audit_log.is_file():
                task["log_tail"] = _tail_lines(audit_log, 5)
        tasks.append(task)
    tasks.sort(key=lambda t: (t["elapsed_s"] is None, -(t["elapsed_s"] or 0)))
    result = {"tasks": tasks}
    _RUNNING_TASKS_CACHE.update(ts=now0, key=key, data=result)
    return result


def _tail_lines_file(path: Path, n: int = 3) -> list[str]:
    """读文件最后 n 行（utf-8 容错，跳过空行）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [ln for ln in text.splitlines() if ln.strip()][-n:]
    except OSError:
        return []


def _log_delta(path: Path, pos: int) -> tuple[list[str], int]:
    """从 pos 偏移读新增行，返回 (行列表, 新偏移)。"""
    try:
        with open(path, "rb") as f:
            f.seek(pos)
            new = f.read()
            pos = f.tell()
        lines = [ln for ln in new.decode("utf-8", errors="replace").splitlines() if ln.strip()]
        return lines, pos
    except OSError:
        return [], pos


def _filter_log_line(raw: str) -> str | None:
    """日志行过滤：去 ANSI，丢弃引擎/工具痕迹/git 噪声，只保留含中文的主输出。"""
    try:
        from server.web.exec_metrics import strip_ansi

        line = strip_ansi(raw).strip()
    except Exception:
        line = raw.strip()
    if not line:
        return None
    if line.startswith("[ccc.engine]"):
        return None
    if line.startswith(("→", "$", ">")):
        return None
    if re.fullmatch(r"[-_=]{3,}", line):
        return None
    if not re.search(r"[\u4e00-\u9fff]", line):
        return None  # 只保留含中文的主输出（git/终端回声等丢弃）
    return line


class _APIHandler(BaseHTTPRequestHandler):
    """HTTP API 请求处理器。"""

    # 禁用父类日志（测试不污染 stdout）
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data: dict, status: int = 200):
        status_line, content_type, body = _json_response(data, status)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_401(self, msg: str = "unauthorized"):
        self._send_json({"error": msg}, 401)

    def _send_404(self):
        self._send_json({"error": "not found"}, 404)

    def _send_static(self, path: str) -> bool:
        """处理静态白名单路径（免鉴权）。命中返回 True，未命中返回 False。

        T23：浏览器直开 7788 看页面，静态资源（HTML/CSS/JS/data）放行。
        非白名单路径不处理，由 do_GET 继续走鉴权 + API 路由。
        白名单路径但文件尚未生成（如 board.js 未 export）→ 404，勿掉进 401。
        """
        resolved = _resolve_static_file(path)
        if resolved is None:
            if path in _STATIC_WHITELIST:
                self._send_404()
                return True
            return False
        target, ctype = resolved
        try:
            body = target.read_bytes()
        except OSError:
            self._send_404()
            return True
        if ctype.startswith("text/html") or str(target).endswith(".html"):
            text = body.decode("utf-8", errors="replace").replace("v=20260809t12", f"v={_compute_static_version()}")
            body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return True

    def _check_auth(self) -> bool:
        """鉴权中间件。返回 True 通过，False 已发送 401。

        T45 免登录模式（``CCC_WEB_AUTH_REQUIRED=0`` 默认）：全部端点放行（仅局域网）。
        """
        if not _auth_required():
            return True
        path = self.path.rstrip("/").split("?")[0]
        if path in _NO_AUTH_PATHS:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._send_401("missing or invalid Authorization header")
            return False
        token = auth[len("Bearer ") :]
        if _validate_token(token) is None:
            self._send_401("token expired or invalid")
            return False
        return True

    def _read_body(self) -> dict[str, Any] | None:
        """读取并解析 JSON 请求体。失败返回 None。"""
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _handle_session(self):
        """POST /session：账号密码校验 → 签发 token。"""
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        username = body.get("username", "")
        password = body.get("password", "")
        if not username or not password:
            self._send_json({"error": "username and password required"}, 400)
            return
        if not _AUTH_USERNAME or not _AUTH_PASSWORD_HASH:
            self._send_json({"error": "server auth not configured"}, 500)
            return
        if username != _AUTH_USERNAME or _password_hash(password) != _AUTH_PASSWORD_HASH:
            self._send_json({"error": "invalid username or password"}, 401)
            return
        _clean_expired_tokens()
        ttl = _get_token_ttl()
        token = _generate_token(username)
        expires_at = datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc).isoformat()
        self._send_json({"token": token, "expires_at": expires_at, "ttl_s": ttl})

    def _handle_conversation_post(self):
        """POST /conversation：调用 2017 Claude Code 大脑 Agent 并返回回复。

        body.stream=true → SSE 流式输出（text/event-stream）；否则同步 JSON（向后兼容）。
        T44：body 可带 ``thread_id``（会话维度历史/分锁）与 ``model``（档位覆盖），
        缺省保持全局行为。
        """
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        message = body.get("message", "")
        if not message:
            self._send_json({"error": "message required"}, 400)
            return
        thread_id = str(body.get("thread_id") or "").strip()
        model = str(body.get("model") or "").strip()
        project = str(body.get("project") or "").strip() or _project_of_thread_id(thread_id)
        if body.get("stream"):
            bridge = _chat_bridge_url()
            if bridge:
                _ensure_chat_bridge()
                # M1 对话桥代理：SSE 透传（原版 Claude Code，无 brain 人格/档位）
                self._proxy_chat_stream(bridge, message, thread_id, project)
                return
            self._handle_conversation_stream(message, thread_id, model, project)
            return
        bridge = _chat_bridge_url()
        if bridge:
            self._send_json({"error": "M1 对话桥仅支持 stream=true（前端已默认流式）"}, 400)
            return
        history = list(_conv_list_for(thread_id))
        success, reply, status = call_brain(message, history, session_key=thread_id or None, model=model or None)
        if not success:
            # 未配置(503)/忙(503)/失败(502)/超时(504)：不落历史
            self._send_json({"error": reply}, status)
            return
        now = datetime.now(timezone.utc).isoformat()
        with _conv_cond:
            conv = _conv_list_for(thread_id)
            conv.append({"role": "user", "message": message, "timestamp": now})
            conv.append({"role": "assistant", "message": reply, "timestamp": now})
            _conv_cond.notify_all()
        if thread_id and project:
            _persist_thread_messages(
                project,
                thread_id,
                [
                    {"role": "user", "message": message, "timestamp": now},
                    {"role": "assistant", "message": reply, "timestamp": now},
                ],
            )
        self._send_json({"reply": reply})

    def _handle_conversation_stream(self, message: str, thread_id: str = "", model: str = "", project: str = ""):
        """POST /conversation {stream:true}：SSE 逐事件转发大脑流式输出。

        错误（未配置/忙/超时/失败）也以 ``event: error`` 流式返回（HTTP 200），
        客户端统一按事件消费；仅 ``done{is_error:false}`` 时回写历史（与同步一致）。
        客户端断开（BrokenPipe/Reset）时关闭 generator 以释放大脑锁。
        T44：``thread_id`` 会话维度历史/分锁；``model`` 档位覆盖。
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")  # 禁用代理缓冲，SSE 实时性
        self.end_headers()
        gen = stream_brain_events(
            message,
            list(_conv_list_for(thread_id)),
            session_key=thread_id or None,
            model=model or None,
        )
        text_parts: list[str] = []
        done_text = ""
        finished_error: bool | None = None
        last_event = time.monotonic()
        SSE_IDLE_TIMEOUT = 60  # 60s 无数据即关闭，释放线程
        try:
            for event, payload in gen:
                if time.monotonic() - last_event > SSE_IDLE_TIMEOUT:
                    self.wfile.write(b'event: error\ndata: {"error":"sse idle timeout"}\n\n')
                    self.wfile.flush()
                    break
                last_event = time.monotonic()
                if event == "text":
                    text_parts.append(payload.get("text", "") or "")
                if event == "done":
                    finished_error = bool(payload.get("is_error"))
                    done_text = payload.get("text", "") or ""
                data = json.dumps(payload, ensure_ascii=False)
                self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            gen.close()
        if finished_error is False:
            reply = "".join(text_parts).strip() or done_text.strip()
            if reply:
                now = datetime.now(timezone.utc).isoformat()
                with _conv_cond:
                    conv = _conv_list_for(thread_id)
                    conv.append({"role": "user", "message": message, "timestamp": now})
                    conv.append({"role": "assistant", "message": reply, "timestamp": now})
                    _conv_cond.notify_all()
                if thread_id and project:
                    _persist_thread_messages(
                        project,
                        thread_id,
                        [
                            {"role": "user", "message": message, "timestamp": now},
                            {"role": "assistant", "message": reply, "timestamp": now},
                        ],
                    )

    def _client_gone(self) -> bool:
        """长轮询等待期间检测客户端是否断开（连接变为 readable/EOF）。"""
        try:
            r, _, _ = select.select([self.connection], [], [], 0)
        except (OSError, ValueError):
            return True
        return bool(r)

    def _wait_conversation_increment(
        self, after: int, timeout: int, thread_id: str = ""
    ) -> tuple[bool, list[dict[str, Any]], int]:
        """长轮询等待历史增量（T43/T44）。

        在 ``_conv_cond`` 上挂起等待，返回 ``(has_increment, messages, latest_seq)``：

        - 有新消息（seq > after）→ ``(True, conv[after:], latest_seq)``
        - 超时 → ``(False, [], latest_seq)``
        - 客户端断开 → 抛 ``ConnectionResetError``（调用方捕获，释放线程）

        ``thread_id`` 为空 → 全局历史（向后兼容）；否则会话维度列表。
        等待期间周期性检测连接 readable（客户端 reset/EOF）以提前退出，
        不依赖写入时才能发现的 BrokenPipe。
        """
        conv = _conv_list_for(thread_id)
        deadline = time.monotonic() + timeout
        with _conv_cond:
            while True:
                current = len(conv)
                if after < current:
                    return True, list(conv[after:]), current
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, [], current
                if self._client_gone():
                    raise ConnectionResetError("client disconnected during long poll")
                _conv_cond.wait(timeout=min(remaining, 0.5))

    def _handle_conversation_get(self):
        """GET /conversation：对话历史（T43 长轮询 + T44 会话维度）。

        无 ``after`` → 返回全量 ``{messages, seq}``（向后兼容）；
        带 ``after=<seq>&timeout=<s>`` → 挂起等待增量，超时返回空增量，
        seq 不变；``after``/``timeout`` 非法 → 400。
        ``thread_id=<id>`` → 会话维度历史（缺省全局）。
        """
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        thread_id = (qs.get("thread_id", [""])[0] or "").strip()
        after_raw = (qs.get("after", [""])[0] or "").strip()
        bridge = _chat_bridge_url()
        if bridge:
            _ensure_chat_bridge()
            import urllib.request
            from urllib.parse import quote

            project = _project_of_thread_id(thread_id) or "ccc"
            url = f"{bridge.rstrip('/')}/chat/history?project={quote(project)}&thread_id={quote(thread_id)}"
            if after_raw:
                url += f"&after={quote(after_raw)}"
            req = urllib.request.Request(url)
            token = _chat_bridge_token()
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
            except Exception as exc:
                self._send_json({"error": f"对话桥历史不可达: {exc}"}, 503)
                return
            self._send_json(data)
            return
        if not after_raw:
            # 向后兼容：全量返回（含 seq 光标）
            conv = _conv_list_for(thread_id)
            self._send_json({"messages": list(conv), "seq": len(conv)})
            return
        try:
            after = int(after_raw)
        except ValueError:
            self._send_json({"error": "invalid after cursor"}, 400)
            return
        if after < 0:
            self._send_json({"error": "invalid after cursor"}, 400)
            return
        timeout = _get_longpoll_timeout()
        t_raw = (qs.get("timeout", [""])[0] or "").strip()
        if t_raw:
            try:
                timeout = max(0, int(t_raw))
            except ValueError:
                self._send_json({"error": "invalid timeout"}, 400)
                return
        try:
            has_increment, messages, seq = self._wait_conversation_increment(after, timeout, thread_id)
        except (BrokenPipeError, ConnectionResetError):
            # 客户端断开：退出等待，释放线程（服务不崩溃）
            return
        self._send_json(
            {"messages": messages if has_increment else [], "seq": seq},
        )

    # ── /plans/* 端点 ──

    def _handle_plans_list(self):
        """GET /plans/list?project=&status=&q=
        Phase2：默认过滤掉「草案」状态（只返回已确认/部分执行/已完成/作废），
        显式传 status=草案 才含草案；传 status 精确过滤。
        """
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        project = qs.get("project", [None])[0]
        status = qs.get("status", [None])[0]
        q = qs.get("q", [None])[0]

        try:
            plans = list_plans(_PROJECT_ROOT, project=project, status=status, q=q)
        except OSError as exc:
            self._send_json({"error": f"方案列表读取失败: {exc}"}, 500)
            return

        # Phase2：默认排除「草案」（除非显式请求某个状态含草案）
        if status is None:
            plans = [p for p in plans if p.get("status") != "草案"]

        self._send_json({"plans": plans, "total": len(plans)})

    def _handle_plans_card_states(self):
        """GET /plans/card-states → 方案关联卡在看板六列分布（ccc-plan-024 流程条）。"""
        from server.board.plans import plan_card_states

        try:
            cards = _enriched_cards(include_archived=False)
            states = plan_card_states(_PROJECT_ROOT, cards)
        except OSError as exc:
            self._send_json({"error": f"方案卡状态读取失败: {exc}"}, 500)
            return
        self._send_json({"states": states})

    def _handle_plans_detail(self):
        """GET /plans/detail?path=docs/projects/ccc/plans/001-test.md"""
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        rel_path = qs.get("path", [None])[0]

        if not rel_path:
            self._send_json({"error": "缺少 path 参数"}, 400)
            return

        try:
            plan = get_plan(_PROJECT_ROOT, rel_path)
        except OSError as exc:
            self._send_json({"error": f"方案读取失败: {exc}"}, 500)
            return

        if plan is None:
            self._send_json({"error": "方案不存在"}, 404)
            return

        self._send_json(plan)

    def _handle_plans_create(self):
        """POST /plans/create {project, title, content, author, tool}"""
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return

        project = body.get("project", "").strip()
        title = body.get("title", "").strip()
        content = body.get("content", "").strip()
        author = body.get("author", "").strip()
        tool = body.get("tool", "").strip()
        milestone = body.get("milestone")

        if not project or not title:
            self._send_json({"error": "缺少 project 或 title"}, 400)
            return

        if not author:
            self._send_json({"error": "作者不能为空"}, 400)
            return

        result = create_plan(
            _PROJECT_ROOT,
            project=project,
            title=title,
            content=content,
            author=author or "未知",
            tool=tool or "未知",
            milestone=milestone,
        )

        if "error" in result:
            self._send_json(result, 400)
        else:
            self._send_json(result, 201)

    def _handle_plans_update(self):
        """POST /plans/update {path, status?, content?, cards?}"""
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return

        rel_path = body.get("path", "").strip()
        if not rel_path:
            self._send_json({"error": "缺少 path 参数"}, 400)
            return

        result = update_plan(
            _PROJECT_ROOT,
            rel_path=rel_path,
            status=body.get("status"),
            content=body.get("content"),
            cards=body.get("cards"),
            milestone=body.get("milestone"),
        )

        # 人审调整动作统一化：方案作废级联的卡 → 清运行时 sidecar（终态权威=卡文件）
        cascaded = result.get("cascaded") or []
        if cascaded:
            log_dir = _executor_log_dir()
            if log_dir is not None:
                try:
                    from server.engine.runtime_state import clear_card_state

                    for _cid in cascaded:
                        clear_card_state(log_dir, _cid)
                except Exception:
                    logger.exception("方案作废级联清 sidecar 失败（不阻断）")

        if "error" in result:
            self._send_json(result, 400)
        else:
            self._send_json(result)

    def _handle_plans_convert(self):
        """POST /plans/convert {path}"""
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return

        rel_path = body.get("path", "").strip()
        if not rel_path:
            self._send_json({"error": "缺少 path 参数"}, 400)
            return

        result = convert_plan(_PROJECT_ROOT, rel_path=rel_path)

        if "error" in result:
            self._send_json(result, 400)
        else:
            self._send_json(result)

    # ── Phase2 线路图 API（roadmap.py）─────────────────────────────

    _ROADMAP_PREFIX_RE = re.compile(r"^[a-z]{2,4}$")

    def _roadmap_read(self, project: str) -> tuple[Any, str]:
        """读项目 roadmap.md，返回 (parsed, text)。无文件/非法前缀返回 (None, '')。
        前缀白名单校验防路径穿越（project 来自 URL 段）。"""
        if not self._roadmap_project_ok(project):
            return None, ""
        from server.board import roadmap as _rm

        _file = Path("docs") / "projects" / project / "roadmap.md"
        if not _file.is_file():
            return None, ""
        _text = _file.read_text(encoding="utf-8", errors="replace")
        return _rm.parse_roadmap(_text, project=project), _text

    def _roadmap_project_ok(self, project: str) -> bool:
        """项目前缀白名单校验（防路径穿越：project 来自 URL 段，只允许 a-z 2-4 位）。"""
        return bool(project and self._ROADMAP_PREFIX_RE.match(project))

    def _roadmap_git_commit(self, project: str, message: str) -> None:
        """roadmap.md 变更落 git（commit + push，失败留脏现场 + 告警，不吞错误不重试）。"""
        try:
            subprocess.run(
                ["git", "add", "--", f"docs/projects/{project}/roadmap.md"],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "push"],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "roadmap 落 git 失败（保留脏现场）: %s (%s)", message, (exc.stderr or exc.stdout or "").strip()[:300]
            )

    def _card_git_commit(self, card_path: Path, message: str) -> None:
        """卡文件变更落 git（commit + push，失败留脏现场 + 告警，不吞错误不重试）。

        人审调整动作统一化：卡作废（终态）写卡文件后落 git，与 roadmap 落 git 同规则。
        """
        rel = str(card_path.relative_to(_PROJECT_ROOT))
        try:
            subprocess.run(
                ["git", "add", "--", rel],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "push"],
                cwd=str(_PROJECT_ROOT),
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            logger.error(
                "card 落 git 失败（保留脏现场）: %s (%s)", message, (exc.stderr or exc.stdout or "").strip()[:300]
            )

    def _delete_card_remote_branch(self, card_path: Path) -> None:
        """作废卡自动删远端 codex/<stem> 分支（人审统一化 2026-08-14）。

        仅当远端分支存在时删除；失败仅告警不阻断（卡作废已由卡文件权威化）。
        """
        branch = ""
        try:
            stem = card_path.stem.lower()
            branch = f"codex/{stem}"
            # 检查远端分支是否存在
            r = subprocess.run(
                ["git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"],
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode != 0:
                return  # 分支不存在，无需删除
            subprocess.run(
                ["git", "push", "origin", "--delete", branch],
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            logger.info("作废卡删除远端分支: %s", branch)
        except Exception as exc:
            logger.warning("作废卡删远端分支失败（不阻断）: %s (%r)", branch, exc)

    def _handle_roadmap_projects(self):
        """GET /roadmap/projects — 全部项目线路图（草案池 + 里程碑）。"""
        from server.board import roadmap as _rm

        _projects = _rm.list_roadmaps()
        _list = []
        for _p in _projects:
            _parsed, _ = self._roadmap_read(_p)
            _parsed = _parsed or {}
            _list.append(
                {
                    "project": _p,
                    "drafts": [
                        {"title": _d.title, "source": _d.source, "created": _d.created}
                        for _d in _parsed.get("drafts", [])
                    ],
                    "milestones": [
                        {
                            "title": _m.title,
                            "status": _m.status,
                            "linked_plans": _rm.active_linked_plans(_p, list(_m.linked_plans)),
                            "description": _m.description,
                            "target_date": _m.target_date,
                            "timeline": _m.timeline,
                            "version": _m.version,
                        }
                        for _m in _parsed.get("milestones", [])
                    ],
                    "updated": _parsed.get("updated", ""),
                }
            )
        self._send_json({"roadmaps": _list, "total": len(_list)})

    def _handle_roadmap_detail(self, project: str):
        """GET /roadmap/<prefix> — 单项目线路图（草案池 + 里程碑）。"""
        from server.board import roadmap as _rm

        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        _parsed, _ = self._roadmap_read(project)
        if _parsed is None:
            self._send_json({"error": f"项目 {project} 尚无 roadmap.md"}, 404)
            return
        self._send_json(
            {
                "project": project,
                "drafts": [
                    {"title": _d.title, "source": _d.source, "created": _d.created}
                    for _d in _parsed.get("drafts", [])
                ],
                "milestones": [
                    {
                        "title": _m.title,
                        "status": _m.status,
                        "linked_plans": _rm.active_linked_plans(project, list(_m.linked_plans)),
                        "description": _m.description,
                        "target_date": _m.target_date,
                            "timeline": _m.timeline,
                            "version": _m.version,
                    }
                    for _m in _parsed.get("milestones", [])
                ],
                "updated": _parsed.get("updated", ""),
            }
        )

    def _handle_roadmap_milestone_create(self, project: str):
        """POST /roadmap/<prefix>/milestone {title, status?, description?, linked_plans?}"""
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return
        title = (body.get("title", "") or "").strip()
        if not title:
            self._send_json({"error": "缺少 title"}, 400)
            return
        from server.board import roadmap as _rm

        _result = _rm.create_milestone(
            project,
            title,
            status=(body.get("status") or "待启动").strip(),
            linked_plans=body.get("linked_plans"),
            description=(body.get("description") or "").strip(),
            target_date=(body.get("target_date") or "").strip(),
        )
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 新增里程碑 {title}")
        self._send_json(_result, 201)

    def _handle_roadmap_milestone_update(self, project: str, title: str):
        """PUT /roadmap/<prefix>/milestone/<id> {status?, description?, linked_plans?}"""
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return
        from server.board import roadmap as _rm

        _result = _rm.update_milestone(
            project,
            title,
            status=body.get("status"),
            linked_plans=body.get("linked_plans"),
            description=body.get("description"),
            target_date=(body.get("target_date") or "").strip(),
        )
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 更新里程碑 {title}")
        self._send_json(_result)

    def _handle_roadmap_milestone_delete(self, project: str, title: str):
        """DELETE /roadmap/<prefix>/milestone/<title> — 删除里程碑（仅当无关联方案）。

        人审调整动作统一化（2026-08-14）：补齐 rebuild-design 的 DELETE 端点。
        """
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        from server.board import roadmap as _rm

        _result = _rm.delete_milestone(project, title)
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 删除里程碑 {title}")
        self._send_json(_result)

    def _handle_roadmap_draft_create(self, project: str):
        """POST /roadmap/<prefix>/draft {title}"""
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        body = self._read_body()
        if body is None:
            self._send_json({"error": "无效的请求体"}, 400)
            return
        title = (body.get("title", "") or "").strip()
        if not title:
            self._send_json({"error": "缺少 title"}, 400)
            return
        from server.board import roadmap as _rm

        source = str(body.get("source") or "").strip()
        _result = _rm.create_draft(project, title, source=source)
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 新增草案 {title}")
        self._send_json(_result, 201)

    def _handle_roadmap_draft_promote_to_plan(self, project: str):
        """POST /roadmap/<prefix>/draft/<index>/promote-to-plan — 草案→方案一键升级（Phase 4.3）。

        从 roadmap.md 草案池取一条草案（按索引），调用 plans.create_plan 创建方案，
        并从草案池移除该条目。
        body: {index?: int, author?: string, tool?: string}
        """
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        body = self._read_body() or {}
        index = body.get("index", 0)
        if not isinstance(index, int) or index < 0:
            index = 0
        author = str(body.get("author") or "system").strip()
        tool = str(body.get("tool") or "ccc").strip()

        from server.board import roadmap as _rm

        _result = _rm.promote_draft_to_plan(project, index=index, author=author, tool=tool)
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 草案→方案 {_result.get('draft_title', '')}")
        self._send_json(_result, 201)

    def _handle_roadmap_draft_edit(self, project: str, index: int):
        """PUT /roadmap/<prefix>/draft/<index> {title} — 修改草案（人审调整动作：节点① 改草案）。"""
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        body = self._read_body() or {}
        new_title = str(body.get("title") or "").strip()
        if not new_title:
            self._send_json({"error": "缺少 title"}, 400)
            return
        from server.board import roadmap as _rm

        _result = _rm.edit_draft(project, index, new_title)
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 修改草案 {new_title}")
        self._send_json(_result)

    def _handle_roadmap_draft_remove(self, project: str, index: int):
        """DELETE /roadmap/<prefix>/draft/<index> — 取消草案（人审调整动作：节点① 取消=不再执行）。"""
        if not self._roadmap_project_ok(project):
            self._send_json({"error": "无效项目前缀"}, 400)
            return
        from server.board import roadmap as _rm

        _result = _rm.remove_draft(project, index)
        if "error" in _result:
            self._send_json(_result, 400)
            return
        self._roadmap_git_commit(project, f"roadmap({project}): 取消草案 {_result.get('removed', '')}")
        self._send_json(_result)

    def _handle_cards_get(self):
        """GET /cards?project=&state=&page=&page_size="""
        from urllib.parse import parse_qs
        from server.board.models import base_state

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        project = (qs.get("project", [""])[0]).strip()
        state = (qs.get("state", [""])[0]).strip()
        executor = (qs.get("executor", [""])[0]).strip()
        dispatched_at = (qs.get("dispatched_at", [""])[0]).strip()
        written_at = (qs.get("written_at", [""])[0]).strip()
        closed_at = (qs.get("closed_at", [""])[0]).strip()
        include_archived = (qs.get("include_archived", [""])[0]).strip().lower() in ("1", "true")

        try:
            page = int(qs.get("page", ["1"])[0].strip() or "1")
        except ValueError:
            page = 1
        if page < 1:
            page = 1

        try:
            page_size = int(qs.get("page_size", ["50"])[0].strip() or "50")
        except ValueError:
            page_size = 50
        if page_size < 1:
            page_size = 50

        # 合成视图 + 运行时富化，整表缓存（运行 marker 变化才失效）
        cards_list = _enriched_cards(include_archived=include_archived)

        filtered = cards_list
        if not include_archived:
            filtered = [c for c in filtered if not c.get("archived", False)]
        if project:
            filtered = [c for c in filtered if c["project"].lower() == project.lower()]
        if state:
            from server.board.models import board_column as _board_column

            def _match_col(c: dict, want: str = state) -> bool:
                audit_ok = bool(c.get("machine_audit_passed", False))
                col = c.get("board_column") or _board_column(c.get("state", ""), audit_ok)
                return c.get("state") == want or base_state(c.get("state", "")) == want or col == want

            filtered = [c for c in filtered if _match_col(c)]
        if executor:
            filtered = [c for c in filtered if executor.lower() in c.get("executor", "").lower()]
        if dispatched_at:
            filtered = [c for c in filtered if c.get("dispatched_at") == dispatched_at]
        if written_at:
            filtered = [c for c in filtered if c.get("written_at") == written_at]
        if closed_at:
            filtered = [c for c in filtered if c.get("closed_at") == closed_at]

        total = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = filtered[start_idx:end_idx]

        cards_out: list[dict[str, Any]] = []
        for c in paginated:
            row = dict(c)
            if "board_column" not in row:
                from server.board.models import board_column as _bc

                row["board_column"] = _bc(
                    row.get("state", ""),
                    bool(row.get("machine_audit_passed", False)),
                )
            cards_out.append(row)

        self._send_json(
            {
                "cards": cards_out,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
            }
        )

    def _handle_cards_search(self):
        """GET /cards/search?q=&project=&state=&page="""
        from urllib.parse import parse_qs
        from server.board.models import base_state

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        q = (qs.get("q", [""])[0]).strip().lower()
        project = (qs.get("project", [""])[0]).strip()
        state = (qs.get("state", [""])[0]).strip()
        executor = (qs.get("executor", [""])[0]).strip()
        dispatched_at = (qs.get("dispatched_at", [""])[0]).strip()
        written_at = (qs.get("written_at", [""])[0]).strip()
        closed_at = (qs.get("closed_at", [""])[0]).strip()
        include_archived = (qs.get("include_archived", [""])[0]).strip().lower() in ("1", "true")

        try:
            page = int(qs.get("page", ["1"])[0].strip() or "1")
        except ValueError:
            page = 1
        if page < 1:
            page = 1

        page_size = 50

        # 合成视图：git 真相 + 运行时状态 + 分支信封证据
        cards_list = [i.to_dict() for i in _load_board_items(include_archived=include_archived)]

        filtered = cards_list
        if not include_archived:
            filtered = [c for c in filtered if not c.get("archived", False)]
        if project:
            filtered = [c for c in filtered if c["project"].lower() == project.lower()]
        if state:
            from server.board.models import board_column as _board_column

            def _match_col_search(c: dict, want: str = state) -> bool:
                audit_ok = bool(c.get("machine_audit_passed", False))
                col = c.get("board_column") or _board_column(c.get("state", ""), audit_ok)
                return c.get("state") == want or base_state(c.get("state", "")) == want or col == want

            filtered = [c for c in filtered if _match_col_search(c)]
        if executor:
            filtered = [c for c in filtered if executor.lower() in c.get("executor", "").lower()]
        if dispatched_at:
            filtered = [c for c in filtered if c.get("dispatched_at") == dispatched_at]
        if written_at:
            filtered = [c for c in filtered if c.get("written_at") == written_at]
        if closed_at:
            filtered = [c for c in filtered if c.get("closed_at") == closed_at]

        if q:
            scored = []
            for c in filtered:
                score = 0.0
                if q in c["id"].lower():
                    score += 10.0 if c["id"].lower() == q else 5.0
                if q in c["title"].lower():
                    score += 3.0
                if q in c.get("executor", "").lower():
                    score += 1.5
                if q in c["project"].lower():
                    score += 1.0
                if q in c["state"].lower():
                    score += 0.5

                if score > 0.0:
                    scored.append((score, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [item for _, item in scored]
        else:
            results = filtered
            results.sort(key=lambda x: x["id"])

        total = len(results)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = results[start_idx:end_idx]

        self._send_json(
            {
                "cards": paginated,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
            }
        )

    def _handle_board_snapshot(self, items: list[BoardItem]):
        """GET /board/snapshot?workspace=X&include_hidden=0 → BoardSnapshot 兼容结构。"""
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        workspace = (qs.get("workspace", [""])[0]).strip()
        # include_hidden 参数接受但任务卡无 hidden 标记（契约 §4 派生视图）
        self._send_json(_build_snapshot(items, workspace))

    def _handle_board_summaries(self, items: list[BoardItem]):
        """GET /board/summaries?workspaces=a,b → {summaries: {项目: BoardSnapshot}}。"""
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        raw = (qs.get("workspaces", [""])[0]).strip()
        workspaces = [w.strip() for w in raw.split(",") if w.strip()] if raw else []
        if not workspaces:
            # 无参数 → 全部项目各自一个 snapshot
            workspaces = sorted({i.project for i in items})
        summaries = {ws: _build_snapshot(items, ws) for ws in workspaces}
        self._send_json({"summaries": summaries})

    def _handle_task_detail(self, items: list[BoardItem], task_id: str):
        """GET /tasks/{id} → BoardTaskDetail；未找到 404。"""
        detail = _find_task_detail(items, task_id)
        if detail is None:
            self._send_json({"error": f"task not found: {task_id}"}, 404)
            return
        self._send_json(detail)

    def _find_card_file(self, card_id: str) -> Path | None:
        """根据 id 寻找任务卡文件。"""
        candidates = sorted(_DISPATCH_DIR.glob(f"{card_id}-*.md"))
        if not candidates:
            candidates = sorted(_DISPATCH_DIR.glob(f"*/{card_id}-*.md"))
        if not candidates:
            candidates = sorted(_DISPATCH_DIR.glob(f"*{card_id}*.md"))
        return candidates[0] if candidates else None

    def _handle_task_transition(self, task_id: str):
        """POST /tasks/{id}/transition → 卡级动作统一入口（人审调整动作统一化 2026-08-14）。

        两种动作：
        1. 重新分派（打回/待分派 → 待分派）：写运行时 sidecar（state=待分派、
           retry_count=0、redispatch=ts），engine 每轮读取视同重派。主树卡文件只读。
        2. 作废（待分派/执行中/已回写/打回 → 作废）：终态，写卡文件
           `状态：作废（原因）` + git commit/push + 清 sidecar（与「已关闭」同级权威）。
        body: {status: "待分派"|"作废", reason?: string}
        """
        body = self._read_body()
        if not body:
            self._send_json({"error": "request body required"}, 400)
            return

        target_state_str = (body.get("status") or body.get("state") or "").strip()
        normalized = target_state_str.lower()
        is_redispatch = normalized in ("todo", "待分派")
        is_void = normalized in ("void", "作废")
        if not (is_redispatch or is_void):
            self._send_json({"error": "transition 仅支持「待分派」(重派) /「作废」(终态)"}, 400)
            return

        log_dir = _executor_log_dir()

        item = next((i for i in _load_board_items() if i.id == task_id), None)
        if item is None:
            self._send_json({"error": f"task card not found for: {task_id}"}, 404)
            return

        cur = base_state(item.state)

        # ── 作废（终态，写卡文件）──
        if is_void:
            reason = (body.get("reason") or "").strip()
            if not reason:
                self._send_json({"error": "作废必须附原因（reason）"}, 400)
                return
            # 来源状态校验：待分派/执行中/已回写/打回 可作废（已关闭/已作废终态不可）
            if cur not in ("待分派", "执行中", "已回写", "打回"):
                self._send_json(
                    {"error": f"当前状态「{item.state}」不可作废（仅 待分派/执行中/已回写/打回）"},
                    400,
                )
                return

            # 定位卡文件：docs/dispatch/<prefix>/<task_id>-<slug>.md（含根目录旧 T 卡）
            card_path = None
            for p in _DISPATCH_DIR.rglob(f"{task_id}-*.md"):
                if "archive" not in p.as_posix():
                    card_path = p
                    break
            if card_path is None:
                self._send_json({"error": f"未找到卡文件: {task_id}"}, 404)
                return

            # 写卡文件 `状态：作废（原因）`（复用 engine store 的状态段替换）
            from server.engine.store import _replace_state_in_metadata

            try:
                text = card_path.read_text(encoding="utf-8")
                new_text = _replace_state_in_metadata(
                    text, f"作废（{reason[:40]}）"
                )
            except ValueError as exc:
                self._send_json({"error": f"卡头无状态段: {exc}"}, 500)
                return
            card_path.write_text(new_text, encoding="utf-8")

            # git commit + push（与 roadmap 落 git 同规则）
            self._card_git_commit(card_path, f"cards: {task_id} 作废（人审取消）")

            # 人审统一化：作废卡自动删远端 codex/ 分支（避免僵尸分支；仅当分支存在）
            self._delete_card_remote_branch(card_path)

            # 清运行时 sidecar（终态权威 = 卡文件）
            if log_dir is not None:
                try:
                    from server.engine.runtime_state import clear_card_state

                    clear_card_state(log_dir, task_id)
                except Exception:
                    logger.exception("作废清 sidecar 失败（不阻断）")

            self._send_json({"ok": True, "id": task_id, "from": cur, "to": "作废", "reason": reason})
            return

        # ── 重新分派（打回/待分派 → 待分派，运行时 sidecar）──
        if log_dir is None:
            self._send_json({"error": "EXECUTOR_LOG_DIR 未配置，无法写运行时状态"}, 500)
            return

        if cur not in ("打回", "待分派"):
            self._send_json(
                {"error": f"当前状态「{item.state}」不可重新分派（仅打回/待分派）"},
                400,
            )
            return

        from datetime import datetime, timezone

        from server.engine.runtime_state import write_card_state

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        write_card_state(
            log_dir,
            task_id,
            state="待分派",
            retry_count=0,
            redispatch=ts,
        )
        # 机审命中率台账（v4 · 复审 P1-C）：打回→待分派 = 返工 → 通过行标未命中
        try:
            from server.board.audit_ledger import mark_card_pass_miss

            mark_card_pass_miss(task_id)
        except Exception:
            pass
        self._send_json({"ok": True, "id": task_id, "from": cur, "to": "待分派", "runtime": True})

    def _handle_task_audit(self, task_id: str):
        """POST /tasks/{id}/audit — 手动机审节点（流程开发阶段·老板手动转发去机审）。

        复用引擎 `_run_machine_audit_after_writeback`（与 `ccc-engine --audit` 同链路）。
        body: {severity?: "轻"|"中"|"重", force?: bool}
          - severity：覆盖 v4 判定（重度 → Phase 2 fresh agent 零上下文）
          - force：已有机审通过证据时强制重审
        """
        body = self._read_body() or {}
        severity = str(body.get("severity") or "").strip()
        force = bool(body.get("force"))
        if severity and severity not in ("轻", "中", "重"):
            self._send_json({"error": "severity 须为 轻/中/重"}, 400)
            return

        from server.config.loader import load_config_from_env
        from server.engine.dispatch import load_registry
        from server.engine.main import _card_machine_audit_passed, _run_machine_audit_after_writeback
        from server.engine.store import FileBoardStore

        try:
            cfg = load_config_from_env()
        except Exception as exc:
            self._send_json({"error": f"配置加载失败: {exc}"}, 500)
            return
        registry_path = cfg.get("EXECUTOR_REGISTRY_PATH", "")
        if not registry_path:
            self._send_json({"error": "EXECUTOR_REGISTRY_PATH 未配置"}, 500)
            return
        log_dir = _executor_log_dir()
        if log_dir is None:
            self._send_json({"error": "EXECUTOR_LOG_DIR 未配置"}, 500)
            return
        try:
            registry = load_registry(registry_path)
        except Exception as exc:
            self._send_json({"error": f"注册表加载失败: {exc}"}, 500)
            return
        store = FileBoardStore(
            cfg.get("DISPATCH_DIR") or "docs/dispatch",
            registry,
            log_dir=log_dir,
        )
        by_id = {w.id: w for w in store.list_work()}
        work = by_id.get(task_id)
        if work is None:
            self._send_json({"error": f"task card not found: {task_id}"}, 404)
            return
        # P2-D 修复：手动机审仅对已回写（机审列）卡开放；待分派/执行中不得跳过产物门禁
        from server.board.models import base_state

        card_state = base_state(str(work.state.value) if hasattr(work.state, "value") else str(work.state))
        if card_state != "已回写":
            self._send_json(
                {"error": f"当前状态「{card_state}」不可手动机审（仅 已回写 卡可审）"}, 400
            )
            return
        # P2-C 修复：在途防重——同卡审计已在跑则拒绝
        try:
            from server.engine.main import _audit_marker_alive

            if _audit_marker_alive(log_dir, work.id):
                self._send_json(
                    {"ok": True, "id": task_id, "busy": True, "reason": "该卡机审已在途，请稍后"}
                )
                return
        except Exception:
            pass
        if not force and _card_machine_audit_passed(work.card_path):
            self._send_json(
                {"ok": True, "id": task_id, "skipped": True, "reason": "已有机审通过证据（force 可强制重审）"}
            )
            return
        timeout = int(
            cfg.get("EXECUTOR_AUDIT_TIMEOUT_SECONDS")
            or cfg.get("EXECUTOR_TIMEOUT_SECONDS")
            or 1800
        )
        try:
            ok, problems, audited = _run_machine_audit_after_writeback(
                work, registry, cfg, log_dir, timeout,
                severity=severity or None, force=force, manual=True,
            )
        except Exception as exc:
            self._send_json({"error": f"机审拉起失败: {exc}"}, 500)
            return
        if not audited:
            # P1-E 修复：无验收席/已跳过 ≠ 通过，明确返回「未审」
            self._send_json(
                {"ok": True, "id": task_id, "audited": False, "conclusion": "未审",
                 "reason": "无验收席可审计或已跳过（非通过）"}
            )
            return
        conclusion = "通过" if ok else "不通过"
        self._send_json(
            {"ok": True, "id": task_id, "audited": True, "conclusion": conclusion,
             "problems": problems, "severity": severity or ""}
        )

    def _handle_audit_false_positive(self, task_id: str):
        """POST /tasks/{id}/false-positive — 老板标机审误报（命中率台账回填 hit=False）。

        打回卡被老板判定为误报时调用；回填台账里该卡最近一条未判定记录为未命中。
        """
        try:
            from server.board.audit_ledger import mark_card_hit

            found = mark_card_hit(task_id, False)
        except Exception as exc:
            self._send_json({"error": f"台账回填失败: {exc}"}, 500)
            return
        if not found:
            self._send_json({"error": f"未找到 {task_id} 的未判定「不通过」审计记录，无法标误报"}, 404)
            return
        self._send_json({"ok": True, "id": task_id, "marked": "false_positive"})

    def _handle_ops_summary(self):
        """GET /ops/summary → OpsSummary 兼容子集（cluster 采集 + board 派生 severity）。

        缺采集配置或采集失败：返回 200 + 空结构 + error 字段（容错，不 500）。
        """
        try:
            summary = _build_ops_summary()
            self._send_json(summary)
        except OSError as exc:
            # subprocess.TimeoutExpired 是 OSError 子类；采集失败不 500
            self._send_json(
                {
                    "overview": {"machines": [], "alert_count": 0, "down_ports": [], "generated_at": ""},
                    "severity": "red",
                    "human_line": f"运维采集失败: {exc}",
                    "error": str(exc),
                },
                200,
            )

    def _handle_ops_failures(self):
        """GET /ops/failures → 执行/机审失败原因聚合（第三步 · 挂账 2026-08-08）。

        主源 worker-events.jsonl（problem 未截断 + phase + exit_kind），
        兜底 state/cards.jsonl（reason，截 200 字）。
        返回：最近 N 条失败明细 + 按原因分类计数（打回 top / 机审不通过 top / 执行失败 top）。
        """
        import json as _json

        log_dir = _executor_log_dir()
        events_path = Path(log_dir) / "worker-events.jsonl" if log_dir else None
        events = []
        if events_path is not None and events_path.is_file():
            try:
                lines = _tail_lines(events_path, 400)
            except OSError:
                lines = []
            for ln in lines:
                try:
                    ev = _json.loads(ln)
                except Exception:
                    continue
                if ev.get("ok") is False and ev.get("work_id"):
                    events.append(ev)
        # 兜底：sidecar reason
        reasons: dict[str, str] = {}
        if log_dir:
            state_file = Path(log_dir) / "state" / "cards.jsonl"
            if state_file.is_file():
                try:
                    for ln in _tail_lines(state_file, 200):
                        try:
                            sd = _json.loads(ln)
                        except Exception:
                            continue
                        if sd.get("id") and sd.get("reason"):
                            reasons[str(sd["id"])] = str(sd["reason"])
                except OSError:
                    pass
        failures = []
        for ev in reversed(events[-30:]):
            wid = str(ev.get("work_id", ""))
            failures.append(
                {
                    "card_id": wid,
                    "ts": ev.get("ts", ""),
                    "phase": ev.get("phase", ""),
                    "exit_kind": ev.get("exit_kind", ""),
                    "problem": ev.get("problem") or reasons.get(wid, ""),
                }
            )
        # 分类 top 计数
        problem_counts: dict[str, int] = {}
        for ev in events:
            p = str(ev.get("problem") or "").strip()
            if not p:
                continue
            key = p[:40]
            problem_counts[key] = problem_counts.get(key, 0) + 1
        top = sorted(problem_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
        self._send_json(
            {
                "failures": failures,
                "total_fail_events": len(events),
                "top_reasons": [{"reason": k, "count": v} for k, v in top],
            }
        )

    def _handle_ops_concurrency(self):
        """GET /ops/concurrency → 槽位上限 + 并发/进程埋点尾部（只读，供运维）。"""

        from server.config.loader import OPTIONAL_KEYS

        exec_max = _config_value(
            "EXECUTOR_MAX_CONCURRENT",
            OPTIONAL_KEYS.get("EXECUTOR_MAX_CONCURRENT", "3"),
        )
        audit_max = _config_value(
            "EXECUTOR_MAX_AUDIT_CONCURRENT",
            OPTIONAL_KEYS.get("EXECUTOR_MAX_AUDIT_CONCURRENT", "2"),
        )
        try:
            exec_max = max(1, int(exec_max))
            audit_max = max(1, int(audit_max))
        except (TypeError, ValueError):
            exec_max, audit_max = 3, 2

        log_dir = _executor_log_dir()
        data: dict[str, Any] = {
            "slots": {"exec_max": exec_max, "audit_max": audit_max},
            "log_dir": str(log_dir) if log_dir else None,
        }
        if log_dir:
            data["engine_metrics_tail"] = [
                _try_json_line(line)
                for line in _tail_lines(log_dir / "engine-metrics.jsonl", 20)
                if _try_json_line(line) is not None
            ]
            data["worker_events_tail"] = [
                _try_json_line(line)
                for line in _tail_lines(log_dir / "worker-events.jsonl", 20)
                if _try_json_line(line) is not None
            ]
        else:
            data["engine_metrics_tail"] = []
            data["worker_events_tail"] = []
        self._send_json(data)

    def _handle_loop_findings(self):
        """GET /loop/findings → Loop Observer 巡查产出（运维看板类目·只读）。

        数据源：DATA_DIR/observer/*.md（observer.py 生成的巡查风险报告）。
        返回：报告清单（最新 N 份）+ 每份的结构化 findings（表行）+ 建议转卡命令。
        无报告 → 200 + 空。人审闸门数据源（采纳/不采纳/待定留档见 /loop/adopt）。
        """
        import re as _re
        from pathlib import Path as _Path

        def _summarize_finding(title: str) -> str:
            """技术标题 → 用户可读一句（与前端兜底逻辑同构，后端真值优先）。"""
            t = str(title or "")
            t = _re.sub(r"^任务卡\s*([a-z0-9]+)\s*状态漂移：", r"\1 状态漂移：", t)
            t = t.replace("roadmap.md 标注", "标注")
            t = t.replace("看板/卡文件实际状态", "实际")
            t = _re.sub(r"项目\s*([a-z0-9]+)\s*缺席 roadmap\.md 的业务线路段落", r"\1 项目缺少路线图段落", t)
            t = _re.sub(r"方案\s*([a-z0-9\-]+)\s*已完成但关联卡未关闭", r"\1 方案已完成但卡未关", t)
            t = _re.sub(r"卡\s*([a-z0-9]+)\s*缺维护区四问", r"\1 卡缺维护区填写", t)
            if len(t) > 40:
                t = t[:40] + "…"
            return t

        data_dir = _config_value("DATA_DIR", "data")
        observer_dir = _Path(data_dir).resolve() / "observer"
        reports: list[dict[str, Any]] = []
        if observer_dir.exists():
            files = sorted(observer_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files[:10]:
                text = f.read_text(encoding="utf-8", errors="ignore")
                head = [ln for ln in text.splitlines() if ln.strip()][:5]
                # 解析风险发现表行（| 权重 | ... | 标题 | 项目 | acting_on | 证据 |）
                findings: list[dict[str, Any]] = []
                in_table = False
                for ln in text.splitlines():
                    if ln.strip().startswith("| 权重"):
                        in_table = True
                        continue
                    if in_table and ln.strip().startswith("| ---"):
                        continue
                    if in_table and ln.strip().startswith("|"):
                        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                        if len(cells) >= 6:
                            # P1#10（机审返工）：报告表无 id 列（权重|交叉确认|影响|频次|标题|项目|acting_on|证据），
                            # 从标题关键字推导 type（此前取 cells[3] 错取频次数值 → 恒 "scan"）
                            findings.append(
                                {
                                    "weight": cells[0],
                                    "severity": _severity_from_weight(cells[0]),
                                    "title": cells[4],
                                    "human_title": _summarize_finding(cells[4]),
                                    "project": cells[5],
                                    "acting_on": cells[6].strip("`"),
                                    "evidence": cells[7].strip("`") if len(cells) > 7 else "",
                                    "ts": f.stat().st_mtime,
                                    "type": _finding_type_from_title(cells[4]),
                                }
                            )
                    elif in_table and not ln.strip().startswith("|"):
                        in_table = False
                # 解析建议转卡命令（```bash 块内 new-card.sh 行）
                commands: list[str] = _re.findall(r"scripts/new-card\.sh[^\n]*", text)
                reports.append(
                    {
                        "name": f.stem,
                        "mtime": f.stat().st_mtime,
                        "path": str(f),
                        "head": head,
                        "findings": findings,
                        "commands": [c.strip() for c in commands],
                    }
                )
        self._send_json({"loop_reports": reports, "count": len(reports)})

    def _handle_loop_adopt(self):
        """POST /loop/adopt → 人审闸门：采纳/不采纳/待定 Loop 发现，留档。

        只读侧的闸门记录（不自动出卡——出卡由 M1 执行 new-card.sh，Loop 只审不投）。
        body: {"report": "<报告名>", "finding": "<标题或ID>", "decision": "adopt|reject|pending",
               "reason": "<原因，可选>"}
        留档：DATA_DIR/observer/.adopted.jsonl（追加，防重复转卡）。
        """
        import json as _json
        import datetime as _dt
        from pathlib import Path as _Path

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = _json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            self._send_json({"ok": False, "error": "bad body"}, 400)
            return

        report = str(body.get("report", "")).strip()
        finding = str(body.get("finding", "")).strip()
        decision = str(body.get("decision", "")).strip()
        reason = str(body.get("reason", "")).strip()
        if decision not in ("adopt", "reject", "pending"):
            self._send_json({"ok": False, "error": "decision must be adopt|reject|pending"}, 400)
            return

        data_dir = _config_value("DATA_DIR", "data")
        adopt_file = _Path(data_dir).resolve() / "observer" / ".adopted.jsonl"
        try:
            adopt_file.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                "report": report,
                "finding": finding,
                "decision": decision,
                "reason": reason,
            }
            with adopt_file.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            self._send_json({"ok": False, "error": f"write failed: {exc}"}, 500)
            return

        self._send_json({"ok": True, "record": record})

    def _handle_ops_relay_stats(self):
        """GET /ops/relay-stats → 中转站今日请求（总/Pro/flash/code）+ 近10s增量 + 健康。"""
        self._send_json(_compute_relay_stats())

    def _handle_ops_ports(self):
        """GET /ops/ports → 集群端口全量探索（监听 + 三态分类 + 快照历史）。"""
        try:
            self._send_json(_build_ports_payload())
        except OSError as exc:
            self._send_json({"error": f"端口扫描失败: {exc}"}, 500)

    def _handle_ops_hp_health(self):
        """GET /ops/hp-health → HP 知识库节点探活 + 延迟。"""
        self._send_json(_build_hp_health())

    def _handle_ops_kb_health(self):
        """GET /ops/kb-health → 知识库健康：ccc-kb 本地索引 + hp-kb 探活/深度。"""
        self._send_json(_build_kb_health())

    def _handle_tasks_stream(self):
        """GET /tasks/stream?ids=a,b,c → SSE：snapshot 最近 3 行 + 日志增量 log 事件 + 15s 心跳。

        机审列读 {id}.audit.log，其余读 {id}.log；断连/异常即线程退出。
        """
        import json as _json
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        ids = [x for x in qs.get("ids", [""])[0].split(",") if x.strip()]
        log_dir = _executor_log_dir()

        col_by_id: dict[str, str] = {}
        try:
            from server.board.models import board_column as _board_column

            for item in _load_board_items():
                col_by_id[item.id.lower()] = _board_column(
                    item.state, bool(getattr(item, "machine_audit_passed", False))
                )
        except OSError:
            pass

        streams: dict[str, dict] = {}
        for cid in ids:
            key = cid.lower()
            files: dict[str, dict] = {}
            for source, fname in (("main", f"{key}.log"), ("audit", f"{key}.audit.log")):
                path = (log_dir / fname) if log_dir else None
                pos = 0
                if path is not None and path.is_file():
                    try:
                        pos = path.stat().st_size
                    except OSError:
                        pos = 0
                files[source] = {"path": path, "pos": pos}
            # snapshot 源：机审 marker 或列=机审 → audit；否则主日志
            auditing = col_by_id.get(key) == "机审"
            if log_dir is not None and _marker_alive_web(log_dir, key, audit=True):
                auditing = True
            streams[key] = {"files": files, "id": cid, "snapshot_source": "audit" if auditing else "main"}

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def emit(event: str, data: dict) -> None:
            payload = _json.dumps(data, ensure_ascii=False)
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
            self.wfile.flush()

        try:
            for cid, s in streams.items():
                src = s["files"][s["snapshot_source"]]
                raw_lines = _tail_lines_file(src["path"], 30) if src["path"] is not None else []
                lines = [ln for ln in raw_lines if _filter_log_line(ln) is not None][-5:]
                emit("snapshot", {"work_id": s["id"], "lines": lines})
            last_beat = time.time()
            while True:
                time.sleep(5.0)  # 统一看板刷新频率（老板 2026-08-12）
                for cid, s in streams.items():
                    for source, f in s["files"].items():
                        if f["path"] is None or not f["path"].is_file():
                            continue
                        lines, pos = _log_delta(f["path"], f["pos"])
                        if lines:
                            f["pos"] = pos
                            kept = [ln for ln in lines if _filter_log_line(ln) is not None]
                            for ln in kept:
                                emit("log", {"work_id": s["id"], "line": ln, "source": source})
                if time.time() - last_beat >= 15:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_beat = time.time()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_GET(self):
        # T23：静态白名单路径免鉴权（页面本身是登录入口）
        raw_path = self.path.split("?")[0]
        path = raw_path.rstrip("/") or "/"
        if self._send_static(path):
            return
        if path == "/health":
            # T30/T45：/health 返回鉴权配置，供前端登录门判断
            # auth_required：是否需 Bearer token（CCC_WEB_AUTH_REQUIRED，默认 0 免登录）
            # auth_configured：服务端是否已配置登录凭证（账号 + 密码哈希）
            self._send_json(
                {
                    "status": "ok",
                    "auth_required": _auth_required(),
                    "auth_configured": bool(_AUTH_USERNAME and _AUTH_PASSWORD_HASH),
                }
            )
            return
        if path == "/config":
            # T33：前端只读配置注入（免鉴权白名单，仅非敏感字段）
            self._send_json(_build_public_config())
            return
        if path == "/projects":
            # T47：真实业务项目清单（免鉴权白名单，与 /config 同；非任务卡分组）
            self._send_json({"projects": _build_public_projects()})
            return
        if path == "/tasks/running":
            # T53：执行中任务进程视图（免登录白名单，与 /projects 同组；须在 /tasks/{id} 之前）
            self._send_json(_load_running_tasks())
            return
        if path == "/tasks/stream":
            # 执行中/机审卡内实时日志流（SSE：snapshot 最近 3 行 + 增量 log 事件 + 心跳）
            self._handle_tasks_stream()
            return
        if path == "/cards":
            self._handle_cards_get()
            return
        if path == "/cards/search":
            self._handle_cards_search()
            return
        if not self._check_auth():
            return
        if path.startswith("/projects/") and path.endswith("/threads"):
            # 会话列表需鉴权（auth_required=0 时 _check_auth 直接放行）
            from urllib.parse import unquote

            project = unquote(path[len("/projects/") : -len("/threads")])
            bridge = _chat_bridge_url()
            if bridge:
                _ensure_chat_bridge()
                import urllib.request
                from urllib.parse import quote

                url = f"{bridge.rstrip('/')}/projects/{quote(project)}/threads"
                req = urllib.request.Request(url)
                token = _chat_bridge_token()
                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                try:
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        data = json.loads(resp.read().decode("utf-8", errors="replace"))
                except Exception as exc:
                    self._send_json({"error": f"对话桥会话列表不可达: {exc}"}, 503)
                    return
                self._send_json(data)
                return
            self._send_json({"threads": session_store.list_threads(project)})
            return
        if path == "/conversation":
            self._handle_conversation_get()
            return
        if path == "/ops/summary":
            self._handle_ops_summary()
            return
        elif path == "/ops/failures":
            self._handle_ops_failures()
            return
        if path == "/ops/concurrency":
            self._handle_ops_concurrency()
            return
        if path == "/ops/relay-stats":
            self._handle_ops_relay_stats()
            return
        if path == "/ops/ports":
            self._handle_ops_ports()
            return
        if path == "/ops/hp-health":
            self._handle_ops_hp_health()
            return
        if path == "/ops/kb-health":
            self._handle_ops_kb_health()
            return
        if path == "/loop/findings":
            self._handle_loop_findings()
            return
        if path == "/plans/list":
            self._handle_plans_list()
            return
        if path == "/plans/card-states":
            self._handle_plans_card_states()
            return
        if path == "/plans/detail":
            self._handle_plans_detail()
            return
        try:
            items = _load_board_items()
        except OSError as exc:
            self._send_json({"error": f"data load failed: {exc}"}, 500)
            return

        if path == "/board/realtime":
            self._send_json(view_realtime(items))
        elif path == "/board/recent":
            self._send_json(view_recent(items, now=date.today(), days=7))
        elif path == "/board/by_project":
            self._send_json(view_by_project(items))
        elif path == "/board/roadmap":
            # Phase2：改读 docs/projects/<prefix>/roadmap.md（roadmap.py），
            # 不再从 epic 卡派生 overview/by_project。
            try:
                from server.board import roadmap as _roadmap_mod

                _projects = _roadmap_mod.list_roadmaps()
                _roadmaps = []
                for _p in _projects:
                    _file = Path("docs") / "projects" / _p / "roadmap.md"
                    _text = _file.read_text(encoding="utf-8", errors="replace")
                    _parsed = _roadmap_mod.parse_roadmap(_text, project=_p)
                    _roadmaps.append(
                        {
                            "project": _p,
                            "drafts": [
                                {"title": _d.title, "source": _d.source, "created": _d.created}
                                for _d in _parsed.get("drafts", [])
                            ],
                            "milestones": [
                                {
                                    "title": _m.title,
                                    "status": _m.status,
                                    "linked_plans": _roadmap_mod.active_linked_plans(_p, list(_m.linked_plans)),
                                    "description": _m.description,
                                    "target_date": _m.target_date,
                            "timeline": _m.timeline,
                            "version": _m.version,
                                }
                                for _m in _parsed.get("milestones", [])
                            ],
                            "updated": _parsed.get("updated", ""),
                        }
                    )
                self._send_json({"roadmaps": _roadmaps, "total": len(_roadmaps)})
            except Exception:
                logger.exception("roadmap 聚合失败")
                self._send_json({"roadmaps": [], "total": 0})
        elif path.startswith("/board/roadmap/"):
            # 单项目线路图详情（2026-08-12）：里程碑 + 卡分组 + 风险，供 SVG 渲染
            _proj = path[len("/board/roadmap/") :]
            try:
                from server.board.roadmap_parser import (
                    load_roadmap_sections,
                    project_detail,
                )

                _rm_path = _PROJECT_ROOT / "docs" / "roadmap.md"
                _cards_by_id = {}
                _by_proj = {}
                for _it in items:
                    _cards_by_id[_it.id.lower()] = str(_it.state)
                    _by_proj[_it.id.lower()] = str(_it.project or "")
                _business = load_roadmap_sections(_rm_path, _cards_by_id, _by_proj)
                _detail = project_detail(_business, _proj)
            except Exception:
                logger.exception("roadmap 详情加载失败: %s", _proj)
                _detail = None
            if _detail is None:
                self._send_json({"error": f"项目 {_proj} 无业务线路"}, 404)
            else:
                self._send_json(_detail)
        elif path == "/roadmap/projects":
            self._handle_roadmap_projects()
        elif path.startswith("/roadmap/"):
            _proj = path[len("/roadmap/") :].strip("/").split("?")[0]
            self._handle_roadmap_detail(_proj)
        elif path == "/board/states":
            self._send_json(states_response(items))
        elif path == "/board/ready_for_merge":
            self._send_json(ready_for_merge(items))
        elif path == "/board/snapshot":
            self._handle_board_snapshot(items)
        elif path == "/board/summaries":
            self._handle_board_summaries(items)
        elif path == "/board/arch":
            self._send_json(_load_arch_index())
        elif path.startswith("/tasks/"):
            task_id = path[len("/tasks/") :].strip("/")
            if not task_id:
                self._send_404()
                return
            self._handle_task_detail(items, task_id)
        else:
            self._send_404()

    def do_POST(self):
        if not self._check_auth():
            return
        path = self.path.rstrip("/").split("?")[0]
        if path == "/session":
            self._handle_session()
        elif path == "/plans/create":
            self._handle_plans_create()
        elif path == "/plans/update":
            self._handle_plans_update()
        elif path == "/plans/convert":
            self._handle_plans_convert()
        elif path == "/conversation":
            self._handle_conversation_post()
        elif m := self._match_thread_route(path, "rename"):
            self._handle_thread_rename(m[0], m[1])
        elif path == "/loop/adopt":
            self._handle_loop_adopt()
        elif path.startswith("/tasks/") and path.endswith("/transition"):
            task_id = path[len("/tasks/") : -len("/transition")].strip("/")
            self._handle_task_transition(task_id)
        elif path.startswith("/tasks/") and path.endswith("/false-positive"):
            task_id = path[len("/tasks/") : -len("/false-positive")].strip("/")
            self._handle_audit_false_positive(task_id)
        elif path.startswith("/tasks/") and path.endswith("/audit"):
            task_id = path[len("/tasks/") : -len("/audit")].strip("/")
            self._handle_task_audit(task_id)
        elif path.startswith("/roadmap/"):
            self._dispatch_roadmap_post(path)
        else:
            self._send_404()

    def _dispatch_roadmap_post(self, path: str):
        """POST /roadmap/<prefix>/milestone | /roadmap/<prefix>/draft | /roadmap/<prefix>/draft/<id>/promote"""
        rest = path[len("/roadmap/") :].strip("/")
        segs = rest.split("/")
        project = segs[0] if segs else ""
        if len(segs) == 2 and segs[1] == "milestone":
            self._handle_roadmap_milestone_create(project)
            return
        if len(segs) == 2 and segs[1] == "draft":
            self._handle_roadmap_draft_create(project)
            return
        if len(segs) == 3 and segs[1] == "draft" and segs[2] == "promote-to-plan":
            # P0 全链路修复：草案→方案一键升级（人审节点①动作入口），body 带 index
            self._handle_roadmap_draft_promote_to_plan(project)
            return
        self._send_404()

    def do_PUT(self):
        """PUT /roadmap/<prefix>/milestone/<id> — 更新里程碑。"""
        if not self._check_auth():
            return
        path = self.path.rstrip("/").split("?")[0]
        rest = path[len("/roadmap/") :].strip("/") if path.startswith("/roadmap/") else ""
        segs = rest.split("/") if rest else []
        if len(segs) == 3 and segs[1] == "milestone":
            self._handle_roadmap_milestone_update(segs[0], segs[2])
            return
        # 人审调整动作统一化：PUT /roadmap/<prefix>/draft/<index> — 修改草案
        if len(segs) == 3 and segs[1] == "draft" and segs[2].isdigit():
            self._handle_roadmap_draft_edit(segs[0], int(segs[2]))
            return
        self._send_404()

    def do_DELETE(self):
        """DELETE /projects/<project>/threads/<thread>：删除会话（仅会话存储）。
        DELETE /roadmap/<prefix>/draft/<index>：取消草案（人审调整动作统一化）。"""
        if not self._check_auth():
            return
        path = self.path.rstrip("/").split("?")[0]
        m = self._match_thread_route(path, "delete")
        if m:
            project, thread_id = m
            session_store.delete_thread(project, thread_id)
            # 同步清内存中的该会话历史（长轮询/断连引用一并释放）
            _thread_conversations.pop(thread_id, None)
            self._send_json({"ok": True})
            return
        # 人审调整动作统一化：DELETE /roadmap/<prefix>/draft/<index> — 取消草案
        rest = path[len("/roadmap/") :].strip("/") if path.startswith("/roadmap/") else ""
        segs = rest.split("/") if rest else []
        if len(segs) == 3 and segs[1] == "draft" and segs[2].isdigit():
            self._handle_roadmap_draft_remove(segs[0], int(segs[2]))
            return
        # 人审调整动作统一化：DELETE /roadmap/<prefix>/milestone/<title> — 删除里程碑（仅无关联方案）
        if len(segs) == 3 and segs[1] == "milestone":
            self._handle_roadmap_milestone_delete(segs[0], segs[2])
            return
        self._send_404()

    def _proxy_chat_stream(self, bridge: str, message: str, thread_id: str, project: str) -> None:
        """转发 POST /chat 到 M1 对话桥，SSE 流式透传。"""
        import http.client

        m = re.match(r"http://([^:/]+):(\d+)", bridge)
        if not m:
            self._send_json({"error": f"对话桥地址非法: {bridge}"}, 500)
            return
        host, port = m.group(1), int(m.group(2))
        token = _chat_bridge_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(
            {"message": message, "thread_id": thread_id, "project": project},
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            conn = http.client.HTTPConnection(host, port, timeout=190)
            conn.request("POST", "/chat", body=body, headers=headers)
            resp = conn.getresponse()
        except Exception as exc:
            self._send_json({"error": f"M1 对话服务不可达: {exc}"}, 503)
            return
        self.send_response(resp.status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            return
        self._send_404()

    def _match_thread_route(self, path: str, kind: str) -> tuple[str, str] | None:
        """解析 /projects/<project>/threads/<thread>[/<kind>]（kind=delete|rename 时要求路径后缀）。

        delete → /threads/<id>（无后缀）；rename → /threads/<id>/rename。匹配返回 (project, thread_id)。
        project/thread_id 段做 URL 解码（thread_id 常含 ``::``）。
        """
        from urllib.parse import unquote

        prefix = "/projects/"
        if not path.startswith(prefix):
            return None
        rest = path[len(prefix) :]
        if kind == "rename":
            if not rest.endswith("/rename"):
                return None
            path_part = rest[: -len("/rename")]
        else:  # delete
            path_part = rest.rstrip("/")
        # path_part = <project>/threads/<thread>
        segs = path_part.split("/")
        if len(segs) != 3 or segs[1] != "threads":
            return None
        return unquote(segs[0]), unquote(segs[2])

    def _handle_thread_rename(self, project, thread_id):
        """POST /projects/<project>/threads/<thread>/rename：持久化改标题。"""
        body = self._read_body()
        if not body:
            self._send_json({"error": "invalid request body"}, 400)
            return
        title = str(body.get("title") or "").strip()
        if not title:
            self._send_json({"error": "title required"}, 400)
            return
        session_store.rename_thread(project, thread_id, title)
        self._send_json({"ok": True})


_last_card_states: dict[str, str] = {}


def _notify_card_status_change(item: BoardItem, change_type: str, old_state: str = None):
    thread_id = item.thread_id
    if not thread_id:
        return

    state_desc = base_state(item.state)
    if change_type == "created":
        msg_text = (
            f"【系统通知】任务卡 **{item.id}** 已成功下达并创建：\n- **标题**: {item.title}\n- **状态**: {item.state}"
        )
    else:
        msg_text = (
            f"【系统通知】任务卡 **{item.id}** 状态发生变化：\n- **标题**: {item.title}\n- **最新状态**: {item.state}"
        )
        if old_state:
            msg_text += f" (原状态: {old_state})"

    now = datetime.now(timezone.utc).isoformat()
    sys_msg = {
        "role": "system",
        "type": "task_status",
        "task_id": item.id,
        "status": state_desc,
        "title": item.title,
        "message": msg_text,
        "timestamp": now,
    }

    with _conv_cond:
        conv = _conv_list_for(thread_id)
        conv.append(sys_msg)
        _conv_cond.notify_all()

    project = _project_of_thread_id(thread_id)
    if project:
        _persist_thread_messages(project, thread_id, [sys_msg])


def _start_card_watcher():
    def watch_loop():
        # Initialize last card states on first scan
        try:
            items = _load_board_items()
            for item in items:
                _last_card_states[item.id] = item.state
        except Exception:
            pass

        while True:
            time.sleep(3)
            try:
                items = _load_board_items()
                for item in items:
                    old_state = _last_card_states.get(item.id)
                    if old_state is None:
                        # This is a newly created card!
                        _last_card_states[item.id] = item.state
                        _notify_card_status_change(item, "created")
                    elif old_state != item.state:
                        # Status changed!
                        _last_card_states[item.id] = item.state
                        _notify_card_status_change(item, "changed", old_state)
            except Exception:
                pass

    t = threading.Thread(target=watch_loop, daemon=True)
    t.start()


class _CCCThreadingHTTPServer(ThreadingHTTPServer):
    """并发 HTTP 服务。

    2026-08-09 修复：原 create_server 在 ``ThreadingHTTPServer(...)`` 构造
    （内部已 ``listen(5)``）之后才赋值 ``request_queue_size = 128``——属性
    赋值发生在 bind/activate 之后，对 backlog 无效（死代码），实际 backlog
    一直是 5。浏览器并发拉 20+ 静态资源时 accept 队列溢出，macOS 内核直接
    RST 掐断连接（tcpdump 实锤：SYN 后 ~7ms 收到 116:7788 的 RST），
    CSS/JS 模块加载失败 → 计划页从未挂载。改为类属性，listen 生效前即生效。

    2026-08-12 加固：① daemon_threads=True 避免进程退出时非 daemon 线程阻塞
    shutdown；② 信号量限流 max_workers=32，防止无界线程创建耗尽内存。
    """

    request_queue_size = 128
    daemon_threads = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._worker_semaphore = threading.BoundedSemaphore(32)

    def process_request(self, request: Any, client_address: Any) -> None:
        """线程池限流：静态只读端点免限，其余受信号量控制。"""
        # 静态端点（/health、/board/*）不占并发配额
        path = request.requestline.split(" ")[1] if hasattr(request, "requestline") else ""
        path = path.split("?")[0].rstrip("/") or "/"
        if path in ("/health",) or path.startswith("/board/"):
            super().process_request(request, client_address)
            return
        self._worker_semaphore.acquire()
        try:
            super().process_request(request, client_address)
        finally:
            self._worker_semaphore.release()


def create_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """创建 HTTP 服务实例（不启动）。

    T43：单线程 HTTPServer → ThreadingHTTPServer（并发），解除 SSE/长轮询
    挂起期间 /health、/board/*、第二路 /conversation 被网络层阻塞的 P1 问题
    （T42 独立复现实锤）。
    """
    return _CCCThreadingHTTPServer((host, port), _APIHandler)


def serve_forever(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """创建并启动 HTTP 服务（阻塞）。"""
    _start_card_watcher()

    def _bridge_heartbeat() -> None:
        """M1 对话桥保活心跳：30s 检查，挂了经 ssh 拉起（断链自愈）。"""
        import threading

        def _loop():
            while True:
                try:
                    if _chat_bridge_url():
                        _ensure_chat_bridge()
                except Exception:
                    logger.exception("bridge heartbeat failed")
                time.sleep(30)

        threading.Thread(target=_loop, daemon=True, name="ccc-bridge-heartbeat").start()

    _bridge_heartbeat()

    def _warmup() -> None:
        """启动后台预热：首屏 /cards、/tasks/running 冷缓存重算提前完成。"""
        import threading

        def _do():
            try:
                _enriched_cards()
                _load_running_tasks()
            except Exception:
                logger.exception("warmup failed")

        threading.Thread(target=_do, daemon=True, name="ccc-web-warmup").start()

    _warmup()
    server = create_server(host, port)
    addr = server.server_address
    print(f"[web] HTTP API 启动于 http://{addr[0]}:{addr[1]}", file=sys.stderr)
    print(f"[web] 数据源: {_DISPATCH_DIR}", file=sys.stderr)
    if _auth_required():
        print("[web] 提示: 已启用 Bearer token 鉴权（CCC_WEB_AUTH_REQUIRED=1）", file=sys.stderr)
    else:
        print("[web] 提示: 免登录模式（CCC_WEB_AUTH_REQUIRED=0，单用户局域网直连即用）", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        print("[web] 收到中断，关闭", file=sys.stderr)
        server.server_close()
    return server


def main():
    parser = argparse.ArgumentParser(description="CCC HTTP API 服务端")
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_PORT,
        help=f"监听端口（默认 {_DEFAULT_PORT}，0=随机，仅测试用）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址（默认 127.0.0.1）",
    )
    args = parser.parse_args()
    serve_forever(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
