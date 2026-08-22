"""server/web/brain.py — 大脑 Agent 对话模块（T29）。

`/conversation` 不再裸转发 6102，改为调用 2017 本机 Claude Code CLI
（走 `127.0.0.1:6100` Anthropic 出口），携带 CCC 大脑人格 + 历史上下文，
返回真实 Agent 输出（有心智/工具/知识库）。

调用方式::

    subprocess.run([claude, "-p", prompt, "--output-format", "text"],
                   env={...6100...}, timeout=CCC_BRAIN_TIMEOUT)

流式（T41）：`--output-format stream-json --verbose` 逐事件读取，经
`stream_brain_events()` 归一化为 (meta / thinking / tool_use / text /
tool_result / done / error) 事件序列，供 HTTP SSE 转发。

并发保护：会话维度分锁（T44）——同会话串行、跨会话可并发，总并发上限
    ``CCC_BRAIN_MAX_CONCURRENCY``（默认 2，可配置）；失败/超时不落历史，
    返回明确错误码（503 未配置/忙 · 504 超时 · 502 失败）。

环境变量（零硬编码，2017 config.env 实际填写）::

    CCC_BRAIN_CLAUDE_BIN    Claude Code CLI 路径（默认 `claude`）
    CCC_BRAIN_MODEL         模型逻辑名（flash / Pro / code）
    CCC_BRAIN_BASE_URL      出口 base URL（如 http://127.0.0.1:6100）
    CCC_BRAIN_AUTH_TOKEN    出口 Bearer token
    CCC_BRAIN_TIMEOUT       调用超时秒（默认 120；知识题需读文档+推理，
                            实测 ~74s，60s 过紧故默认上调）

知识库检索注入（T37：回答前检索 CCC 自建知识库，命中才注入）::

    CCC_BRAIN_KB            知识库检索开关（1/true/yes/on 启用，默认关闭）
    CCC_KB_INDEX_DIR        BM25 索引目录（默认 knowledge/.index/）
    CCC_BRAIN_KB_TOP_K      检索返回条数（默认 3）

    红线（2026-08-14 部分解除）：只读 knowledge/（server/kb BM25 索引）为本体；
    允许经 server.kb.hp_client 只读调 hp-kb（HTTP），禁止写 hp-kb。
    未配置/未命中/检索异常/远端不可达 → 静默降级走裸大脑逻辑，对话不报错中断。
"""

from __future__ import annotations

import json
import os
import queue
import signal
import re
import http.client
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

# ── CCC 大脑人格（系统提示词，注入 prompt 头部；T41 心智升级：全能智能体四职责） ──
BRAIN_SYSTEM_PROMPT = (
    "你是 CCC 的大脑 Agent（全能智能体），负责规划、写任务卡、验收、看板维护四类职责，"
    "并作为多壳对话的大脑。所有输出：结论先行、条理清晰、中文作答；"
    "禁止把问题抛回给用户做选择题——信息不足时给出最合理判断与依据，而非反问。\n\n"
    "【职责一：规划】\n"
    "理解目标 → 拆解为可执行步骤 → 产出任务卡草案（产出 ```ccc-transfer ... ``` JSON 块供用户在对话中确认，绝对不要在第一阶段提前在 docs/dispatch 中创建或写入物理文件）。\n\n"
    "【职责二：写任务卡】\n"
    "只有当用户确认了草案，或者收到包含「确认下达」的指令后，你才正式执行【职责二】。此时你将任务卡正式写入 docs/dispatch/ 目录（或对应的子目录，如果是新卡），格式遵守 references/board-task-schema.md（契约 §1/§2）：\n"
    "- 标题：`# 任务卡 Txx · 标题`；`>` 元数据行 `关联：project` · `执行体：executor` · `状态：待分派` · `日期：YYYY-MM-DD` · `会话：thread_id`；\n"
    "- 必须在卡头的元数据行中保留 `会话：thread_id`（将其设为当前会话的 thread_id，如 qb::abc），以便状态能回流！\n"
    "- 正文：目标 / 范围 / 验收标准（可执行，含验证命令）/ 步骤 / 红线；\n"
    "- 状态机五态：待分派 → 执行中 → 已回写 → 已关闭（打回 → 待分派）；\n"
    "- 写卡前先读 docs/dispatch/ 现有卡编号，避免撞号。\n\n"
    "【职责三：验收】\n"
    "对照任务卡「验收标准」逐项判定：全部满足 → 通过；有缺失 → 打回并附问题清单"
    "（每项说明差距与补救方向），不口头放水、不凭印象 PASS。\n\n"
    "【职责四：看板维护】\n"
    "按状态机流转任务卡状态；打回时必须附原因；只在任务卡范围内修改，"
    "不越范围改其他卡、文档或系统文件（红线见 references/red-lines.md）。\n\n"
    "【工具契约】\n"
    "- 优先知识库检索：先查 CCC 自建知识库（BM25），命中片段已含条目 id，引用时显式标注 id；"
    "避免自行翻阅文件导致延迟（知识题实测 120s 超时 → 加引导后 14s）。\n"
    "- 再按需调用 Claude Code 内置工具：Read / Write / Bash / WebFetch，"
    "以及 MCP 工具（memory / fetch 等）。\n\n"
    "【输出规范】\n"
    "结论先行、条理清晰、给可执行结果（步骤 / 命令 / 任务卡草案），不给开放选择题。"
    "若知识库与文档均未覆盖，明确说明「信息不足」并给出最合理假设与依据。"
)

