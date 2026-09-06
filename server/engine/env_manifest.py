"""P3 环境声明式（env-manifest）：派发前拦截环境缺失，不执行中暴露（v2.0 宪章 P3）。

- 业务仓项目在 ``docs/projects/<prefix>/env-manifest.json`` 声明 python/pytest/ruff
  相对路径与测试入口；engine 挂载 worktree 后按 manifest 校验各路径（symlink 展开）
  真实存在，缺失 = 派发前拒绝（FAIL_FAST），ledger 告警 ``env_manifest_missing``。
- manifest 文件不存在 → 默认回退（``.venv/bin/pytest`` + ``.venv/bin/ruff``）+ WARN。
- 全部只读：不创建、不修复、不硬编码业务仓路径。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("ccc.engine.env_manifest")

MANIFEST_NAME = "env-manifest.json"
# 显式标记：env-manifest 派发前拒绝（ledger 告警 tag；失败分类凭此判 FAIL_FAST，不消耗重试语义）
ENV_MANIFEST_MISSING_MARKER = "env_manifest_missing"
DEFAULT_RUFF = ".venv/bin/ruff"
DEFAULT_PYTEST = ".venv/bin/pytest"


def manifest_path(ccc_repo_root: Path, prefix: str) -> Path:
    """``docs/projects/<prefix>/env-manifest.json`` 相对 CCC 仓根。"""
    return Path(ccc_repo_root) / "docs" / "projects" / prefix / MANIFEST_NAME


def load_manifest(path: Path) -> dict[str, Any] | None:
    """读 env-manifest.json；文件不存在/非法 → None（调用方走默认回退 + WARN）。"""
    try:
        if not Path(path).is_file():
            return None
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.warning("env-manifest 读取失败（走默认回退）: %s", path)
        return None


def _exists_after_symlink(path: Path) -> bool:
    """symlink 展开后的目标真实存在（``.venv`` 指向源环境；不 track 悬空链接）。"""
    try:
        return Path(path).expanduser().resolve().exists()
    except OSError:
        return False


def _bin_status(bin_rel: str | None, worktree: Path) -> tuple[Path | None, str]:
    """解析 manifest 里的相对 bin → (绝对路径, 状态)。"""
    if not bin_rel or not str(bin_rel).strip():
        return None, "unset"
    abs_path = Path(worktree) / str(bin_rel).strip()
    if not _exists_after_symlink(abs_path):
        return abs_path, "missing"
    return abs_path, "ok"


def validate_manifest(
    manifest: dict[str, Any] | None,
    worktree: Path,
    *,
    prefix: str,
) -> tuple[bool, list[str]]:
    """按 manifest 校验 worktree 内各 bin（symlink 展开）真实存在。

    manifest 不存在 → 默认回退（``.venv/bin/pytest`` + ``.venv/bin/ruff``），
    回退路径缺失仅告警（return ok=True + warn 列表 + 日志），不 FAIL_FAST。
    manifest 存在但任一声明路径缺失 → (False, 缺失清单) 派发前拒绝。
    """
    warns: list[str] = []
    if manifest is None:
        # 默认回退：只校验 pytest/ruff 的旧默认两件套；缺失落 WARN 不拦截。
        for rel in (DEFAULT_RUFF, DEFAULT_PYTEST):
            abs_path = Path(worktree) / rel
            if not _exists_after_symlink(abs_path):
                warns.append(f"{prefix} env-manifest 缺失，默认回退路径不存在: {abs_path}")
        if warns:
            logger.warning("; ".join(warns))
            return True, warns
        return True, []

    missing: list[str] = []
    for key in ("python_bin", "pytest_bin", "ruff_bin"):
        rel = manifest.get(key)
        if not rel or not str(rel).strip():
            # manifest 存在但字段未声明 → 不强制（保持向后兼容）；不落告警
            continue
        abs_path, status = _bin_status(rel, worktree)
        if status == "missing":
            missing.append(f"{prefix} {key}={rel} 不存在（symlink 展开后）: {abs_path}")
    if missing:
        logger.warning("env-manifest 校验失败（派发前拒绝）: %s", "; ".join(missing))
        return False, missing
    return True, []
