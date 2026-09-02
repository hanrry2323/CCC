#!/usr/bin/env python3
"""DSH 密钥配额探针（S116-01 管理席 · P0-1 三态收紧）。

对真实执行通道（默认 local-litellm 127.0.0.1:3456，见 scripts/lib/dsh-probe.sh）
做最小探测，判定通道状态，供管理席定时巡检 / 出卡前确认可用性。

退出码协议（与 scripts/dsh-key-check.sh 对齐）：
  0=PASS  2=QUOTA_EXHAUSTED(429)  3=AUTH_ERROR(401/403)
  4=UPSTREAM_ERROR(5xx)  5=PROBE_UNAVAILABLE(000/超时/DNS/TLS/空响应/解析失败/未分类)
  6=NO_KEY  7=ERROR

用法：
  python3 scripts/ops/dsh_key_probe.py              # 人类可读结论
  python3 scripts/ops/dsh_key_probe.py --json       # JSON 输出（供巡检脚本解析）

密钥安全：本模块任何路径不得打印 key 值（2026-08-24 密钥泄漏教训），只输出掩码。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_LIB_SH = _SCRIPTS / "lib" / "dsh-probe.sh"
_KEY_SH = _SCRIPTS / "dsh-key.sh"


def _bash_stdout(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (proc.stdout or "").strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _resolve_probe_url() -> str:
    """经 scripts/lib/dsh-probe.sh 单源解析（唯一事实源）；解析失败返回空 → 按不可用处理。"""
    return _bash_stdout(["bash", str(_LIB_SH), "print-url"])


def _resolve_probe_model() -> str:
    return _bash_stdout(["bash", str(_LIB_SH), "print-model"])


def resolve_key() -> str:
    """密钥单源：env → scripts/dsh-key.sh（与 dsh-key-check.sh 同源，禁读明文落盘）。"""
    if os.environ.get("OPENCODE_GO_API_KEY"):
        return os.environ["OPENCODE_GO_API_KEY"]
    return _bash_stdout(
        ["bash", "-c", f'source "{_KEY_SH}" >/dev/null 2>&1; printf %s "${{OPENCODE_GO_API_KEY:-}}"']
    )


def _mask(key: str) -> str:
    return key[:8] + "…" + key[-4:] if len(key) > 16 else "(空)"


def _ssl_context() -> object:
    """SSL 上下文：优先系统证书；python3 无系统 CA 时降级 unverified（仅 https 场景）。"""
    import ssl

    for cafile in ("/etc/ssl/cert.pem", "/System/Library/OpenSSL/cert.pem"):
        if Path(cafile).is_file():
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                continue
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def classify(code: int, detail: str, body: str = "") -> str:
    """按 HTTP 结果返回状态：ok/quota_exhausted/auth_error/upstream_error/unavailable/error。

    任何 000/空响应/解析失败/未知状态一律不得返回 ok（P0-1 红线）。
    """
    if code == 0:
        return "unavailable"
    if code == 429 or "GoUsageLimitError" in detail or "usage limit" in detail.lower():
        return "quota_exhausted"
    if code in (401, 403):
        return "auth_error"
    if 200 <= code <= 299:
        if not body.strip():
            return "unavailable"
        try:
            payload = json.loads(body)
        except Exception:
            return "unavailable"
        if not payload:
            return "unavailable"
        s = json.dumps(payload)
        if '"content"' in s or '"model"' in s or '"choices"' in s:
            return "ok"
        return "unavailable"
    if 500 <= code <= 599:
        return "upstream_error"
    return "error"


def probe(key: str, timeout: int = 30, url: str | None = None, model: str | None = None) -> dict:
    """最小探测；url/model 缺省经 dsh-probe.sh 单源解析。不打印 key。"""
    url = url or _resolve_probe_url()
    model = model or _resolve_probe_model()
    if not url or not model:
        return {"status": "unavailable", "http": 0, "model": model or "", "detail": "探针 URL/模型未解析（配置缺失）"}
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        status = classify(resp.status, "", raw)
        detail = "" if status == "ok" else "响应不符合协议"
        return {"status": status, "http": resp.status, "model": model, "detail": detail}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {"status": classify(exc.code, detail), "http": exc.code, "model": model, "detail": detail[:200]}
    except Exception as exc:  # 网络/DNS/超时/TLS/畸形响应 等一律不可用，绝不 PASS
        return {"status": "unavailable", "http": 0, "model": model, "detail": str(exc)[:200]}


EXIT_BY_STATUS = {
    "ok": 0,
    "quota_exhausted": 2,
    "auth_error": 3,
    "upstream_error": 4,
    "unavailable": 5,
    "no_key": 6,
    "error": 7,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH 密钥配额探针")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--key", metavar="KEY", help="显式密钥（默认 env → scripts/dsh-key.sh 单源）")
    args = ap.parse_args()

    key = args.key or resolve_key()
    if not key:
        print(
            json.dumps({"status": "no_key", "source": "dsh-key.sh"})
            if args.json
            else "[ERROR] 未找到密钥（OPENCODE_GO_API_KEY 未配置且 dsh-key.sh 解析为空）",
            file=sys.stderr,
        )
        return EXIT_BY_STATUS["no_key"]

    r = probe(key, timeout=args.timeout)
    r["key"] = _mask(key)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        labels = {
            "ok": f"✅ 通道正常（HTTP {r['http']}）",
            "quota_exhausted": f"⚠️ 配额耗尽（HTTP {r['http']} · {r['detail']}）",
            "auth_error": f"❌ 认证失败（HTTP {r['http']} · {r['detail']}）",
            "upstream_error": f"⚠️ 上游错误（HTTP {r['http']} · {r['detail']}）",
            "unavailable": f"⚠️ 探针不可用（HTTP {r['http']} · {r['detail']}）",
            "error": f"⚠️ 未分类错误（HTTP {r['http']} · {r['detail']}）",
            "no_key": "❌ 无密钥",
        }
        print(f"密钥 {r['key']}: {labels.get(r['status'], r['status'])}")
    return EXIT_BY_STATUS.get(r["status"], EXIT_BY_STATUS["error"])


if __name__ == "__main__":
    sys.exit(main())
