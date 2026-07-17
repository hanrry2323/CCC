import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HOST = os.environ.get("CCC_CHAT_HOST", "0.0.0.0")
# Hub 对外端口：7777（用户习惯口）；Board API 内网默认 7775
PORT = int(os.environ.get("CCC_CHAT_PORT", "7777"))
# Hub 约定账密：用户名与密码均为 ccc（可用环境变量覆盖）
AUTH_USER = os.environ.get("CCC_CHAT_USER", "ccc")
AUTH_PASS = os.environ.get("CCC_CHAT_PASS", "ccc").strip()
BOARD_URL = os.environ.get("CCC_BOARD_URL", "http://127.0.0.1:7775")
BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()
PROXY_URL = os.environ.get("CCC_PROXY_URL", "http://127.0.0.1:4002/v1/chat/completions")

# Hub 对话超时（空闲 / 硬上限）。有工具调用时墙钟 180s 极易误杀。
# idle：距上次收到 Claude 输出的静默秒数；max：整轮硬上限。
CHAT_IDLE_TIMEOUT = int(os.environ.get("CCC_CHAT_IDLE_TIMEOUT", "600"))
CHAT_MAX_TIMEOUT = int(os.environ.get("CCC_CHAT_MAX_TIMEOUT", "1800"))
CHAT_IDLE_TIMEOUT = max(60, min(CHAT_IDLE_TIMEOUT, 3600))
CHAT_MAX_TIMEOUT = max(CHAT_IDLE_TIMEOUT, min(CHAT_MAX_TIMEOUT, 7200))
# 会话存储目录（测试可设 CCC_CHAT_DIR 指到临时目录，避免污染真实列表）
CHAT_DIR = Path(os.environ.get("CCC_CHAT_DIR", str(PROJECT_ROOT / ".ccc" / "chat")))
CHAT_DIR.mkdir(parents=True, exist_ok=True)
# LAN / localhost CORS regex（SPA 同机访问为 same-origin；跨端口/跨源时启用）
CORS_ORIGIN_REGEX = os.environ.get(
    "CCC_CHAT_CORS_ORIGIN_REGEX",
    r"https?://("
    r"localhost|127\.0\.0\.1|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$",
)

# 禁止历史泄漏 / 空口令；产品约定口令 "ccc" 明确允许
_FORBIDDEN_PASSWORDS = frozenset({
    "", "claude2026", "password", "admin", "123456", "changeme",
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
    """Hub 账密门禁：禁止空口令与历史泄漏默认；约定 ccc/ccc 可用。"""
    if AUTH_PASS.lower() in _FORBIDDEN_PASSWORDS:
        raise SystemExit(
            "CCC_CHAT_PASS is empty or a forbidden default "
            "(e.g. claude2026). Use the Hub password 'ccc', or set another non-forbidden value."
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
