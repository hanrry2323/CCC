"""ccc — Webhook 通知发送器（v0.32+）

纯标准库，零外部依赖。支持通用 JSON / 飞书卡片 / 钉钉 Markdown 三种格式。

用法:
    from _webhook import send_webhook
    send_webhook(cfg.webhook_url, "L3", "Engine 重启失败", "需人工介入")
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

_log = logging.getLogger("webhook")

_TIMEOUT = 10  # HTTP 超时（秒）


def _guess_format(url: str) -> str:
    """根据 URL 推断 webhook 格式：generic / feishu / dingtalk"""
    u = url.lower()
    if "feishu" in u or "open.feishu.cn" in u:
        return "feishu"
    if "dingtalk" in u or "oapi.dingtalk.com" in u:
        return "dingtalk"
    return "generic"


def _build_payload(level: str, title: str, message: str, fmt: str) -> dict:
    """按格式构建请求体"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if fmt == "feishu":
        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"[CCC {level}] {title}",
                        "content": [
                            [{"tag": "text", "text": f"{message}\n时间: {ts}"}]
                        ],
                    }
                }
            },
        }
    if fmt == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"[CCC {level}] {title}",
                "text": f"### [CCC {level}] {title}\n\n{message}\n时间: {ts}",
            },
        }
    # generic
    return {
        "level": level,
        "title": title,
        "message": message,
        "timestamp": ts,
    }


def send_webhook(url: str, level: str, title: str, message: str) -> bool:
    """发送 webhook 通知。成功返回 True，失败返回 False。

    level 通常为 "L0"–"L4" 或 "INFO"/"WARN"/"ERROR"。
    """
    if not url:
        _log.debug("webhook URL 为空，跳过")
        return False
    fmt = _guess_format(url)
    payload = _build_payload(level, title, message, fmt)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            status = resp.status
            if status < 400:
                _log.info("webhook 发送成功 [%s] level=%s title=%s", status, level, title)
                return True
            _log.warning("webhook 返回 %s level=%s title=%s", status, level, title)
            return False
    except urllib.error.URLError as e:
        _log.error("webhook 发送失败: %s", e)
        return False
