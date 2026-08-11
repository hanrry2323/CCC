"""M1 对话桥（ccc-plan-027）：原版 Claude Code 壳服务。

定位：对话页后端直连 M1 Claude Code CLI——不带 CCC 大脑人格、不带 KB 检索、
不带模型档位/中转站（6100 relay）。工作目录 = 项目在 M1 的路径（registry.yaml
的 ``paths.m1``），Claude 自己读项目 CLAUDE.md/文件，和在 CLI 里对话一致。

接口（端口 7799，局域网，Bearer 鉴权）：
    POST /chat {message, thread_id, project}            → SSE 流式
    GET  /chat/history?project=&thread_id=&after=       → {messages, seq}
    GET  /projects/<project>/threads                    → {threads: [...]}

环境变量：
    CCC_CHAT_BRIDGE_PORT    监听端口（默认 7799）
    CCC_CHAT_BRIDGE_TOKEN   鉴权 token（2017 代理注入；空则不鉴权）
    CCC_CHAT_DATA_DIR       对话历史目录（默认 ~/.ccc-chat）
    CCC_CHAT_CLAUDE_BIN     claude 可执行（默认 `claude`）
    CCC_CHAT_CONTEXT        1 时在 prompt 注入「CCC 体系项目语境」（默认关）
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

from server.web.session_store import append_messages, list_threads, load_thread

DEFAULT_PORT = 7799


def _project_roots() -> dict[str, str]:
    """registry.yaml 项目 → M1 路径（paths.m1），CCC 兜底本仓。"""
    out: dict[str, str] = {}
    try:
        from server.board.registry import load_projects

        for p in load_projects():
            if not p.prefix:
                continue
            roots = p.paths or {}
            m1 = roots.get("m1") or roots.get("m1-program")
            if m1:
                out[p.prefix] = str(m1)
    except Exception:
        pass
    out.setdefault("ccc", str(Path(__file__).resolve().parents[2]))
    return out


def _claude_bin() -> str:
    env = os.environ.get("CCC_CHAT_CLAUDE_BIN", "").strip()
    if env:
        return env
    candidates = (
        "claude",
        str(Path.home() / ".npm-global" / "bin" / "claude"),
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
    )
    for cand in candidates:
        try:
            subprocess.run([cand, "--version"], capture_output=True, timeout=5)
            return cand
        except Exception:
            continue
    return candidates[1]  # 兜底 M1 npm-global（bridge 部署在 M1）


def _context_inject(project: str) -> str:
    if os.environ.get("CCC_CHAT_CONTEXT", "").strip().lower() not in ("1", "true", "yes", "on"):
        return ""
    return f"（你在 CCC 体系的项目 {project} 中对话；项目文件已在当前工作目录。）\n"


def _claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def _cwd_encode(path: str) -> str:
    """Claude 原生会话目录编码：/Users/apple/program/CCC → -Users-apple-program-CCC。"""
    return "-" + path.lstrip("/").replace("/", "-")


def _parse_claude_jsonl(path: Path) -> list[dict[str, str]]:
    """解析 Claude 原生 jsonl → [{role, content}]（仅 user/assistant 文本）。"""
    out: list[dict[str, str]] = []
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if d.get("type") not in ("user", "assistant"):
                continue
            if d.get("isMeta") or d.get("isSidechain"):
                continue
            m = d.get("message")
            c = m.get("content") if isinstance(m, dict) else m
            if isinstance(c, list):
                text = "".join(
                    x.get("text", "")
                    for x in c
                    if isinstance(x, dict) and x.get("type") == "text"
                )
            else:
                text = str(c or "")
            text = text.strip()
            if text and not text.startswith("<"):
                out.append({"role": d["type"], "content": text})
    except OSError:
        pass
    return out


def _build_prompt(project: str, history: list[dict[str, Any]], message: str) -> str:
    parts = [_context_inject(project)]
    for m in history:
        role = "Human" if m.get("role") == "user" else "Assistant"
        parts.append(f"{role}: {m.get('message') or m.get('content') or ''}")
    parts.append(f"Human: {message}")
    parts.append("Assistant: ")
    return "\n\n".join(parts)


def _run_claude_stream(prompt: str, project_root: str):
    """调 M1 claude CLI（stream-json），逐事件产出 (type, payload) 或 None 结束。"""
    env = dict(os.environ)
    env.pop("ANTHROPIC_BASE_URL", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("ANTHROPIC_API_KEY", None)
    claude_bin = _claude_bin()
    claude_cmd = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    # launchd 环境下 claude 会挂起（mach 锁等待）；用 launchctl asuser 包装回用户上下文
    if os.environ.get("CCC_CHAT_BRIDGE_ASUSER", "").strip().lower() in ("1", "true", "yes", "on"):
        home = str(Path.home())
        claude_cmd = [
            "launchctl",
            "asuser",
            str(os.getuid()),
            "env",
            f"HOME={home}",
            "PATH=/usr/bin:/bin:/usr/sbin:/opt/homebrew/bin:" + home + "/.npm-global/bin",
            *claude_cmd,
        ]
    # launchd 下 claude 直接子进程会挂起（mach 等待）；经本机 ssh 回环创建
    # sshd 会话（正常用户环境）执行，桥进程仅作入口。
    if os.environ.get("CCC_CHAT_BRIDGE_SSH_LOOP", "").strip().lower() in ("1", "true", "yes", "on"):
        remote_cmd = (
            f"cd {shlex.quote(project_root)} && exec {shlex.quote(claude_bin)} "
            f"-p \"$(cat)\" --output-format stream-json --verbose"
        )
        proc = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "127.0.0.1", remote_cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert proc.stdin is not None
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except BrokenPipeError:
            pass
    else:
        proc = subprocess.Popen(
            claude_cmd,
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    assert proc.stdout is not None
    for raw in proc.stdout:
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")
        if etype == "assistant":
            msg = ev.get("message") or {}
            for block in msg.get("content") or []:
                kind = block.get("type")
                if kind == "text" and block.get("text"):
                    yield ("text", {"text": block["text"]})
                elif kind == "thinking" and block.get("thinking"):
                    yield ("thinking", {"thinking": block["thinking"]})
                elif kind == "tool_use" and block.get("name"):
                    yield ("tool_use", {"name": block["name"], "input": block.get("input", {})})
        elif etype == "result":
            yield ("done", {})
            break
        elif etype == "system" and ev.get("subtype") == "error":
            yield ("error", {"message": str(ev.get("message") or ev.get("error") or "claude error")})
            break
    proc.wait(timeout=10)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静默访问日志
        pass

    def _authed(self) -> bool:
        token = os.environ.get("CCC_CHAT_BRIDGE_TOKEN", "").strip()
        if not token:
            return True
        expect = f"Bearer {token}"
        return (self.headers.get("Authorization") or "") == expect

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return {}

    def do_GET(self):
        if not self._authed():
            self._json({"error": "unauthorized"}, 401)
            return
        path = self.path.rstrip("/").split("?")[0]
        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        if path == "/chat/history":
            project = (qs.get("project", [""])[0] or "").strip()
            thread_id = (qs.get("thread_id", [""])[0] or "").strip()
            after_raw = (qs.get("after", [""])[0] or "").strip()
            msgs = load_thread(project, thread_id)
            after = int(after_raw) if after_raw.isdigit() else 0
            self._json({"messages": msgs[after:], "seq": len(msgs)})
            return
        if path == "/claude/sessions":
            project = (qs.get("project", [""])[0] or "").strip()
            roots = _project_roots()
            cwd = roots.get(project) or roots.get("ccc")
            sessions: list[dict[str, Any]] = []
            if cwd:
                d = _claude_projects_dir() / _cwd_encode(cwd)
                try:
                    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
                    for f in files[:30]:
                        msgs = _parse_claude_jsonl(f)
                        title = ""
                        for m in msgs:
                            if m["role"] == "user":
                                title = m["content"].strip().splitlines()[0][:40]
                                if title.startswith(("Human:", "Assistant:")):
                                    title = title.split(":", 1)[1].strip()[:40]
                                break
                        try:
                            updated = int(f.stat().st_mtime)
                        except OSError:
                            updated = 0
                        sessions.append(
                            {"file": f.name, "title": title or "Claude 会话", "updated_at": updated, "count": len(msgs)}
                        )
                except OSError:
                    pass
            self._json({"sessions": sessions})
            return
        if path == "/claude/messages":
            project = (qs.get("project", [""])[0] or "").strip()
            file = (qs.get("file", [""])[0] or "").strip()
            roots = _project_roots()
            cwd = roots.get(project) or roots.get("ccc")
            msgs: list[dict[str, str]] = []
            if cwd and file and "/" not in file and ".." not in file:
                p = _claude_projects_dir() / _cwd_encode(cwd) / file
                msgs = _parse_claude_jsonl(p)
            self._json({"messages": msgs})
            return
        if path.startswith("/projects/") and path.endswith("/threads"):
            project = unquote(path[len("/projects/") : -len("/threads")])
            self._json({"threads": list_threads(project)})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authed():
            self._json({"error": "unauthorized"}, 401)
            return
        path = self.path.rstrip("/").split("?")[0]
        if path != "/chat":
            self._json({"error": "not found"}, 404)
            return
        body = self._read_body()
        message = str(body.get("message") or "").strip()
        thread_id = str(body.get("thread_id") or "").strip()
        project = str(body.get("project") or "").strip()
        claude_session = str(body.get("claude_session") or "").strip()
        if not message or not project:
            self._json({"error": "message and project required"}, 400)
            return
        roots = _project_roots()
        project_root = roots.get(project) or roots.get("ccc")
        if claude_session and "/" not in claude_session and ".." not in claude_session:
            history = _parse_claude_jsonl(
                _claude_projects_dir() / _cwd_encode(project_root) / claude_session
            )
        else:
            history = load_thread(project, thread_id)
        prompt = _build_prompt(project, history, message)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        def emit(event: str, data: dict) -> None:
            payload = json.dumps(data, ensure_ascii=False)
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
            self.wfile.flush()

        assistant_parts: list[str] = []
        try:
            for etype, payload in _run_claude_stream(prompt, project_root):
                if etype == "text":
                    assistant_parts.append(payload["text"])
                    emit("text", payload)
                elif etype == "thinking":
                    emit("thinking", payload)
                elif etype == "tool_use":
                    emit("tool_use", payload)
                elif etype == "done":
                    emit("done", {})
                elif etype == "error":
                    emit("error", payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            reply = "".join(assistant_parts).strip()
            if reply:
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                append_messages(
                    project,
                    thread_id,
                    [
                        {"role": "user", "message": message, "timestamp": now},
                        {"role": "assistant", "message": reply, "timestamp": now},
                    ],
                )

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()


def create_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("0.0.0.0", port), _Handler)


def serve_forever(port: int = DEFAULT_PORT) -> None:
    server = create_server(port)
    print(f"[chat-bridge] M1 对话桥启动于 :{port}", file=os.sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    serve_forever(int(os.environ.get("CCC_CHAT_BRIDGE_PORT", DEFAULT_PORT)))
