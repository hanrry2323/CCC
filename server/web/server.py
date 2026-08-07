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
import mimetypes
import os
import select
import sys
import threading
import time
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# ── 项目根路径探测 ──
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.board.loader import load_dispatch_cards
from server.board.queries import (
    ready_for_merge,
    roadmap_overview,
    roadmap_by_project,
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
    """长轮询默认超时（秒，CCC_WEB_LONGPOLL_TIMEOUT，默认 30）。"""
    try:
        return max(0, int(os.environ.get("CCC_WEB_LONGPOLL_TIMEOUT", "30")))
    except ValueError:
        return 30


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

    note = item.progress if item.type == "epic" else ""

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

    字段：``id/name/kind/workspace_path/is_taskable``（T47 契约）。
    ``id`` 用 name 的稳定 slug；``kind`` 由 role/nature 推断；``workspace_path`` 为纯路径；
    ``is_taskable`` 走 _is_taskable_projects 白名单（可下达任务）。
    本接口不带任何任务卡分组名（INT-120 等只在看板筛选出现，不进入左栏）。
    """
    from server.board.registry import load_projects

    projects: list[dict[str, Any]] = []
    taskable = _is_taskable_projects()

    prefix_map = {}
    for p in load_projects():
        if p.name:
            prefix_map[p.name] = p.prefix
        if p.id:
            prefix_map[p.id] = p.prefix
        if p.display:
            prefix_map[p.display] = p.prefix

    for item in _load_project_metadata():
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        projects.append(
            {
                "id": name,  # 稳定 id（name 即业务仓稳定标识）
                "name": name,
                "kind": _infer_project_kind(item),
                "workspace_path": _extract_workspace_path(str(item.get("path") or "")),
                "is_taskable": name in taskable,
                "prefix": prefix_map.get(name, ""),
            }
        )
    # 固定排序：taskable 业务项目在前，其余按 name
    projects.sort(key=lambda p: (not p["is_taskable"], p["name"].lower()))
    return projects


def _infer_project_kind(item: dict[str, Any]) -> str:
    """由元数据推断项目种类：base（底座）/ business（业务）/ legacy（旧/退役）。"""
    role = str(item.get("role") or "").lower()
    nature = str(item.get("nature") or "").lower()
    name = str(item.get("name") or "").lower()
    last_act = str(item.get("last_activity") or "").lower()
    if (
        "退役" in role or "retired" in role or "旧" in role or "离线" in role
        or last_act == "retired" or "unknown" in last_act
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
        "phases": [],
        "events": [],
    }


# ── 运维接口辅助（T21：/ops/summary，cluster 采集 + board 派生 severity） ──


def _collect_ops_nodes() -> list[dict[str, Any]]:
    """采集集群节点状态（TCP 可达性），返回 OpsMachine 兼容字典列表。

    目标来自 CLUSTER_TARGETS env（逗号分隔 host:port）；空则返回空列表。
    """
    cfg = {"CLUSTER_TARGETS": os.environ.get("CLUSTER_TARGETS", "")}
    targets = parse_cluster_targets(cfg)
    machines: list[dict[str, Any]] = []
    for host, port in targets:
        ns = check_tcp_reachable(host, port)
        # 端口名走 env 映射（CLUSTER_PORT_NAMES=7788:web-server,4100:relay-anthropic），
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
        port_name = port_names.get(port, f"port-{port}")
        machines.append(
            {
                "name": port_name,
                "ip": host,
                "role": port_name,
                "reachable": ns.reachable,
                "alive_ports": 1 if ns.reachable else 0,
                "port_count": 1,
            }
        )
    return machines


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

    machines = _collect_ops_nodes()
    services = _collect_ops_services()
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


def _load_board_items():
    """加载任务卡数据。"""
    return load_dispatch_cards(_DISPATCH_DIR)


# ── T53：后台任务进程实时展示（GET /tasks/running） ──


def _executor_log_dir() -> Path | None:
    """执行体日志目录（EXECUTOR_LOG_DIR）；未配置返回 None。

    解析顺序与 worktree 指标一致：
    1. 环境变量 ``EXECUTOR_LOG_DIR``
    2. ``CCC_CONFIG_ENV`` 文件内同名键（web-server launchd 通常只注入 CCC_CONFIG_ENV）
    """
    raw = os.environ.get("EXECUTOR_LOG_DIR", "").strip()
    if not raw:
        cfg_path = os.environ.get("CCC_CONFIG_ENV", "").strip()
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


def _try_json_line(line: str) -> dict | None:
    try:
        parsed = json.loads(line)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _load_running_tasks() -> dict[str, Any]:
    """GET /tasks/running：执行中 + 机审中任务进程视图 + worktree / 日志指标。

    - 数据源：卡头「执行中」，或看板列「机审」（已回写待审）；
    - 时长：``.running`` / ``-audit.running`` birthtime；
    - 调用：汇总各阶段日志 ``→`` 等 + metrics sidecar 高水位；
    - dirty / lines：worktree 落盘改动（force 刷新）。
    """
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
            live_marker = (log_dir / f"{item.id}.running").is_file() or (
                log_dir / f"{item.id}-audit.running"
            ).is_file()
        if base != "执行中" and col != "机审" and not live_marker:
            continue
        metrics = get_worktree_metrics(item.id, force=True)
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
            task["metrics_live"] = bool(timing.get("live"))
            counts = parse_work_call_counts(log_dir, item.id)
            task["tool_calls"] = int(counts["tool_calls"] or 0) + int(counts["shell_calls"] or 0)
            task["shell_calls"] = counts["shell_calls"]
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
    return {"tasks": tasks}


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
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
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
            self._handle_conversation_stream(message, thread_id, model, project)
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
                project, thread_id,
                [{"role": "user", "message": message, "timestamp": now},
                 {"role": "assistant", "message": reply, "timestamp": now}],
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
        try:
            for event, payload in gen:
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
                        project, thread_id,
                        [{"role": "user", "message": message, "timestamp": now},
                         {"role": "assistant", "message": reply, "timestamp": now}],
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

    def _handle_cards_get(self):
        """GET /cards?project=&state=&page=&page_size="""
        from urllib.parse import parse_qs
        from server.board.loader import load_index_file
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

        try:
            index_entries = load_index_file()
            if not index_entries:
                index_entries = load_index_file(_DISPATCH_DIR)
            if not index_entries:
                import sys
                print(f"[web] 索引文件缺失或为空，自动回退全量扫描并重建索引: {_DISPATCH_DIR}", file=sys.stderr)
                from server.board.loader import load_dispatch_cards
                try:
                    load_dispatch_cards(_DISPATCH_DIR, include_archived=True)
                    index_entries = load_index_file()
                    if not index_entries:
                        index_entries = load_index_file(_DISPATCH_DIR)
                except Exception as e:
                    print(f"[web] 自动重建索引失败: {e}，回退至内存动态扫描", file=sys.stderr)
                    from server.board.loader import scan_dispatch_files, parse_card, build_index_entry, get_archive_dir, scan_archive_files
                    disk_files = scan_dispatch_files(_DISPATCH_DIR)
                    archive_dir = get_archive_dir(_DISPATCH_DIR)
                    archive_files = scan_archive_files(archive_dir)
                    index_entries = {}
                    for path in disk_files + archive_files:
                        try:
                            item = parse_card(path)
                            entry = build_index_entry(path, item, 0.0)
                            index_entries[item.id] = entry
                        except Exception:
                            continue
        except Exception as e:
            self._send_json({"error": f"index load failed: {e}"}, 500)
            return

        cards_list = list(index_entries.values())
        cards_list.sort(key=lambda x: x["id"])

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
                return (
                    c.get("state") == want
                    or base_state(c.get("state", "")) == want
                    or col == want
                )

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

        from server.web.exec_metrics import card_wants_runtime, enrich_card_runtime

        log_dir = _executor_log_dir()
        cards_out: list[dict[str, Any]] = []
        for c in paginated:
            row = dict(c)
            if "board_column" not in row:
                from server.board.models import board_column as _bc

                row["board_column"] = _bc(
                    row.get("state", ""),
                    bool(row.get("machine_audit_passed", False)),
                )
            # 调用/时长/Δ 跟卡走：执行中·机审·已回写·打回·已关闭（有日志或 worktree 才有数）
            if card_wants_runtime(row):
                enrich_card_runtime(
                    row,
                    log_dir,
                    force=base_state(c.get("state", "")) == "执行中",
                )
            cards_out.append(row)

        self._send_json({
            "cards": cards_out,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size > 0 else 1
        })

    def _handle_cards_search(self):
        """GET /cards/search?q=&project=&state=&page="""
        from urllib.parse import parse_qs
        from server.board.loader import load_index_file
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

        try:
            index_entries = load_index_file()
            if not index_entries:
                index_entries = load_index_file(_DISPATCH_DIR)
            if not index_entries:
                import sys
                print(f"[web] 索引文件缺失或为空，自动回退全量扫描并重建索引: {_DISPATCH_DIR}", file=sys.stderr)
                from server.board.loader import load_dispatch_cards
                try:
                    load_dispatch_cards(_DISPATCH_DIR, include_archived=True)
                    index_entries = load_index_file()
                    if not index_entries:
                        index_entries = load_index_file(_DISPATCH_DIR)
                except Exception as e:
                    print(f"[web] 自动重建索引失败: {e}，回退至内存动态扫描", file=sys.stderr)
                    from server.board.loader import scan_dispatch_files, parse_card, build_index_entry, get_archive_dir, scan_archive_files
                    disk_files = scan_dispatch_files(_DISPATCH_DIR)
                    archive_dir = get_archive_dir(_DISPATCH_DIR)
                    archive_files = scan_archive_files(archive_dir)
                    index_entries = {}
                    for path in disk_files + archive_files:
                        try:
                            item = parse_card(path)
                            entry = build_index_entry(path, item, 0.0)
                            index_entries[item.id] = entry
                        except Exception:
                            continue
        except Exception as e:
            self._send_json({"error": f"index load failed: {e}"}, 500)
            return

        cards_list = list(index_entries.values())

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
                return (
                    c.get("state") == want
                    or base_state(c.get("state", "")) == want
                    or col == want
                )

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

        self._send_json({
            "cards": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size > 0 else 1
        })

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
        """POST /tasks/{id}/transition
        Body: {"status": "..."} or {"state": "..."}
        """
        body = self._read_body()
        if not body:
            self._send_json({"error": "request body required"}, 400)
            return

        target_state_str = body.get("status") or body.get("state")
        if not target_state_str:
            self._send_json({"error": "status parameter is required"}, 400)
            return

        from server.engine.task import State, _LEGAL_TRANSITIONS
        state_map = {
            "todo": State.TODO,
            "running": State.RUNNING,
            "done": State.DONE,
            "closed": State.CLOSED,
            "rejected": State.REJECTED,
            "待分派": State.TODO,
            "执行中": State.RUNNING,
            "已回写": State.DONE,
            "已关闭": State.CLOSED,
            "打回": State.REJECTED,
        }

        target_state = state_map.get(target_state_str.lower() if isinstance(target_state_str, str) else target_state_str)
        if not target_state:
            self._send_json({"error": f"invalid status: {target_state_str}"}, 400)
            return

        card_file = self._find_card_file(task_id)
        if not card_file:
            self._send_json({"error": f"task card not found for: {task_id}"}, 404)
            return

        try:
            from server.board.loader import parse_card
            item = parse_card(card_file)
        except Exception as exc:
            self._send_json({"error": f"failed to parse card: {exc}"}, 500)
            return

        curr_state_str = item.state
        curr_state = state_map.get(curr_state_str)
        if not curr_state:
            curr_state = State.TODO

        allowed = _LEGAL_TRANSITIONS.get(curr_state, frozenset())
        if target_state not in allowed:
            allowed_vals = [s.value for s in sorted(allowed, key=str)]
            self._send_json({
                "error": f"Illegal state transition: {curr_state.value} -> {target_state.value} (Allowed targets: {allowed_vals})"
            }, 400)
            return

        try:
            from server.engine.store import _replace_state_in_metadata
            text = card_file.read_text(encoding="utf-8")
            new_state_str = target_state.value
            new_text = _replace_state_in_metadata(text, new_state_str)
            card_file.write_text(new_text, encoding="utf-8")

            # 重建索引/刷新看板
            from server.board.loader import load_dispatch_cards
            load_dispatch_cards(_DISPATCH_DIR)
        except Exception as exc:
            self._send_json({"error": f"failed to write transition: {exc}"}, 500)
            return

        self._send_json({"ok": True, "id": task_id, "from": curr_state.value, "to": target_state.value})

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
            self._send_json({"threads": session_store.list_threads(project)})
            return
        if path == "/conversation":
            self._handle_conversation_get()
            return
        if path == "/ops/summary":
            self._handle_ops_summary()
            return
        if path == "/ops/concurrency":
            self._handle_ops_concurrency()
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
            self._send_json(
                {
                    "overview": roadmap_overview(items),
                    "by_project": roadmap_by_project(items),
                }
            )
        elif path == "/board/states":
            self._send_json(states_response(items))
        elif path == "/board/ready_for_merge":
            self._send_json(ready_for_merge(items))
        elif path == "/board/snapshot":
            self._handle_board_snapshot(items)
        elif path == "/board/summaries":
            self._handle_board_summaries(items)
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
        elif path == "/conversation":
            self._handle_conversation_post()
        elif m := self._match_thread_route(path, "rename"):
            self._handle_thread_rename(m[0], m[1])
        elif path.startswith("/tasks/") and path.endswith("/transition"):
            task_id = path[len("/tasks/") : -len("/transition")].strip("/")
            self._handle_task_transition(task_id)
        else:
            self._send_404()

    def do_DELETE(self):
        """DELETE /projects/<project>/threads/<thread>：删除会话（仅会话存储）。"""
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
        rest = path[len(prefix):]
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
        msg_text = f"【系统通知】任务卡 **{item.id}** 已成功下达并创建：\n- **标题**: {item.title}\n- **状态**: {item.state}"
    else:
        msg_text = f"【系统通知】任务卡 **{item.id}** 状态发生变化：\n- **标题**: {item.title}\n- **最新状态**: {item.state}"
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


def create_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """创建 HTTP 服务实例（不启动）。

    T43：单线程 HTTPServer → ThreadingHTTPServer（并发），解除 SSE/长轮询
    挂起期间 /health、/board/*、第二路 /conversation 被网络层阻塞的 P1 问题
    （T42 独立复现实锤）。
    """
    server = ThreadingHTTPServer((host, port), _APIHandler)
    # 2026-08-05 修复：默认 request_queue_size=5，浏览器并发拉静态资源（20+ 连接）
    # 时连接队列溢出 → ERR_CONNECTION_RESET；调大队列消除并发连接失败。
    server.request_queue_size = 128
    return server


def serve_forever(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """创建并启动 HTTP 服务（阻塞）。"""
    _start_card_watcher()
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
