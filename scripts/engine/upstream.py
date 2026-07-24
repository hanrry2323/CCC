"""engine/upstream.py — 上游 relay/proxy 健康检测。

fix-planning-2026-07-24 ccc-engine.py 拆分布局：自包含模块，零内部依赖
（仅 stdlib + _utils）。原 ccc-engine.py:312-424 迁移到此处。

使用：
    from engine.upstream import get_relay_url, is_upstream_healthy
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger("ccc.engine.upstream")

_health_cache: dict[str, Any] = {}


def _utils_get_relay_url() -> str:
    from _utils import get_relay_url

    return get_relay_url()


def _utils_now_iso() -> str:
    from _utils import now_iso_utc

    return now_iso_utc()


def get_relay_url() -> str:
    """v0.51.0 P2-2: 委托 _utils.get_relay_url（SSOT）。"""
    return _utils_get_relay_url()


def is_upstream_healthy() -> bool:
    """检查 relay/proxy 是否可达，30s 缓存。

    v0.40.1: 默认 4xx 视为 proxy 在线（鉴权失败 ≠ 进程宕机）— 这是
    audit-2026-07-24 类别②假阳性来源。strict mode 仅 2xx 才算 healthy。
    CCC_UPSTREAM_STRICT=1 时 strict；CCC_UPSTREAM_STRICT=0 关闭 strict
    （保留旧行为兼容）。

    修复 stability-audit-2026-07-24 类别②：默认 strict=True，
    不再把任意 4xx 当 healthy，避免鉴权失败 / 路径错误被误判为"在线"。
    """
    now = time.time()
    cached = _health_cache.get("healthy")
    cached_at = _health_cache.get("checked_at", 0)
    if cached is not None and now - cached_at < 30:
        return cached

    relay = get_relay_url()
    messages_url = relay.rstrip("/") + "/v1/messages"
    _strict_raw = (os.environ.get("CCC_UPSTREAM_STRICT") or "").strip().lower()
    strict = _strict_raw not in ("0", "false", "no", "")
    status_code: int | None = None
    err_msg = ""
    try:
        import ssl
        import urllib.error
        import urllib.request

        def _probe(ctx: ssl.SSLContext | None = None) -> tuple[int | None, str]:
            req = urllib.request.Request(
                messages_url,
                method="GET",
                headers={"User-Agent": "ccc-engine-health"},
            )
            try:
                kwargs: dict = {"timeout": 5}
                if ctx is not None and messages_url.startswith("https://"):
                    kwargs["context"] = ctx
                resp = urllib.request.urlopen(req, **kwargs)
                code = getattr(resp, "status", None) or resp.getcode()
                return (int(code) if code is not None else None), ""
            except urllib.error.HTTPError as http_exc:
                return http_exc.code, str(http_exc.reason or http_exc)[:120]
            except urllib.error.URLError as url_exc:
                return None, str(url_exc.reason or url_exc)[:160]

        status_code, err_msg = _probe()
        if status_code is None and "CERTIFICATE" in (err_msg or "").upper():
            try:
                status_code, err_msg2 = _probe(ssl._create_unverified_context())
                if status_code is not None:
                    err_msg = f"tls_insecure_ok:{err_msg2 or err_msg}"[:160]
            except Exception as exc:
                err_msg = f"{err_msg}; insecure_retry={exc}"[:160]
    except Exception as exc:
        status_code = None
        err_msg = str(exc)[:120]

    if status_code is None:
        healthy = False
    elif strict:
        healthy = status_code == 200
    else:
        healthy = 200 <= status_code < 500

    _health_cache["healthy"] = healthy
    _health_cache["checked_at"] = now
    _health_cache["status_code"] = status_code
    _health_cache["error"] = err_msg
    prev = _health_cache.get("_last_logged")
    sig = (healthy, status_code)
    if prev != sig:
        _health_cache["_last_logged"] = sig
        try:
            probe_dir = Path.home() / ".ccc" / "stats"
            probe_dir.mkdir(parents=True, exist_ok=True)
            probe_path = probe_dir / "upstream-probe.jsonl"
            probe_record = {
                "ts": _utils_now_iso(),
                "healthy": healthy,
                "status": status_code,
                "error": err_msg or None,
                "relay": relay,
            }
            try:
                from _jsonl_rotate import append_jsonl

                append_jsonl(probe_path, probe_record)
            except ImportError:
                with probe_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(probe_record, ensure_ascii=False) + "\n")
        except Exception:
            pass
    if not healthy:
        _log.info(
            "[health] upstream 不可用 status=%s err=%s — 跳过 product_role（缓存 30s）",
            status_code,
            err_msg or "-",
        )
    elif status_code and status_code != 200:
        _log.info("[health] upstream proxy 可达 status=%s（视为 healthy）", status_code)
    return healthy
