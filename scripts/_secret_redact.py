"""敏感信息脱敏 — failures/logs API 出站前 scrub。"""

from __future__ import annotations

import re

# 常见密钥模式（保守：宁可多抹）
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]\s*\S+"), r"\1=***"),
    (re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"), "Bearer ***"),
    (re.compile(r"(?i)basic\s+[a-z0-9+/=]+"), "Basic ***"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "sk-***"),
    (re.compile(r"(?i)anthropic[_-]?api[_-]?key\s*[:=]\s*\S+"), "ANTHROPIC_API_KEY=***"),
]


def redact_secrets(text: str | None, *, max_len: int = 2048) -> str:
    if not text:
        return ""
    out = str(text)
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    if len(out) > max_len:
        out = out[:max_len] + "…"
    return out
