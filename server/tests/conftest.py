"""server/tests 共享夹具：把仓库根加入 sys.path，使 `import server.*` 可用。"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

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

# ccc082 测试隔离：全局机审注册表同样锚到临时目录，防测试经默认
# ~/.ccc/data/audit-inflight 读写生产防线面。
os.environ.setdefault(
    "CCC_AUDIT_REGISTRY_DIR",
    os.path.join(_tempfile.mkdtemp(prefix="ccc-test-audit-reg-")),
)

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


@pytest.fixture(autouse=True)
def _protect_real_dispatch_writes(monkeypatch: pytest.MonkeyPatch):
    """测试保险：真实 ``docs/dispatch`` 目录在 pytest 内只允许读。"""
    real_dispatch = (PROJECT_ROOT / "docs" / "dispatch").resolve()

    def _is_real(path: Path) -> bool:
        try:
            return path.resolve() == real_dispatch or real_dispatch in path.resolve().parents
        except OSError:
            return False

    def _guard(path: Path, operation: str) -> None:
        if _is_real(path):
            raise AssertionError(f"测试禁止写入真实 dispatch 目录: {operation} {path}")

    original_open = Path.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes
    original_unlink = Path.unlink
    original_mkdir = Path.mkdir
    original_replace = Path.replace
    original_rename = Path.rename

    def guarded_open(self, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            _guard(self, f"open({mode})")
        return original_open(self, mode, *args, **kwargs)

    def guarded_write_text(self, *args, **kwargs):
        _guard(self, "write_text")
        return original_write_text(self, *args, **kwargs)

    def guarded_write_bytes(self, *args, **kwargs):
        _guard(self, "write_bytes")
        return original_write_bytes(self, *args, **kwargs)

    def guarded_unlink(self, *args, **kwargs):
        _guard(self, "unlink")
        return original_unlink(self, *args, **kwargs)

    def guarded_mkdir(self, *args, **kwargs):
        _guard(self, "mkdir")
        return original_mkdir(self, *args, **kwargs)

    def guarded_replace(self, target, *args, **kwargs):
        _guard(self, "replace")
        _guard(Path(target), "replace-target")
        return original_replace(self, target, *args, **kwargs)

    def guarded_rename(self, target, *args, **kwargs):
        _guard(self, "rename")
        _guard(Path(target), "rename-target")
        return original_rename(self, target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    monkeypatch.setattr(Path, "write_bytes", guarded_write_bytes)
    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    monkeypatch.setattr(Path, "mkdir", guarded_mkdir)
    monkeypatch.setattr(Path, "replace", guarded_replace)
    monkeypatch.setattr(Path, "rename", guarded_rename)
    yield
