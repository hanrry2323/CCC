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
                "text": f"### [CCC {level}] {title}\n\n{message}\n\n---\n {ts}",
            },
        }
    # generic
    return {
        "title": title,
        "message": message,
        "level": level,
        "source": "patrol-v4",
        "timestamp": ts,
    }


def send_webhook(url: str, level: str, title: str, message: str) -> bool:
    """发送 webhook 通知。异常静默处理，返回 True=成功/False=失败/跳过。

    Args:
        url: webhook URL（空串或空白 = 跳过）
        level: "L1" / "L2" / "L3"
        title: 通知标题
        message: 通知正文

    Returns:
        True 表示发送成功（或 url 为空被跳过），False 表示 HTTP 错误
    """
    url = url.strip()
    if not url:
        return True  # 未配置 = 跳过，不算失败

    fmt = _guess_format(url)
    payload = _build_payload(level, title, message, fmt)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status == 200:
                _log.info("webhook ok (%s, %s)", level, title)
                return True
            _log.warning("webhook HTTP %d: %s", resp.status, body[:200])
            return False
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _log.warning("webhook failed (%s): %s", title, exc)
        return False