# 对话历史拼入 prompt 的最大轮数（user+assistant 算一轮）
_BRAIN_HISTORY_TURNS = 10

# 会话维度分锁（T44）：默认键 "" 复用 _brain_lock（向后兼容既有测试）；
# 同会话串行、跨会话可并发，总并发上限 CCC_BRAIN_MAX_CONCURRENCY（默认 2）。
_brain_lock = threading.Lock()
_session_locks: dict[str, threading.Lock] = {}
_slot_guard = threading.Lock()
_active_slots = 0

# 会话级模型覆盖（T44：thread-local，避免跨请求串扰）
_model_override = threading.local()


def _get_brain_max_concurrency() -> int:
    """跨会话总并发上限（CCC_BRAIN_MAX_CONCURRENCY，默认 2）。"""
    try:
        return max(1, int(os.environ.get("CCC_BRAIN_MAX_CONCURRENCY", "2")))
    except ValueError:
        return 2


def _get_brain_model_tiers() -> list[str]:
    """模型档位列表（CCC_MODEL_TIERS，逗号分隔，默认 flash,code）。"""
    raw = os.environ.get("CCC_MODEL_TIERS", "flash,code")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _session_lock(key: str) -> threading.Lock:
    """会话 → 锁映射：默认键 "" 用全局 _brain_lock（向后兼容）。"""
    if not key:
        return _brain_lock
    with _slot_guard:
        return _session_locks.setdefault(key, threading.Lock())


def _acquire_brain_slot(key: str) -> bool:
    """尝试获取会话槽位：总并发未超限 + 该会话锁空闲（同会话串行，跨会话可并发）。"""
    global _active_slots
    with _slot_guard:
        if _active_slots >= _get_brain_max_concurrency():
            return False
        _active_slots += 1
    lock = _session_lock(key)
    if not lock.acquire(blocking=False):
        with _slot_guard:
            _active_slots -= 1
        return False
    return True


def _release_brain_slot(key: str) -> None:
    global _active_slots
    _session_lock(key).release()
    with _slot_guard:
        _active_slots -= 1


def _effective_model() -> str:
    """当前请求生效模型：会话覆盖优先，否则环境变量。"""
    override = getattr(_model_override, "model", None) or ""
    return (override or "").strip() or _get_brain_model()


# ── 配置读取（运行时可刷新，测试可覆盖） ──
def _brain_cfg(key: str, default: str = "") -> str:
    """读取大脑配置：环境变量 → ``CCC_CONFIG_ENV`` 文件 → 默认值。

    与 ``server.py._config_value`` 同一优先级约定（环境变量优先，其次 config.env）。
    背景：2017 生产 web-server 经 launchd plist 注入部分 ``CCC_BRAIN_*`` 环境变量，
    但 config.env 中的其余配置（如 ``CCC_BRAIN_DIRECT=1``）不会自动进入 os.environ；
    此前 getters 只读 ``os.environ``，导致 config.env 新增配置在运行进程里静默失效。
    统一走本函数后，config.env 与 launchd 注入取并集，env 优先、config.env 兜底。
    """
    if key in os.environ:
        # 显式设置（含空串）优先：如 CCC_BRAIN_THINKING="" 表示静态关闭，不落到 config.env 默认
        return os.environ[key].strip()
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


