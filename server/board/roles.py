"""席位与验收规则（2026-08-08 定稿：M1 自验收 / 2017 机审固定交叉）。

产品意图（双轨，老板 2026-08-08 澄清）：
- **M1 端（出卡/合入验收）**：自验收——谁出卡谁验收。OpenCode 出卡 →
  OpenCode 可验收合入；Claude Code 同理。卡头「验收」字段即此席。
- **2017 端（产线机审）**：固定交叉——OpenCode 开发 → Claude Code 机审；
  Claude Code 开发 → OpenCode 机审。机审工具不读卡头「验收」字段
  （见 engine/main.py `_run_machine_audit_after_writeback`）。
- **Codex / Cursor**：取消验收资格（Codex 可出卡/裁决；Cursor 仅难度突击写码）。

两条硬规则（不可省）：
- **机审是独立步骤**：开发阶段禁止写 ``## 机审区``；验收席（即使与开发同工具）
  须按 Code Review 技能独立审查、写机审区、过 ready 门禁。
- **老板合入批准 = 人审最终 diff**：任何人/工具都不能绕过老板「合入批准」自行合入。

名称别名归一：``Claude`` → ``Claude Code``。
"""

from __future__ import annotations

# 可参与「开发 / 验收」的工具（归一后名）；自验收合法
ALLOWED_TOOLS: frozenset[str] = frozenset({"OpenCode", "Claude Code"})

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
DEFAULT_ACCEPTANCE = "OpenCode"  # 自验收：默认与执行体相同


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
    """自验收：给定执行体，返回同一工具作为验收席；不在白名单则 None。"""
    exe = normalize_tool(executor)
    return exe if exe in ALLOWED_TOOLS else None


def cross_acceptance_ok(executor: str, acceptance: str) -> bool:
    """自验收是否合法（执行体与验收同工具且在白名单内）。"""
    exe = normalize_tool(executor)
    acc = normalize_tool(acceptance)
    if exe not in ALLOWED_TOOLS or acc not in ALLOWED_TOOLS:
        return False
    return exe == acc


def acceptance_issue(executor: str, acceptance: str) -> str | None:
    """校验卡头执行体×验收（自验收）；合法返回 None，否则人话错误原因。"""
    exe = normalize_tool(executor)
    acc = normalize_tool(acceptance)
    if not acc:
        return "卡头缺「验收」字段（自验收：须与执行体同工具）"
    if acc in FORBIDDEN_ACCEPTORS:
        return (
            f"验收席禁止绑定 {acc!r}（Codex/Cursor 已取消验收资格；"
            f"验收须为 OpenCode 或 Claude Code 自验收）"
        )
    if not exe or exe == "未知":
        return None  # 执行体另检；此处不重复
    if exe not in ALLOWED_TOOLS:
        return f"执行体 {exe!r} 不可开发（仅 OpenCode / Claude Code 可开发并自验收）"
    if acc != exe:
        return (
            f"验收不匹配（自验收）：执行体 {exe} 须由 {exe} 验收，"
            f"当前验收={acc!r}"
        )
    return None


def default_acceptance_for(executor: str) -> str:
    """出卡默认验收：自验收（与执行体同工具）；未知执行体 → OpenCode。"""
    return expected_acceptance(executor) or DEFAULT_ACCEPTANCE
