import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = PROJECT_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _claude_cli import ClaudeCliMissing, resolve_claude_cli  # noqa: E402

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
# 持续会话：live ClaudeSDKClient 空闲回收 / 并发上限
CHAT_SESSION_IDLE_TTL = int(os.environ.get("CCC_CHAT_SESSION_IDLE_TTL", "900"))
CHAT_SESSION_IDLE_TTL = max(60, min(CHAT_SESSION_IDLE_TTL, 7200))
CHAT_SESSION_MAX_LIVE = int(os.environ.get("CCC_CHAT_SESSION_MAX_LIVE", "4"))
CHAT_SESSION_MAX_LIVE = max(1, min(CHAT_SESSION_MAX_LIVE, 16))
# 会话存储目录（测试可设 CCC_CHAT_DIR 指到临时目录，避免污染真实列表）
CHAT_DIR = Path(os.environ.get("CCC_CHAT_DIR", str(PROJECT_ROOT / ".ccc" / "chat")))
CHAT_DIR.mkdir(parents=True, exist_ok=True)
# LAN / localhost CORS regex（SPA；原生 Desktop 不依赖 CORS）
# 默认仅本机，避免 RFC1918 + credentials 被同网段网页滥用；扩网段请设 CCC_CHAT_CORS_ORIGIN_REGEX
CORS_ORIGIN_REGEX = os.environ.get(
    "CCC_CHAT_CORS_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
# discuss = 对话面默认（只读探查，禁止写业务仓）；engineer = 显式解锁本机改文件
CLAUDE_TOOL_ALLOWLIST_DISCUSS = frozenset({
    "Read", "Glob", "Grep", "LS", "TodoWrite", "WebFetch", "WebSearch",
})
CLAUDE_TOOL_ALLOWLIST_ENGINEER = frozenset({
    "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "LS", "Bash", "NotebookEdit", "TodoWrite", "WebFetch", "WebSearch",
})
# 兼容旧引用：全量 = 工程师模式
CLAUDE_TOOL_ALLOWLIST = CLAUDE_TOOL_ALLOWLIST_ENGINEER

_ENGINEER_PHRASES = ("工程师模式", "直接改本机")


def resolve_tool_mode(
    explicit: str | None = None,
    *,
    user_text: str = "",
) -> str:
    """返回 discuss | engineer。缺省 discuss；显式或口令解锁 engineer。"""
    t = (explicit or "").strip().lower()
    if t in ("engineer", "discuss"):
        return t
    text = user_text or ""
    if any(p in text for p in _ENGINEER_PHRASES):
        return "engineer"
    return "discuss"


def tools_for_mode(mode: str) -> frozenset:
    if (mode or "").strip().lower() == "engineer":
        return CLAUDE_TOOL_ALLOWLIST_ENGINEER
    return CLAUDE_TOOL_ALLOWLIST_DISCUSS

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress",
    "testing", "verified", "released", "abnormal",
]

def _resolve_hub_claude_bin() -> str:
    try:
        return resolve_claude_cli(require=False) or ""
    except Exception:
        return ""


CLAUDE_BIN = _resolve_hub_claude_bin()
CLAUDE_ENV = {
    **os.environ,
    "PATH": f"{os.environ.get('PATH', '')}:{os.path.dirname(CLAUDE_BIN) if CLAUDE_BIN else ''}",
}


def validate_auth_config() -> None:
    """Hub 账密门禁：禁止空口令与历史泄漏默认；约定 ccc/ccc 可用。

    监听 0.0.0.0 且仍用默认口令时打印警告（产品允许 ccc:ccc，但全网暴露有风险）。
    """
    if AUTH_PASS.lower() in _FORBIDDEN_PASSWORDS:
        raise SystemExit(
            "CCC_CHAT_PASS is empty or a forbidden default "
            "(e.g. claude2026). Use the Hub password 'ccc', or set another non-forbidden value."
        )
    if HOST in ("0.0.0.0", "::") and AUTH_USER == "ccc" and AUTH_PASS == "ccc":
        print(
            "WARNING: Hub listens on all interfaces with default auth ccc:ccc. "
            "Prefer CCC_CHAT_HOST=127.0.0.1 or a stronger CCC_CHAT_PASS on shared LAN.",
            file=sys.stderr,
        )


def require_claude_bin() -> str:
    """F-SEC-06: 统一走 resolve_claude_cli（支持 CCC_CLAUDE_BIN / loop-code）。"""
    try:
        return resolve_claude_cli(require=True)
    except ClaudeCliMissing as exc:
        raise RuntimeError(str(exc)) from exc

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(PROJECT_ROOT)},
}