def _get_brain_claude_bin() -> str:
    """Claude Code CLI 可执行文件路径（默认 `claude`）。"""
    return _brain_cfg("CCC_BRAIN_CLAUDE_BIN", "claude").strip() or "claude"


def _get_brain_model() -> str:
    """大脑模型逻辑名（如 flash / Pro / code）。"""
    return _brain_cfg("CCC_BRAIN_MODEL", "").strip()


def _get_brain_base_url() -> str:
    """Claude Code 出口 base URL（如 http://127.0.0.1:6100）。"""
    return _brain_cfg("CCC_BRAIN_BASE_URL", "").strip()


def _get_brain_auth_token() -> str:
    """Claude Code 出口 Bearer token。"""
    return _brain_cfg("CCC_BRAIN_AUTH_TOKEN", "").strip()


def _get_brain_timeout() -> int:
    """大脑调用超时（秒，默认 300）。

    防止重度工具调用（如全局知识检索等）发生超时，上调到 300。
    """
    try:
        return int(_brain_cfg("CCC_BRAIN_TIMEOUT", "300"))
    except ValueError:
        return 300


def _get_brain_thinking() -> str:
    """大脑扩展思考开关（enabled / disabled / ""=不传）。

    T46 B5 实测：flash 经 `--thinking enabled` 后 stream-json 出现
    `redacted_thinking` 块且其 data 为可读推理文本 → 思考可达，走 B6 渲染。
    用 config 控制避免硬编码（红线 #7）；默认 enabled 以真跑通 B6。
    """
    return _brain_cfg("CCC_BRAIN_THINKING", "enabled").strip()


def _get_brain_direct() -> bool:
    """是否强制直连大模型中继 (2017 单端服务器推荐，避免 macOS 常驻守护下的 Mach 锁挂起问题)。"""
    return _brain_cfg("CCC_BRAIN_DIRECT", "").strip().lower() in ("1", "true", "yes", "on")


def _is_brain_configured() -> bool:
    """大脑代理配置是否齐全。

    `CCC_BRAIN_CLAUDE_BIN` 默认 `claude` 可用，故只校验 model / base_url / token。
    """
    return bool(_get_brain_model() and _get_brain_base_url() and _get_brain_auth_token())


# ── 知识库检索配置（T37） ──


def _get_brain_kb_enabled() -> bool:
    """大脑知识库检索开关（CCC_BRAIN_KB=1/true/yes/on 启用，默认关闭）。"""
    return _brain_cfg("CCC_BRAIN_KB", "0").strip().lower() in ("1", "true", "yes", "on")


def _get_brain_kb_index_dir() -> str:
    """BM25 索引目录（CCC_KB_INDEX_DIR；空则交由 server.kb.search 走默认 knowledge/.index/）。"""
    return _brain_cfg("CCC_KB_INDEX_DIR", "").strip()


def _get_brain_kb_top_k() -> int:
    """知识库检索 top-k（默认 3，最小 1）。"""
    try:
        return max(1, int(_brain_cfg("CCC_BRAIN_KB_TOP_K", "3")))
    except ValueError:
        return 3


