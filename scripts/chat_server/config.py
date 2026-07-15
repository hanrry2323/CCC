import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAT_DIR = PROJECT_ROOT / ".ccc" / "chat"
CHAT_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("CCC_CHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CCC_CHAT_PORT", "8084"))
AUTH_USER = os.environ.get("CCC_CHAT_USER", "ccc")
# F-SEC-01: 无默认弱口令；必须由 CCC_CHAT_PASS 显式提供
AUTH_PASS = os.environ.get("CCC_CHAT_PASS", "").strip()
BOARD_URL = os.environ.get("CCC_BOARD_URL", "http://127.0.0.1:7777")
BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()
PROXY_URL = os.environ.get("CCC_PROXY_URL", "http://127.0.0.1:4002/v1/chat/completions")

_WEAK_PASSWORDS = frozenset({
    "", "claude2026", "password", "ccc", "admin", "123456", "changeme",
})

# F-SEC-03: 辅助拦截（主防线=工具 allowlist + cwd jail）；覆盖常见变形，避免裸 \brm\b 误伤
DANGEROUS_PATTERN = re.compile(
    r"(?i)("
    r"\brm\s+(-[a-zA-Z0-9]*[rf][a-zA-Z0-9]*[rf]?[a-zA-Z0-9]*|-r\s+-f|-f\s+-r|--force)\b|"
    r"\brm\s+/"
    r"|/bin/rm\b"
    r"|\bsudo\b"
    r"|\bdd\s+if="
    r"|\bmkfs\b"
    r"|\bformat\s+[A-Za-z]:"  # format C: / format d:
    r"|>\s*/dev/"
    r"|\bchmod\s+777\b"
    r"|\b(curl|wget)\b[^\n]*\|\s*(ba)?sh\b"
    r"|\bshred\b"
    r")"
)

# F-SEC-03: Claude CLI 允许的工具（allowlist）；未列出的工具名应被拒绝
CLAUDE_TOOL_ALLOWLIST = frozenset({
    "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "LS", "Bash", "NotebookEdit", "TodoWrite", "WebFetch", "WebSearch",
})

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress",
    "testing", "verified", "released", "abnormal",
]

CLAUDE_BIN = shutil.which("claude") or ""
CLAUDE_ENV = {
    **os.environ,
    "PATH": f"{os.environ.get('PATH', '')}:{os.path.dirname(CLAUDE_BIN) if CLAUDE_BIN else ''}"
}


def validate_auth_config() -> None:
    """F-SEC-01: 强口令门禁；弱口令或未设置则拒绝启动。"""
    if AUTH_PASS.lower() in _WEAK_PASSWORDS or len(AUTH_PASS) < 12:
        raise SystemExit(
            "CCC_CHAT_PASS must be set to a strong password "
            "(>=12 chars, not a well-known default). Refusing to start."
        )


def require_claude_bin() -> str:
    """F-SEC-06: 仅 which；找不到则显式失败。"""
    if not CLAUDE_BIN:
        raise RuntimeError(
            "claude CLI not found in PATH; install Claude Code or set PATH"
        )
    return CLAUDE_BIN

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(PROJECT_ROOT)},
}
