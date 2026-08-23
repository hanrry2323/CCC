"""wall.py — DSH 监控墙数据引擎（并入 CCC，源 dsh-wall v0.3.4 等价移植）。

移交事实源：~/program/apps/dsh-wall/docs/HANDOVER.md（commit 782d960）；
架构与踩坑记录：同仓 docs/ARCHITECTURE.md。本模块 = 原 dsh_wall_reader.py +
dsh_wall_server.py 的状态管理/RPC 部分，逻辑零改动合并为单文件，供
server/web/server.py 以 `/wall/*` 前缀挂线（ccc-plan-045 P1）。

数据流：
- 后台线程每 POLL_INTERVAL 秒 mtime 快检 ~/.dsh/sessions/**/session.jsonl.zstd，
  变化才 zstd -d 解压、按行 offset 增量解析事件 → Session 状态机；
- GET 快照/SSE 从 Condition 保护的状态取全量快照；SSE 侧做字符串 diff 无变化不推；
- 回写只走 DSH 官方 RPC（127.0.0.1:3080/api/<method>），失败静默降级。

红线（HANDOVER §4.3）：零碰 DSH 核心、纯本地文件只读解析 + 官方 RPC 回写；
审批/提问帧轮询、直连 DSH WS 等路线已实证不可行，勿再尝试。
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

# ── reader 常量（原样保留；调参见 HANDOVER §4.1）─────────────────────

_ZSTD_CANDIDATES = ("zstd", "/usr/local/bin/zstd", "/opt/homebrew/bin/zstd")

CCC_MARKERS = ("program-CCC",)
QUANT_MARKERS = ("ZCodeProject",)
ACTIVE_WINDOW = 3600  # 秒：文件 mtime 在此窗口内纳入扫描（新会话）
ENDED_KEEP = 1800  # 秒：完成/错误会话结束后保留展示窗口（未读只留最近 30 分钟）
IDLE_ACTIVE = 90.0  # 秒：无事件超过此时间视为结束
IDLE_LONG = 300.0  # 秒：停在中间事件（长工具执行）超过此时间视为结束
STALL_HINT = 120.0  # 秒：active 且空闲超此值且末块为工具调用 → 前台「可能等待输入」提示
SCAN_INTERVAL = 6.0  # 秒：全量目录扫描间隔（中间轮只 stat 已知文件）

POLL_INTERVAL = 0.6  # 秒：mtime 快检轮询（文件变化才解压，成本极低）
HEARTBEAT = 15.0  # 秒：SSE 心跳，保持长连接

_scan_cache: dict[str, Any] = {"ts": 0.0, "files": None, "rejects": {}}

# DSH 归档集缓存（只读 workspace.json，mtime 未变化不重读）
_arch_cache: dict[str, Any] = {"mtime": 0.0, "archived": set()}


def dsh_workspace_file() -> Path:
    return dsh_data_root() / "storages" / "workspace.json"


def archived_session_ids() -> set[str]:
    """读取 DSH 归档会话集（global.archivedSessionIds）。只读，解析失败保留旧缓存。"""
    p = dsh_workspace_file()
    try:
        mt = p.stat().st_mtime
    except OSError:
        return _arch_cache["archived"]
    if mt != _arch_cache["mtime"]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ids = (data.get("global") or {}).get("archivedSessionIds") or []
            _arch_cache["archived"] = {str(x) for x in ids}
            _arch_cache["mtime"] = mt
        except (OSError, json.JSONDecodeError):
            pass  # 文件半写/损坏：沿用上次缓存，下轮 mtime 变化再试
    return _arch_cache["archived"]


def invalidate_archive_cache() -> None:
    """墙代发归档成功后调用：强制下轮重读归档集，过滤立即生效。"""
    _arch_cache["mtime"] = 0.0


def dsh_data_root() -> Path:
    raw = os.environ.get("DSH_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / ".dsh"


def _decompress(path: Path) -> str:
    for exe in _ZSTD_CANDIDATES:
        try:
            r = subprocess.run(
                [exe, "-d", "-c", str(path)],
                capture_output=True,
                timeout=20,
            )
            if r.returncode == 0:
                return r.stdout.decode("utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired):
            continue
    return ""


def classify_source(cwd: str) -> str | None:
    if not cwd:
        return None
    if any(m in cwd for m in CCC_MARKERS):
        return "ccc"
    if any(m in cwd for m in QUANT_MARKERS):
        return "quant"
    return "manual"  # 手动工作区（qx-map/DeepSeek 等）同样显示


class Session:
    """单个 DSH 会话的解析状态。"""

    def __init__(self, session_id: str, fpath: Path):
        self.id = session_id
        self.path = fpath
        self.cwd = ""
        self.title = ""
        self.source: str | None = None
        self.model = ""
        self.created_ms: int | None = None
        self.last_ms: int | None = None
        self.turn = 0
        self.step = 0
        self.status = "active"
        self.reason = ""
        self.ended_ms: int | None = None  # 状态变为 done/error 的时刻
        self.stalled = False  # active 且长期无事件且末块为工具调用 → 前台停滞提示
        self.blocks: list[dict[str, Any]] = []
        self.tokens = {"input": 0, "output": 0, "cache": 0}
        self._offset = 0
        self._seen_steps: set[int] = set()
        self._pending_tool: str | None = None
        self._last_type = ""  # 最后事件类型：finish / turn_end / other
        self._last_finish_kind = ""  # 最后结束类事件结果：error / ok
        self.ended = False  # 已见 session/end-seed（DSH 确定性关闭会话）→ 立即判结束
        self._mtime = 0.0  # 文件 mtime 缓存（未变化则跳过解压）

    @property
    def elapsed_sec(self) -> float:
        if self.created_ms is None or self.last_ms is None:
            return 0.0
        return round((self.last_ms - self.created_ms) / 1000.0, 1)

    def add_block(self, btype: str, text: str) -> None:
        if not text.strip():
            return
        self.blocks.append({"type": btype, "text": text})


def _event_list(raw: str) -> list[dict[str, Any]]:
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _first_text_of(content: Any) -> str:
    for c in content or []:
        if c.get("type") == "text" and c.get("text", "").strip():
            return c["text"].strip()
    return ""


# 异常终止类 reason kind：报错 + 中断 + 中止 + 超 token 上限，都判异常并在墙上前台红色提示
_ABNORMAL_KINDS = {"error", "interrupted", "aborted", "max-tokens"}


def _reason_label(kind: str, reason: dict[str, Any]) -> str:
    """异常终止 reason → 前台展示文案；正常 kind 返回空串。"""
    if kind == "error":
        err = reason.get("error") or reason.get("failure") or {}
        return str(err.get("message") or err.get("type") or reason.get("message") or "错误")[:120]
    if kind == "interrupted":
        return "中断"
    if kind == "aborted":
        user = (reason.get("reason") or {}).get("kind") == "user"
        return "中止（用户）" if user else "中止"
    if kind == "max-tokens":
        return "达到 token 上限"
    return ""


def _apply_events(s: Session, events: list[dict[str, Any]]) -> None:
    for ev in events:
        t = ev.get("type", "")
        data = ev.get("data") or {}
        if t == "session":
            s.cwd = ev.get("cwd", "")
            s.created_ms = ev.get("createdAt")
            s.source = classify_source(s.cwd)
        elif t == "session/title":
            s.title = data.get("title", "")
        elif t == "request/header":
            cfg = (data.get("header") or {}).get("config") or {}
            if cfg.get("provider"):
                s.model = f"{cfg.get('provider')}/{cfg.get('model', '')}"
        elif t == "user/message":
            # 每条用户消息都上墙（含追问）；与上一条完全相同且中间无新块时视为重复事件忽略。
            # harness 内部注入（system-reminder/runtime-context 等）不是真用户输入，不上墙。
            txt = _first_text_of(data.get("content"))
            if not txt or txt.startswith(("<system-reminder>", "Current runtime context")):
                continue
            last_user_idx = None
            for i in range(len(s.blocks) - 1, -1, -1):
                if s.blocks[i]["type"] == "user":
                    last_user_idx = i
                    break
            if last_user_idx is None:
                s.add_block("user", txt)
            else:
                has_new_between = any(
                    s.blocks[i]["type"] != "user"
                    for i in range(last_user_idx + 1, len(s.blocks))
                )
                if has_new_between or s.blocks[last_user_idx]["text"] != txt:
                    s.add_block("user", txt)
                    s.blocks[-1]["followup"] = True  # 前台标记「追问」
        elif t == "step/start":
            n = int(data.get("step", 0))
            s.step = max(s.step, n)
            if n not in s._seen_steps:
                s._seen_steps.add(n)
                s.add_block("step", str(n))
        elif t == "step/end":
            pass
        elif t == "turn/start":
            s.turn = max(s.turn, int(data.get("turn", 0)))
            s.reason = ""  # 新轮开始 = 继续执行，清掉历史错误
        elif t == "turn/end":
            s._last_type = "turn_end"
            reason = data.get("reason") or {}
            kind = reason.get("kind", "")
            if kind in _ABNORMAL_KINDS:
                s._last_finish_kind = "error"
                s.reason = _reason_label(kind, reason)
            else:
                s._last_finish_kind = "ok"
                s.reason = ""
        elif t == "assistant/chunk":
            chunk = data.get("chunk") or {}
            ctype = chunk.get("type")
            if ctype == "text-delta" and chunk.get("text"):
                s.add_block("assistant", chunk["text"])
            elif ctype == "reasoning-delta" and chunk.get("text"):
                s.add_block("reasoning", chunk["text"])
            elif ctype == "tool-call-delta":
                s._pending_tool = chunk.get("name", "") or s._pending_tool
            elif ctype == "block-start":
                pass
            elif ctype == "block-end":
                block = chunk.get("block") or {}
                if block.get("type") == "reasoning" and block.get("text"):
                    s.add_block("reasoning", block["text"])
            elif ctype == "usage":
                u = chunk.get("usage") or {}
                s.tokens["input"] += int(u.get("inputTokens", 0) or 0)
                s.tokens["output"] += int(u.get("outputTokens", 0) or 0)
                s.tokens["cache"] += int(u.get("cacheReadTokens", 0) or 0)
            elif ctype == "finish":
                s._last_type = "finish"
                reason = chunk.get("reason") or {}
                kind = reason.get("kind", "")
                if kind in _ABNORMAL_KINDS:
                    s._last_finish_kind = "error"
                    s.reason = _reason_label(kind, reason)
                else:
                    s._last_finish_kind = "ok"
                    s.reason = ""
        elif t == "tool/call":
            name = data.get("name", "")
            args = data.get("arguments", "")
            s.add_block("tool", f"{name} {args}")
        elif t == "assistant/message":
            txt = ""
            for c in (data.get("message") or {}).get("content") or []:
                if c.get("type") == "text":
                    txt = c.get("text", "")
                    break
            if txt:
                s.add_block("assistant", txt)
        elif t == "session/end-seed":
            # DSH 确定性收尾事件：会话已关闭。标记 ended，状态机立即判 done/error，
            # 不再被通用兜底覆盖成 other（否则已完成会话要空等 300s 才翻 done）。
            s.ended = True
            s._last_type = "turn_end"
        if ev.get("time"):
            s.last_ms = ev["time"]
        if t not in ("assistant/chunk", "turn/end", "session/end-seed"):
            s._last_type = "other"


def _discover_session_files(prev: dict[str, Session]) -> dict[str, tuple[Path, float]]:
    global _scan_cache
    now = time.time()
    if _scan_cache["files"] is None or now - _scan_cache["ts"] > SCAN_INTERVAL:
        # 全量扫描（rglob + stat），每 SCAN_INTERVAL 秒一次
        root = dsh_data_root() / "sessions"
        files: dict[str, tuple[Path, float]] = {}
        if root.is_dir():
            cutoff = now - ACTIVE_WINDOW
            rejects = _scan_cache["rejects"]
            for p in root.rglob("session.jsonl.zstd"):
                sid = p.parent.name
                mt = p.stat().st_mtime
                # 已剔除会话未变化：跳过（避免每轮重解压）
                if sid in rejects and rejects[sid] == mt:
                    continue
                # 已在列表中的会话不因 mtime 窗口剔除（防抖动）；新会话才要求窗口内
                if mt < cutoff and sid not in prev:
                    continue
                files[sid] = (p, mt)
        _scan_cache = {"ts": now, "files": files, "rejects": {}}
        return files
    # 轻量轮：只 stat 已知文件（微秒级），不重新遍历目录
    files = {}
    rejects = _scan_cache["rejects"]
    for sid, (p, _mt) in _scan_cache["files"].items():
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue  # 文件消失，下一轮全扫描会处理
        if sid in rejects and rejects[sid] == mt:
            continue  # 不合格文件未变化：跳过，避免每轮重复解压
        files[sid] = (p, mt)
    return files


def _recompute_status(s: Session, now: float) -> None:
    """状态机：由空闲时长 + 最后事件类型判定状态（无需解压文件）。"""
    if s.ended:
        # 已见 session/end-seed：DSH 确定性关闭会话，无需等空闲窗口，立即判结束
        s.stalled = False
        s.status = "error" if s._last_finish_kind == "error" else "done"
        if s._last_finish_kind != "error":
            s.reason = ""
        if s.ended_ms is None:
            s.ended_ms = s.last_ms or int(now * 1000)
        return
    if s.last_ms is None:
        s.stalled = False
        return
    idle = now - s.last_ms / 1000.0
    if idle <= IDLE_ACTIVE:
        s.status = "active"
    elif s._last_type in ("finish", "turn_end") and s._last_finish_kind == "error":
        s.status = "error"
    elif s._last_type in ("finish", "turn_end"):
        s.status = "done"
        s.reason = ""
    elif idle > IDLE_LONG:
        s.status = "done"
        s.reason = ""
    else:
        s.status = "active"  # 停在长工具执行（sleep/ssh 等）或等待中，保持运行态
    # 启发式停滞提示：仅运行中 + 空闲超阈值 + 末块为工具调用（可能卡等待输入/慢工具）
    s.stalled = (
        s.status == "active"
        and idle >= STALL_HINT
        and bool(s.blocks)
        and s.blocks[-1]["type"] == "tool"
    )
    if s.status in ("done", "error") and s.ended_ms is None:
        s.ended_ms = s.last_ms or int(now * 1000)
    if s.status == "active":
        s.ended_ms = None  # 恢复运行则清除结束时间


def refresh_sessions(prev: dict[str, Session]) -> tuple[dict[str, Session], list[str]]:
    """轮询刷新：mtime 快检（毫秒级），文件未变化只重算状态，变化才解压解析。

    返回 (会话表, 消失的会话id)。"""
    now = time.time()
    archived = archived_session_ids()  # DSH 侧已归档 = 已处理 → 墙不再显示
    cur: dict[str, Session] = {}
    for sid, (fpath, mt) in _discover_session_files(prev).items():
        if sid in archived:
            continue
        s = prev.get(sid)
        if s is None:
            s = Session(sid, fpath)
        # 文件未变化：跳过解压，只重算状态（低成本）
        if s._mtime == mt and s._offset > 0:
            _recompute_status(s, now)
            if _keep_after_end(s, now):
                cur[sid] = s
            continue
        s._mtime = mt
        try:
            raw = _decompress(fpath)
        except Exception:
            raw = ""
        if not raw:
            if sid in prev:  # 解压失败：保留旧状态，不让会话闪烁消失
                cur[sid] = s
            continue
        if s._offset == 0:
            first = next(
                (e for e in _event_list(raw) if e.get("type") == "session"), None
            )
            if first is None or classify_source(first.get("cwd", "")) is None:
                _scan_cache["rejects"][sid] = mt  # 不合格：缓存 mtime，避免每轮重解压
                continue
        lines = raw.splitlines()
        if len(lines) > s._offset:
            _apply_events(s, _event_list("\n".join(lines[s._offset :])))
            s._offset = len(lines)
        _recompute_status(s, now)
        if not _keep_after_end(s, now):
            _scan_cache["rejects"][sid] = mt  # 超展示窗口：剔除并缓存，mtime 变化才重评
            continue  # 完成超过展示窗口的会话不再返回（未读只留最近 30 分钟）
        if len(s.blocks) > 2000:
            s.blocks = s.blocks[-2000:]
        cur[sid] = s
    gone = [sid for sid in prev if sid not in cur]
    return cur, gone


def _keep_after_end(s: Session, now: float) -> bool:
    """完成/错误会话只在结束后的展示窗口内返回。"""
    if s.status in ("done", "error") and s.ended_ms:
        return now - s.ended_ms / 1000.0 <= ENDED_KEEP
    return True


STEP_WINDOW = 8  # 快照只保留最后 N 步的内容（折叠更早，省传输 + 同步准确）


def _last_steps(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从尾部收集最后 STEP_WINDOW 个 step 段；无 step 块或不足窗口则全保留。"""
    n = len(blocks)
    if n == 0:
        return blocks
    # 无 step 块（纯对话会话）：内容少，全保留
    has_step = any(b["type"] == "step" for b in blocks)
    if not has_step:
        return blocks
    idx = n
    seen = 0
    for i in range(n - 1, -1, -1):
        if blocks[i]["type"] == "step":
            seen += 1
            if seen == STEP_WINDOW:
                idx = i
                break
    if seen < STEP_WINDOW:
        return blocks
    folded = blocks[:idx]
    kept = blocks[idx:]
    return [{"type": "fold", "text": f"…更早 {len(folded)} 个内容块已折叠"}] + kept