def _retrieve_kb_context(message: str) -> str:
    """检索 CCC 自建知识库，返回注入 prompt 的参考段落。

    红线：只读 ``knowledge/``（server/kb BM25 索引），禁止读 qx-map / hp-kb。
    降级策略：未配置开关 / 未命中 / 检索异常 → 一律返回空串，对话照常走裸大脑。

    命中时返回形如::

        【知识库参考】
        {section}：{title}：{snippet}
        ...

    其中 title 取 doc_id 中 ``::`` 之后的部分（无 ``::`` 则用完整 doc_id）。
    """
    if not _get_brain_kb_enabled():
        return ""
    try:
        # T51：统一查询内核（与 kb MCP 同一 service），自动增量 ensure_index
        from server.kb.service import search as kb_search

        index_dir = _get_brain_kb_index_dir()
        results = kb_search(
            query=message,
            top_k=_get_brain_kb_top_k(),
            index_dir=index_dir or None,
        )
    except Exception:
        # 检索异常静默降级：不中断对话（红线 #3）
        return ""
    if not results:
        return ""
    # 引导语（T38）：明确告知优先用参考段落，避免 Claude Code 自行翻文件导致超时
    # （T37 验收观察：未加引导语时首次实测 120s 超时；引导后 14s 正常返回）
    # 引导语合并到标题行，保持 _build_prompt 注入段落结构与测试断言不变
    lines = [
        "【知识库参考】（以下为 BM25 检索命中片段，请优先据此回答；片段已含条目 id，"
        "引用时显式标注。如片段未覆盖问题，再说明信息不足——避免自行翻阅文件以控制延迟。）"
    ]
    for r in results:
        section = r.get("section", "") or "?"
        doc_id = r.get("id", "") or "?"
        title = doc_id.split("::", 1)[1] if "::" in doc_id else doc_id
        snippet = r.get("snippet", "")
        lines.append(f"{section}：{title}：{snippet}")
    return "\n".join(lines)


def _build_prompt(message: str, history: list[dict[str, Any]], thread_id: str = "") -> str:
    """组装单次 Claude Code 调用 prompt：系统人格 + 知识库参考 + 最近 N 轮历史 + 当前消息。"""
    parts: list[str] = [BRAIN_SYSTEM_PROMPT, ""]
    if thread_id:
        parts.append(f"【当前会话 ID】\n{thread_id}\n")
    # T37：知识库检索注入（命中才注入，置于系统人格与历史之间）
    kb_context = _retrieve_kb_context(message)
    if kb_context:
        parts.append(kb_context)
        parts.append("")
    recent = history[-(2 * _BRAIN_HISTORY_TURNS) :] if history else []
    if recent:
        parts.append("【历史对话】")
        for entry in recent:
            role = entry.get("role", "")
            content = entry.get("message", "")
            if role in ("user", "assistant") and content:
                parts.append(f"{role}: {content}")
        parts.append("")
    parts.append("【当前问题】")
    parts.append(message)
    return "\n".join(parts)


