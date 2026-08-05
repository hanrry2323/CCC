"""server/tests 共享夹具：把仓库根加入 sys.path，使 `import server.*` 可用。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 全局禁用测试时的网络探活，避免测试运行受本地 6100 端口状态影响
os.environ["EXECUTOR_PROBE_URL"] = ""

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