def snapshot(s: Session) -> dict[str, Any]:
    return {
        "id": s.id,
        "title": s.title or s.id[:20],
        "source": s.source,
        "model": s.model,
        "turn": s.turn,
        "step": s.step,
        "elapsed": s.elapsed_sec,
        "status": s.status,
        "reason": s.reason,
        "stalled": s.stalled,
        "blocks": _last_steps(s.blocks),
        "tokens": s.tokens,
        "last_ms": s.last_ms,
        "started_ms": s.created_ms,
        "ended_ms": s.ended_ms,
        "updated": time.time(),
    }


# ── 服务端状态管理 + DSH RPC（源自 dsh_wall_server.py，等价搬入）──────────

_lock = threading.Lock()
_sessions: dict = {}
_cond = threading.Condition(_lock)
_poll_started = False


def _poll_loop() -> None:
    global _sessions
    while True:
        try:
            with _cond:
                _sessions, _ = refresh_sessions(_sessions)
                _cond.notify_all()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


def ensure_poll_started() -> None:
    """启动后台快照轮询线程（幂等）；由 server.py serve_forever 调用一次。"""
    global _poll_started
    with _lock:
        if _poll_started:
            return
        _poll_started = True
    threading.Thread(target=_poll_loop, daemon=True, name="ccc-wall-poll").start()


