"""后半段 Claude CLI 网关环境自包含 + 配额预检（ccc-plan-053 阶段3）。

launchd 语境无 zshrc，网关三件（base/model/key）必须显式装配：
- key 只经 ``scripts/dsh-key.sh`` 单源解析（env → dsh-web plist → disabled engine plist），
  禁裸依赖 shell env；
- 派发（engine 门禁，仅 DSH 执行体命令）与审核（phase2 audit_card）前强制调
  ``scripts/dsh-key-check.sh``，429/拔 key 即拒单 + ledger 告警，防无声 429 循环。

密钥安全：本模块任何路径不得打印 key 值（2026-08-24 密钥泄漏教训）。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from server.board.audit_ledger import record_action

ANTHROPIC_BASE_URL = "https://opencode.ai/zen/go"
ANTHROPIC_MODEL = "deepseek-v4-flash"
_KEY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dsh-key.sh"
_CHECK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dsh-key-check.sh"
_PREFLIGHT_TTL_SECONDS = 300.0

_preflight_cache: dict[str, object] = {"ts": 0.0, "ok": True, "detail": "init"}


def resolve_key() -> str:
    """经 dsh-key.sh 单源解析网关 key（bash source；读不到返回空串）。"""
    try:
        proc = subprocess.run(
            ["bash", "-c", f'source "{_KEY_SCRIPT}" >/dev/null 2>&1; printf %s "${{OPENCODE_GO_API_KEY:-}}"'],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def cli_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Claude CLI 子进程环境：显式导出网关三件，launchd env -i 语境自包含。"""
    env = dict(base_env if base_env is not None else os.environ)
    env.setdefault("ANTHROPIC_BASE_URL", ANTHROPIC_BASE_URL)
    env.setdefault("ANTHROPIC_MODEL", ANTHROPIC_MODEL)
    for tier in ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        env.setdefault(tier, ANTHROPIC_MODEL)
    key = resolve_key()
    if key:
        env.setdefault("OPENCODE_GO_API_KEY", key)
        env.setdefault("ANTHROPIC_API_KEY", key)
    return env


def preflight_gateway(
    *,
    source: str = "engine",
    ttl_seconds: float = _PREFLIGHT_TTL_SECONDS,
    force: bool = False,
) -> tuple[bool, str]:
    """配额/密钥预检（TTL 缓存）。返回 (ok, detail)；False=拒单。

    - key 缺失（拔 key/单源失效）→ 拒单 + ledger `dsh_quota_alert`；
    - ``dsh-key-check.sh`` exit 2（429 周配额耗尽）→ 拒单（脚本自身已 ledger 告警）。
    """
    now = time.time()
    if (
        not force
        and ttl_seconds > 0
        and now - float(_preflight_cache["ts"]) < ttl_seconds
    ):
        return bool(_preflight_cache["ok"]), str(_preflight_cache["detail"])

    if not resolve_key():
        detail = "无 OPENCODE_GO_API_KEY（key 单源失效/拔 key），拒单"
        record_action("dsh_quota_alert", "gateway", source=source, detail=detail)
        ok = False
    else:
        try:
            proc = subprocess.run(
                ["bash", str(_CHECK_SCRIPT), "--quiet"],
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(_CHECK_SCRIPT.parents[1]),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            # 预检自身起不来属平台故障：放行不拒单（拒单语义只留给 429/拔 key）
            _preflight_cache.update(ts=now, ok=True, detail=f"preflight skipped: {exc}")
            return True, str(_preflight_cache["detail"])
        if proc.returncode == 2:
            ok = False
            detail = "dsh-key-check: 429 周配额耗尽，拒单（脚本已 ledger 告警）"
        elif proc.returncode != 0:
            ok = False
            detail = f"dsh-key-check 异常退出 rc={proc.returncode}，拒单"
        else:
            ok = True
            detail = "gateway preflight ok"
    _preflight_cache.update(ts=now, ok=ok, detail=detail)
    return ok, detail
