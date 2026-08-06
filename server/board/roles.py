"""席位与交叉验收规则（2026-08-06）。

产品意图：
- **Mac2017**：OpenCode = 开发；Claude Code = 验收（默认对）。
- **交叉验收**：执行体与验收必须互为 Claude Code ↔ OpenCode；同工具自验禁止。
- **Codex / Cursor**：取消验收资格（Codex 可出卡/裁决；Cursor 仅难度突击写码）。

卡头字段：``执行体`` / ``验收``。名称别名归一：``Claude`` → ``Claude Code``。
"""

from __future__ import annotations

# 可参与「开发 / 验收」交叉对的工具（归一后名）
CROSS_PAIR: dict[str, str] = {
    "OpenCode": "Claude Code",
    "Claude Code": "OpenCode",
}

# 明确禁止出现在卡头「验收」的席位
FORBIDDEN_ACCEPTORS: frozenset[str] = frozenset(
    {
        "Codex",
        "Cursor",
        "Trae",
        "人工",
    }
)

# 名称别名 → 规范名
_ALIASES: dict[str, str] = {
    "claude": "Claude Code",
    "claude code": "Claude Code",
    "claudecode": "Claude Code",
    "opencode": "OpenCode",
    "open code": "OpenCode",
    "codex": "Codex",
    "cursor": "Cursor",
    "trae": "Trae",
}

DEFAULT_EXECUTOR = "OpenCode"
DEFAULT_ACCEPTANCE = "Claude Code"  # OpenCode 开发 → Claude 验收


def normalize_tool(name: str) -> str:
    """归一工具名；空串保持空；未知名原样 strip。"""
    raw = (name or "").strip()
    if not raw:
        return ""
    # 去括号注释
    base = raw.split("（", 1)[0].split("(", 1)[0].strip()
    key = base.lower().replace("_", " ")
    return _ALIASES.get(key, base)


def expected_acceptance(executor: str) -> str | None:
    """给定执行体，返回唯一合法验收席；无法交叉则 None。"""
    exe = normalize_tool(executor)
    return CROSS_PAIR.get(exe)


def cross_acceptance_ok(executor: str, acceptance: str) -> bool:
    """执行体 / 验收是否构成合法交叉对。"""
    exe = normalize_tool(executor)
    acc = normalize_tool(acceptance)
    if not exe or not acc:
        return False
    return CROSS_PAIR.get(exe) == acc


def acceptance_issue(executor: str, acceptance: str) -> str | None:
    """校验卡头执行体×验收；合法返回 None，否则人话错误原因。"""
    exe = normalize_tool(executor)
    acc = normalize_tool(acceptance)
    if not acc:
        return "卡头缺「验收」字段（须 Claude Code 或 OpenCode，且与执行体交叉）"
    if acc in FORBIDDEN_ACCEPTORS:
        return (
            f"验收席禁止绑定 {acc!r}（Codex/Cursor 已取消验收资格；"
            f"须交叉：OpenCode 开发→Claude Code 验收，或 Claude Code 开发→OpenCode 验收）"
        )
    if not exe or exe == "未知":
        return None  # 执行体另检；此处不重复
    if exe not in CROSS_PAIR:
        return (
            f"执行体 {exe!r} 不在交叉验收对内（仅 OpenCode / Claude Code 可开发并交叉验收）"
        )
    expect = CROSS_PAIR[exe]
    if acc != expect:
        return (
            f"交叉验收不匹配：执行体 {exe} 须由 {expect} 验收，"
            f"当前验收={acc!r}（禁止自验 / Codex / Cursor）"
        )
    return None


def default_acceptance_for(executor: str) -> str:
    """出卡默认验收：按执行体交叉；未知执行体 → Claude Code。"""
    return expected_acceptance(executor) or DEFAULT_ACCEPTANCE
