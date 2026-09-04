"""后段审核插件网关环境自包含 + 配额/通道预检（ccc-plan-053 阶段3 · P0-1 三态收紧）。

现役经 M1 3456 中转，模型绑定走配置；launchd 语境无 zshrc，网关三件（base/model/key）必须显式装配：
- key 只经 ``scripts/dsh-key.sh`` 单源解析（env → dsh-web plist → disabled engine plist），
  禁裸依赖 shell env；
- 派发（engine 门禁，仅 DSH 执行体命令）与审核（phase2 audit_card）前强制调
  ``scripts/dsh-key-check.sh``：三态协议（0=PASS / 2=QUOTA / 3=AUTH / 4=UPSTREAM /
  5=UNAVAILABLE / 6=NO_KEY / 7=ERROR），除 PASS 外一律拒单，绝不放行（P0-1）。

通道口径（2026-09-02 取证）：
- 配额/通道**探针默认目标 = 真实执行通道** local-litellm 127.0.0.1:3456
  （经 m1-tunnel → M1 SCNet；唯一事实源见 scripts/lib/dsh-probe.sh）。
- ``ANTHROPIC_BASE_URL`` 与 ``ANTHROPIC_MODEL`` 是 **Claude CLI 审核通道**，
  与 DSH 探针统一走 local-litellm（127.0.0.1:3456/v1/messages · Code），
  由 M1 中转隧道提供，2017 本机不另设第二条模型出口。

密钥安全：本模块任何路径不得打印 key 值（2026-08-24 密钥泄漏教训）。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from server.board.audit_ledger import record_action

# Claude CLI 审核通道（2026-09-03 对齐 2017 全通道真值：M1 中转站 local-litellm 3456 · Code）
ANTHROPIC_BASE_URL = "http://127.0.0.1:3456/v1/messages"
ANTHROPIC_MODEL = "Code"
_KEY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dsh-key.sh"
_CHECK_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dsh-key-check.sh"
_PREFLIGHT_TTL_SECONDS = 300.0

# scripts/dsh-key-check.sh 退出码协议（P0-1）：0=PASS 2=QUOTA 3=AUTH 4=UPSTREAM
# 5=UNAVAILABLE 6=NO_KEY 7=ERROR。除 0 外一律拒单（不静默放行）。
_CHECK_RC_OK = 0
_CHECK_RC_QUOTA = 2

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
    """Claude CLI 子进程环境：显式导出网关三件，launchd env -i 语境自包含。

    2026-09-03 修复：launchd 环境 PATH 极简（env -i），``claude``/``node`` 解析不到
    会直接 ``No such file or directory``（rc=127，phase2 机审断点）。这里兜底补
    npm 全局 bin + /usr/local/bin，确保 CLI 与其 node 运行时都能被拉起。
    """
    env = dict(base_env if base_env is not None else os.environ)
    # 统一覆盖调用方/launchd 残留的旧 zen/go 与 deepseek 模型，确保 2017 全通道走 M1 3456 Code。
    env["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE_URL
    env["ANTHROPIC_MODEL"] = ANTHROPIC_MODEL
    for tier in ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        env[tier] = ANTHROPIC_MODEL
    # PATH 兜底：launchd env -i 下默认无 npm bin；claude.exe 是 node 包装，node 也需可解析
    current_path = env.get("PATH") or ""
    npm_bin = os.path.expanduser("~/.npm-global/bin")
    required = [npm_bin, "/usr/local/bin", "/usr/bin", "/bin"]
    missing = [p for p in required if p not in current_path.split(":")]
    if missing:
        env["PATH"] = ":".join(missing + ([current_path] if current_path else []))
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
    """配额/通道预检（TTL 缓存）。返回 (ok, detail)；False=拒单。

    - key 缺失（拔 key/单源失效）→ 拒单 + ledger `dsh_quota_alert`；
    - ``dsh-key-check.sh`` exit 2（429 周配额耗尽）→ 拒单（脚本自身已 ledger 告警）；
    - 其余非 0 退出（AUTH/UPSTREAM/UNAVAILABLE/NO_KEY/ERROR）→ 一律拒单（P0-1 不静默放行）；
    - 预检进程自身起不来（OSError/超时）→ 拒单（探针不可用 = 明确错误态）。
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
            # P0-1：预检自身起不来 = 探针不可用，进入明确错误态拒单，不得静默放行
            _preflight_cache.update(ts=now, ok=False, detail=f"preflight unavailable: {exc}")
            return False, str(_preflight_cache["detail"])
        ok, detail = _map_check_rc(proc.returncode)
    _preflight_cache.update(ts=now, ok=ok, detail=detail)
    return ok, detail


def _map_check_rc(rc: int) -> tuple[bool, str]:
    """把 scripts/dsh-key-check.sh 退出码映射为 (ok, detail)；除 PASS 外一律拒单。"""
    if rc == _CHECK_RC_OK:
        return True, "gateway preflight ok"
    if rc == _CHECK_RC_QUOTA:
        return False, "dsh-key-check: 429 配额耗尽（QUOTA_EXHAUSTED），拒单（脚本已 ledger 告警）"
    labels = {
        3: "认证失败（AUTH_ERROR）",
        4: "上游错误（UPSTREAM_ERROR）",
        5: "探针不可用（PROBE_UNAVAILABLE）",
        6: "无 key（NO_KEY）",
        7: "未分类错误（ERROR）",
    }
    if rc in labels:
        return False, f"dsh-key-check: {labels[rc]}，拒单"
    return False, f"dsh-key-check 异常退出 rc={rc}，拒单"
