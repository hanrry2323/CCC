import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHAT_DIR = PROJECT_ROOT / ".ccc" / "chat"
CHAT_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.environ.get("CCC_CHAT_HOST", "0.0.0.0")
PORT = int(os.environ.get("CCC_CHAT_PORT", "8084"))
AUTH_USER = os.environ.get("CCC_CHAT_USER", "ccc")
AUTH_PASS = os.environ.get("CCC_CHAT_PASS", "claude2026")
BOARD_URL = os.environ.get("CCC_BOARD_URL", "http://127.0.0.1:7777")
BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()
PROXY_URL = os.environ.get("CCC_PROXY_URL", "http://127.0.0.1:4002/v1/chat/completions")

DANGEROUS_PATTERN = re.compile(
    r"(?i)\b(rm\s+-rf|rm\s+/|sudo\b|dd\s+if=|format\b|mkfs\b|>\s*/dev/)"
)

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress",
    "testing", "verified", "released", "abnormal",
]

CLAUDE_BIN = shutil.which("claude") or "/Users/apple/.local/bin/claude"
CLAUDE_ENV = {
    **os.environ,
    "PATH": f"{os.environ.get('PATH', '')}:{os.path.dirname(CLAUDE_BIN)}"
}

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(PROJECT_ROOT)},
}