def state_payload() -> dict:
    """当前全量快照（不含 ts；SSE diff 比较用原始态，避免 ts 抖动破坏 diff）。"""
    with _cond:
        return {
            "sessions": [snapshot(s) for s in _sessions.values()],
            "archived": sorted(archived_session_ids()),
        }


def wait_state_payload(timeout: float) -> dict:
    """等待状态变化（或超时）后返回全量快照；供 SSE 长连接挂起使用。"""
    with _cond:
        _cond.wait(timeout=timeout)
        return {
            "sessions": [snapshot(s) for s in _sessions.values()],
            "archived": sorted(archived_session_ids()),
        }


def active_payload() -> dict:
    """GET 快照端点响应体（含 ts）。"""
    return {**state_payload(), "ts": time.time()}


def _iana_tz() -> str:
    """取本机 IANA 时区名（DSH 校验要求 IANA Area/Location，传 offset 会被拒）。"""
    try:
        p = Path("/etc/localtime").resolve()
        return p.parent.name + "/" + p.name
    except Exception:
        return "UTC"


def dsh_rpc(method: str, payload: dict, timeout: int = 5) -> tuple[bool, str]:
    """向 DSH Web 官方 RPC（127.0.0.1:3080/api/<method>）转发一次 unary 调用。

    信封格式见 HANDOVER §4.2（已实证可用）。失败返回 (False, 原因)。"""
    body = json.dumps({
        "type": "client-request",
        "rpcId": f"wall-{int(time.time() * 1000)}",
        "method": method,
        "payload": payload,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:3080/api/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
        if resp.get("result", {}).get("ok"):
            return True, ""
        err = resp.get("result", {}).get("error") or {}
        return False, str(err.get("message") or err or "rpc not ok")
    except Exception as e:
        return False, str(e)


def dsh_prompt(session_id: str, text: str) -> tuple[bool, str]:
    """格内对话：转发 session.prompt（queue 模式，排队追加不打断当前执行）。"""
    payload = {
        "sessionId": session_id,
        "mode": "queue",
        "content": [{"type": "text", "text": text}],
        "clientTimeZone": _iana_tz(),
    }
    return dsh_rpc("session.prompt", payload)


def dsh_archive(session_id: str) -> tuple[bool, str]:
    """归档会话：转发 DSH 官方 workspace.archiveSession。（UI 已停用，端点保留）"""
    ok, err = dsh_rpc("workspace.archiveSession", {"sessionId": session_id})
    if ok:
        invalidate_archive_cache()  # 过滤立即生效，不等 mtime 轮询
    return ok, err
