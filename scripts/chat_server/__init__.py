"""chat_server — CCC Hub 服务端包。

v0.51.0 P2-3: 统一 sys.path 注入到 scripts/ 目录，避免 config.py / routers/* 各自重复。
注入幂等：多次 import 不会污染 sys.path。
"""

from __future__ import annotations

import sys
from pathlib import Path

# chat_server/ 在 scripts/chat_server/，scripts 目录在 parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
