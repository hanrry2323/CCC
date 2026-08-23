#!/usr/bin/env python3
"""DSH 密钥配额探针（S116-01 管理席 · P1-d 常态工具）。

对 opencode-go 密钥（settings.yaml 默认 provider）做最小 chat completion 探测，
判定配额状态，供管理席定时巡检 / 出卡前确认密钥可用，防静默 429（GoUsageLimitError）。

密钥单源：engine plist（com.ccc.engine.plist → EnvironmentVariables.OPENCODE_GO_API_KEY）。
探测端点与模型对齐 ~/.dsh/settings.yaml（provider opencode-go）。

用法：
  python3 scripts/ops/dsh_key_probe.py              # 探测 engine plist 密钥，人类可读结论
  python3 scripts/ops/dsh_key_probe.py --json       # JSON 输出（供巡检脚本解析）

退出码：0=配额正常 2=配额耗尽(GoUsageLimitError/429) 3=密钥无效/未配置 4=网络/服务异常
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 探测端点 / 模型：与 ~/.dsh/settings.yaml 的 opencode-go provider 对齐
PROBE_URL = "https://opencode.ai/zen/go/v1/chat/completions"
PROBE_MODEL = "minimax-m3"
ENGINE_PLIST = Path.home() / "Library/LaunchAgents/com.ccc.engine.plist"


def _read_key_from_plist() -> str | None:
    """从 engine plist 读 OPENCODE_GO_API_KEY（唯一权威源）。"""
    if not ENGINE_PLIST.is_file():
        return None
    try:
        import plistlib

        with ENGINE_PLIST.open("rb") as fh:
            d = plistlib.load(fh)
        return (d.get("EnvironmentVariables") or {}).get("OPENCODE_GO_API_KEY")
    except Exception:
        return None


def _mask(key: str) -> str:
    return key[:8] + "…" + key[-4:] if len(key) > 16 else "(空)"


def _ssl_context() -> object:
    """SSL 上下文：优先系统证书；python3 无系统 CA 时降级 unverified（探测端点固定）。"""
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


def probe(key: str, timeout: int = 30) -> dict:
    body = json.dumps(
        {"model": PROBE_MODEL, "messages": [{"role": "user", "content": "回复:ok"}], "max_tokens": 5}
    ).encode()
    req = urllib.request.Request(
        PROBE_URL, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                       "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            payload = json.loads(resp.read().decode())
        return {"status": "ok", "http": resp.status, "model": payload.get("model", PROBE_MODEL), "detail": ""}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()
        except Exception:
            pass
        is_quota = exc.code in (429,) or "GoUsageLimitError" in detail or "usage limit" in detail.lower()
        if is_quota:
            return {"status": "quota_exhausted", "http": exc.code, "detail": detail[:200]}
        if exc.code in (401, 403):
            return {"status": "invalid_key", "http": exc.code, "detail": detail[:200]}
        return {"status": "http_error", "http": exc.code, "detail": detail[:200]}
    except Exception as exc:
        return {"status": "network_error", "http": 0, "detail": str(exc)[:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH 密钥配额探针")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--key", metavar="KEY", help="显式密钥（默认读 engine plist）")
    args = ap.parse_args()

    key = args.key or os.environ.get("OPENCODE_GO_API_KEY") or _read_key_from_plist()
    if not key:
        print(json.dumps({"status": "no_key", "source": "engine plist"}) if args.json else
              "[ERROR] 未找到密钥（engine plist 无 OPENCODE_GO_API_KEY 或未显式 --key）", file=sys.stderr)
        return 3

    r = probe(key, timeout=args.timeout)
    r["key"] = _mask(key)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        labels = {
            "ok": f"✅ 配额正常（HTTP {r['http']}）",
            "quota_exhausted": f"⚠️ 配额耗尽（HTTP {r['http']} · {r['detail']}）",
            "invalid_key": f"❌ 密钥无效（HTTP {r['http']} · {r['detail']}）",
            "http_error": f"⚠️ HTTP 异常（HTTP {r['http']} · {r['detail']}）",
            "network_error": f"⚠️ 网络/服务异常（{r['detail']}）",
        }
        print(f"密钥 {r['key']}: {labels.get(r['status'], r['status'])}")
    return 0 if r["status"] == "ok" else (2 if r["status"] == "quota_exhausted" else 4)


if __name__ == "__main__":
    sys.exit(main())