def _run_claude(prompt: str, timeout: int) -> tuple[bool, str, str | None]:
    """调用 Claude Code CLI。

    返回 ``(success, stdout_or_error, error_kind)``：

    - 成功 → ``(True, stdout_text, None)``
    - 超时 → ``(False, "brain timeout", "timeout")``
    - 其他失败 → ``(False, "brain failed: <detail>", "failed")``

    env 在当前进程环境基础上覆盖三个 Anthropic 出口变量，指向 6100；
    Claude Code 全局配置（``~/.claude/settings.json``）保持不动。
    """
    bin_path = _get_brain_claude_bin()
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = _get_brain_base_url()
    env["ANTHROPIC_AUTH_TOKEN"] = _get_brain_auth_token()
    env["ANTHROPIC_MODEL"] = _get_brain_model()
    try:
        proc = subprocess.run(
            [bin_path, "-p", prompt, "--output-format", "text", "-y"],
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return (False, "brain timeout", "timeout")
    except (OSError, FileNotFoundError) as exc:
        return (False, f"brain failed: {exc}", "failed")

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[:200] or f"exit {proc.returncode}"
        return (False, f"brain failed: {detail}", "failed")
    reply = (proc.stdout or "").strip()
    if not reply:
        return (False, "brain returned empty content", "failed")
    return (True, reply, None)


def call_brain(
    message: str,
    history: list[dict[str, Any]],
    session_key: str | None = None,
    model: str | None = None,
) -> tuple[bool, str, int]:
    """大脑 Agent 对话入口（供 ``/conversation`` 调用）。

    返回 ``(success, reply_or_error, status_code)``：

    - 未配置 → ``(False, "brain not configured ...", 503)``
    - 忙（总并发超限 / 同会话进行中） → ``(False, "brain busy, try later", 503)``
    - 超时 → ``(False, "brain timeout", 504)``
    - 失败 → ``(False, error_msg, 502)``
    - 成功 → ``(True, reply, 200)``

    T44：``session_key`` 按会话分锁（同会话串行、跨会话可并发，上限见
    CCC_BRAIN_MAX_CONCURRENCY）；``model`` 为会话级模型覆盖（缺省走环境变量）。
    """
    if not _is_brain_configured():
        return (
            False,
            "brain not configured (CCC_BRAIN_MODEL / CCC_BRAIN_BASE_URL / CCC_BRAIN_AUTH_TOKEN)",
            503,
        )
    prompt = _build_prompt(message, history, thread_id=session_key or "")
    # 非阻塞获取会话槽位，忙则立即拒绝（不排队等待，避免长阻塞）
    key = session_key or ""
    if not _acquire_brain_slot(key):
        return (False, "brain busy, try later", 503)
    try:
        _model_override.model = (model or "").strip()
        ok, out, kind = _run_claude(prompt, _get_brain_timeout())
    finally:
        _model_override.model = ""
        _release_brain_slot(key)
    if ok:
        return (True, out, 200)
    if kind == "timeout":
        return (False, out, 504)
    return (False, out, 502)


# ── 流式输出（T41：SSE 逐事件转发） ──


def _normalize_stream_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """claude stream-json 单行事件 → 归一化 ``(event, payload)`` 或 None（跳过）。

    映射：
    - ``system/init``      → ``meta``（模型 / 工具 / MCP / skills 可见）
    - ``assistant`` 块     → ``thinking`` / ``tool_use`` / ``text``
    - ``user`` 块          → ``tool_result``（工具结果回显，截断至 2000 字符）
    - ``stream_event``     → ``text``（兼容分片流，未启用时不出现）
    - ``result``           → ``done``（is_error 终结，附最终文本）
    - 其他（system/status 等）→ None 跳过
    """
    etype = event.get("type")
    if etype == "system" and event.get("subtype") == "init":
        return (
            "meta",
            {
                "model": event.get("model", "") or "",
                "tools": event.get("tools", []) or [],
                "mcp_servers": event.get("mcp_servers", []) or [],
                "skills": event.get("skills", []) or [],
            },
        )
    if etype == "assistant":
        msg = event.get("message", {}) or {}
        # T46 C8：assistant.message.content 可能含多个同类型块。text 块需完整拼接
        # （不丢字/不重复），其他类型（thinking/tool_use）取首个。编排侧保证一次
        # 事件只产出一种语义事件；text 拼接后一次性输出。
        blocks = msg.get("content", []) or []
        # 收集非 text 块的优先级：thinking > tool_use（按首个出现的特别事件）
        special = None
        for block in blocks:
            btype = block.get("type")
            if btype in ("thinking", "redacted_thinking"):
                special = ("thinking", {"data": block.get("data", "") or ""})
                break
            if btype == "tool_use":
                special = (
                    "tool_use",
                    {
                        "id": block.get("id", "") or "",
                        "name": block.get("name", "") or "",
                        "input": block.get("input", {}) or {},
                    },
                )
                break
        text_parts = [
            b.get("text", "") or ""
            for b in blocks
            if b.get("type") == "text"
        ]
        if text_parts:
            # 有 text → 输出完整拼接的 text 事件（thinking/tool_use 由单块事件承载）
            return ("text", {"text": "".join(text_parts)})
        # 无 text → 输出首个特别事件；两者皆无则不产出
        if special is not None:
            return special
        # 退化：content 里既无 text 也无特别块 → 尝试逐块取 text 兜底
        for block in blocks:
            btype = block.get("type")
            if btype in ("thinking", "redacted_thinking"):
                return ("thinking", {"data": block.get("data", "") or ""})
            if btype == "tool_use":
                return (
                    "tool_use",
                    {
                        "id": block.get("id", "") or "",
                        "name": block.get("name", "") or "",
                        "input": block.get("input", {}) or {},
                    },
                )
        return None
    if etype == "user":
        msg = event.get("message", {}) or {}
        for block in msg.get("content", []) or []:
            if block.get("type") == "tool_result":
                content = block.get("content", "")
                if isinstance(content, list):
                    content = " ".join(c if isinstance(c, str) else (c.get("text", "") or "") for c in content)
                return (
                    "tool_result",
                    {
                        "tool_use_id": block.get("tool_use_id", "") or "",
                        "content": str(content)[:2000],
                    },
                )
        return None
    if etype == "result":
        is_error = bool(event.get("is_error"))
        return (
            "done",
            {
                "is_error": is_error,
                "text": event.get("result", "") or "",
                "error": event.get("api_error_status") or ("" if not is_error else "brain failed"),
            },
        )
    if etype == "stream_event":
        ev = event.get("event") or {}
        if ev.get("type") == "content_block_delta":
            delta = ev.get("delta") or {}
            if delta.get("type") == "text_delta":
                return ("text", {"text": delta.get("text", "") or ""})
        return None
    return None


def _terminate_proc(proc: subprocess.Popen) -> None:
    """确保子进程及整个进程组结束：运行中则 killpg + wait（超时/断连兜底）。

    自我误杀隔离：``preexec_fn=os.setsid`` 的 fork→setsid 竞态窗口内，子进程仍可能
    属于本服务端进程组，直接 killpg 会连 Web 自身一起 SIGKILL。故 killpg 前校验
    ``pgid > 1`` 且 ``pgid != os.getpgrp()``；无 pid / 非法 pgid / 取 pgid 失败一律
    退化为 ``proc.kill()``。
    """
    if proc.poll() is None:
        try:
            pid = getattr(proc, "pid", None)
            if pid is None:
                proc.kill()
            else:
                try:
                    pgid = os.getpgid(pid)
                    if pgid > 1 and pgid != os.getpgrp():
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        proc.kill()
                except OSError:
                    proc.kill()
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
    try:
        proc.wait(timeout=1.0)
    except Exception:
        pass


def _stream_claude(prompt: str, timeout: int | None = None):
    """以 stream-json 调用 Claude Code CLI，逐事件 yield 归一化 ``(event, payload)``。

    与 ``_run_claude`` 共用环境变量注入（6100 出口）。stdout 由守护线程逐行读取，
    主循环按剩余超时等待：超时 → kill 并 yield ``error(504)``；
    spawn 失败 → ``error(502)``；正常结束 → 末尾 ``done`` 事件（result 行）。
    """
    if _get_brain_direct():
        yield from _stream_relay_direct(prompt)
        return

    timeout = _get_brain_timeout() if timeout is None else timeout
    bin_path = _get_brain_claude_bin()
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = _get_brain_base_url()
    env["ANTHROPIC_AUTH_TOKEN"] = _get_brain_auth_token()
    env["ANTHROPIC_MODEL"] = _effective_model()
    # T46 B5：扩展思考可由 `--thinking <enabled|disabled>` 控制（可读 redacted_thinking）。
    # 空白则不传（模型/中继不支持时后端可静态关闭，避免 CLI 报错）。
    _thinking = _get_brain_thinking()
    _thinking_args = (
        ["--thinking", _thinking] if _thinking in ("enabled", "disabled") else []
    )
    try:
        proc = subprocess.Popen(
            [bin_path, "-p", prompt, "--output-format", "stream-json", "--verbose"]
            + _thinking_args
            + ["-y"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )
    except (OSError, FileNotFoundError) as exc:
        # Fallback：当本地不具备 claude CLI 时（例如在 2017 单端服务器上），直连中继 (6100/6102/DSH) 获取大模型大脑流
        yield from _stream_relay_direct(prompt)
        return

    lines_q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _read_lines():
        try:
            for line in proc.stdout or []:
                lines_q.put(("line", line))
        except Exception as exc:  # pragma: no cover - 读线程异常兜底
            lines_q.put(("exc", exc))
        finally:
            lines_q.put(("eof", None))

    threading.Thread(target=_read_lines, daemon=True).start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_proc(proc)
                yield ("error", {"status": 504, "message": "brain timeout"})
                return
            try:
                kind, payload = lines_q.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                continue
            if kind == "exc":
                _terminate_proc(proc)
                yield ("error", {"status": 502, "message": f"brain failed: {payload}"})
                return
            if kind == "eof":
                break
            line = (payload or "").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            normalized = _normalize_stream_event(event)
            if normalized is None:
                continue
            yield normalized
            if normalized[0] == "done":
                return
    finally:
        _terminate_proc(proc)


def _stream_relay_direct(prompt: str):
    """2017 本地直连中继 (6100/6102/DSH) 流式大模型生成器。

    支持双核转译（Anthropic / OpenAI），消除了冷启动子进程的全部环境要求：
    - 6100 端口：走 Anthropic 协议 (请求 /v1/messages，转译 content_block_delta)
    - 6102 / 3080 端口：走 OpenAI 协议 (请求 /v1/chat/completions，支持 DeepSeek R1 reasoning_content 思考流转译)
    """

    base_url = _get_brain_base_url() or "http://127.0.0.1:6100"
    model = _effective_model() or "deepseek-chat"
    auth_token = _get_brain_auth_token()

    m = re.match(r"http://([^:/]+):(\d+)", base_url)
    if m:
        host, port = m.group(1), int(m.group(2))
    else:
        host, port = "127.0.0.1", 6100

    is_anthropic = (port == 6100) or ("6100" in base_url)

    headers = {
        "Content-Type": "application/json",
    }

    if is_anthropic:
        if auth_token:
            headers["x-api-key"] = auth_token
        headers["anthropic-version"] = "2023-06-01"
        body = json.dumps({
            "model": model if "claude" in model else "claude-3-5-sonnet-latest",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "stream": True
        }, ensure_ascii=False).encode("utf-8")
        path = "/v1/messages"
    else:
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True
        }, ensure_ascii=False).encode("utf-8")
        path = "/v1/chat/completions"

    conn = None
    try:
        conn = http.client.HTTPConnection(host, port, timeout=120)
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        if resp.status != 200:
            err_msg = resp.read().decode("utf-8", errors="replace")
            yield ("error", {"status": resp.status, "message": f"DSH Relay error: {err_msg}"})
            return

        yield ("meta", {"model": model, "tools": [], "mcp_servers": [], "skills": []})

        buffer = b""
        done_triggered = False
        while not done_triggered:
            chunk = resp.read(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line_bytes, buffer = buffer.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        done_triggered = True
                        break
                    try:
                        data = json.loads(data_str)
                        if is_anthropic:
                            etype = data.get("type")
                            if etype == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield ("text", {"text": delta.get("text", "")})
                            elif etype == "message_delta":
                                delta = data.get("delta", {})
                                if delta.get("stop_reason"):
                                    done_triggered = True
                                    break
                        else:
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                reasoning = delta.get("reasoning_content", "")
                                if reasoning:
                                    yield ("thinking", {"data": reasoning})
                                if content:
                                    yield ("text", {"text": content})
                    except Exception:
                        pass
        yield ("done", {"is_error": False, "text": ""})
    except Exception as exc:
        yield ("error", {"status": 502, "message": f"direct relay connection failed: {exc}"})
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def stream_brain_events(

    message: str,
    history: list[dict[str, Any]],
    session_key: str | None = None,
    model: str | None = None,
):
    """流式大脑对话入口（供 ``/conversation`` stream 分支调用）。

    以 generator 逐事件产出 ``(event, payload)``（meta / thinking / tool_use /
    text / tool_result / done / error），SSE 格式由 HTTP 层负责。

    与 ``call_brain`` 一致：未配置 → ``error(503)``；忙 → ``error(503)``；
    超时 → ``error(504)``；失败 → ``error(502)``。锁在消费期间持有，
    generator 关闭（客户端断开/异常）时释放。

    T44：``session_key`` 按会话分锁；``model`` 为会话级模型覆盖。
    """
    if not _is_brain_configured():
        yield (
            "error",
            {
                "status": 503,
                "message": "brain not configured (CCC_BRAIN_MODEL / CCC_BRAIN_BASE_URL / CCC_BRAIN_AUTH_TOKEN)",
            },
        )
        return
    prompt = _build_prompt(message, history, thread_id=session_key or "")
    key = session_key or ""
    if not _acquire_brain_slot(key):
        yield ("error", {"status": 503, "message": "brain busy, try later"})
        return
    try:
        _model_override.model = (model or "").strip()
        yield from _stream_claude(prompt)
    finally:
        _model_override.model = ""
        _release_brain_slot(key)
