"""看板 API 拉取（reaper 只读前置 · v2.0 P4.2）。

鉴权（token 内存态，绝不落盘）：优先 CCC_BOARD_TOKEN 环境变量；
无 env 时从 ~/.ccc/web-auth.txt 读凭证 POST /session 换 token。
401 自动换 token 重试一次（与 redispatch-card.sh 同策略）。

网络不可达/501/5xx → 返回 None（调用方视为「看板不可用」，整个看板维度标 WARN）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BOARD_URL = "http://192.168.3.116:7788"
DEFAULT_WEB_AUTH_FILE = "~/.ccc/web-auth.txt"
CARD_ENDPOINT = "/cards"


def _board_url() -> str:
    return os.environ.get("CCC_BOARD_URL", DEFAULT_BOARD_URL).rstrip("/")


def _web_auth_file() -> str:
    return os.environ.get("CCC_WEB_AUTH_FILE", DEFAULT_WEB_AUTH_FILE)

# 看板对齐现网：/cards 默认 page_size=50，需显式放大拿全量
CARD_PAGE_SIZE = 9999
_TIMEOUT = 15
_RENEWED = False


def _parse_auth_file(path: str | Path) -> tuple[str, str]:
    """解析 web-auth.txt → (username, password)；失败返回 ("", "")。"""
    p = Path(path).expanduser()
    user = ""
    password = ""
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "", ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, val = line.partition("：")
        if not sep:
            key, sep, val = line.partition(":")
        if not sep:
            continue
        val = val.strip()
        if key in ("账号", "用户", "账号名", "user", "username"):
            user = val
        elif key in ("口令", "密码", "password", "pass"):
            password = val
    if user and password:
        return user, password
    # 兜底：首行 `user:pass` 或单行口令（账号 ccc）
    first = ""
    try:
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                first = line
                break
    except OSError:
        return "", ""
    if ":" in first:
        u, _, pw = first.partition(":")
        return u.strip(), pw.strip()
    if first:
        return "ccc", first
    return "", ""


def _fetch_token() -> str:
    """POST /session 换 token；失败返回空串。token 只在内存。"""
    global _RENEWED
    if _RENEWED:
        return ""
    user, password = _parse_auth_file(_web_auth_file())
    if not user or not password:
        return ""
    body = json.dumps({"username": user, "password": password}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{_board_url()}/session",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return ""
    token = str(data.get("token") or "")
    if token:
        _RENEWED = True
    return token


def fetch_cards() -> list[dict[str, Any]] | None:
    """拉取看板全量卡；不可用返回 None。401/403 自动换 token 重试一次。"""
    token = os.environ.get("CCC_BOARD_TOKEN", "").strip()
    url = f"{_board_url()}{CARD_ENDPOINT}?page_size={CARD_PAGE_SIZE}"
    for attempt in range(2):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and attempt == 0:
                new_token = _fetch_token()
                if not new_token:
                    return None
                token = new_token
                continue
            if exc.code == 401 or exc.code == 403:
                return None
            return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None
        cards = data.get("cards") if isinstance(data, dict) else None
        if not isinstance(cards, list):
            return None
        return cards
    return None
