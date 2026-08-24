"""server/tests 共享夹具：把仓库根加入 sys.path，使 `import server.*` 可用。"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

# 全局禁用测试时的网络探活，避免测试运行受本地 6100 端口状态影响
os.environ["EXECUTOR_PROBE_URL"] = ""

# R2 测试隔离（2026-08-24 直修）：机审台账与强拆台账一律落临时目录，
# 杜绝测试直写生产账本（曾实锤污染 ~/.ccc/data 强拆台账与 data/audit/ledger.jsonl）。
import tempfile as _tempfile

os.environ.setdefault(
    "CCC_AUDIT_LEDGER",
    os.path.join(_tempfile.gettempdir(), "ccc-test-audit-ledger.jsonl"),
)
os.environ.setdefault("DATA_DIR", _tempfile.mkdtemp(prefix="ccc-test-data-"))

# 提前注入鉴权凭据：`server.web.server` 在 import 时冻结用户名/密码哈希。
# 按字母序先收集的模块若提前 import server，会冻住空凭据 → http_api 全线 500。
# 此处只注入凭据，不设 CCC_WEB_AUTH_REQUIRED（各测试自行控制）。
os.environ.setdefault("CCC_WEB_USERNAME", "testuser")
os.environ.setdefault(
    "CCC_WEB_PASSWORD_HASH", hashlib.sha256(b"testpass").hexdigest()
)
os.environ.setdefault("CCC_WEB_TOKEN_TTL", "3600")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
