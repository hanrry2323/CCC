#!/usr/bin/env python3
"""_diff_check.py — 产线安全检查（FlowWeave 启发 · 薄能力）

只保留服务 CCC 意图链/门禁的部分：
- 敏感路径拦截（transfer_gate / DoD）
- 过大删除预警（供 Engine/Agent 提示，不挡产线默认路径）

**不**恢复 FlowWeave 画布 / 六适配器 / 完整 Electron 插件栈。
**不**做独立 Agent Protocol 文件桥（CCC 冲刷器 = sidecar outbox）。
"""

from __future__ import annotations

import re
from typing import Optional

# 敏感文件：不得出现在意图卡 scope / DoD 产品变更里
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:^|/)\.env(?:\.\w+)?$"),
    re.compile(r"(?:^|/)\.env\.local$"),
    re.compile(r"(?:^|/)credentials\.\w+$"),
    re.compile(r"(?:^|/)\.credentials"),
    re.compile(r"(?:^|/)\w+-secret\.\w+$"),
    re.compile(r"(?:^|/)\w+-secrets\.\w+$"),
    re.compile(r"(?:^|/)\w+-key\.\w+$", re.I),
    re.compile(r"(?:^|/)\.ssh/"),
    re.compile(r"(?:^|/)\.pypirc$"),
    re.compile(r"(?:^|/)\.npmrc$"),
    re.compile(r"(?:^|/)\.netrc$"),
    re.compile(r"(?:^|/)control\.json$"),
    re.compile(r"(?:^|/)\.ccc/.*control\.json"),
]


def is_sensitive_path(path: str) -> Optional[str]:
    """若路径敏感返回命中说明，否则 None。"""
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not p:
        return None
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(p):
            return f"sensitive:{pat.pattern}"
    # 文件名含明显密钥字样（保守：仅文件名段）
    name = p.rsplit("/", 1)[-1].lower()
    for token in ("password", "secret", "api_key", "apikey", "private_key"):
        if token in name:
            return f"sensitive:name:{token}"
    return None


def check_paths(paths: list[str]) -> list[dict]:
    """对路径列表做安全检查。返回 flag 列表。

    flag: {level: block|warn, rule, message, path}
    """
    flags: list[dict] = []
    seen: set[str] = set()
    for raw in paths or []:
        p = (raw or "").strip().replace("\\", "/")
        if not p or p in seen:
            continue
        seen.add(p)
        hit = is_sensitive_path(p)
        if hit:
            flags.append(
                {
                    "level": "block",
                    "rule": "sensitive_path",
                    "message": f"禁止把敏感路径写入意图卡/DoD：{p}",
                    "path": p,
                    "detail": hit,
                }
            )
    return flags


def any_blocked(flags: list[dict]) -> bool:
    return any(str(f.get("level") or "") == "block" for f in (flags or []))
