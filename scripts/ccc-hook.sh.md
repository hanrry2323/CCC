# `ccc-hook.sh` — Claude Code pre-tool hook

> 作为 Claude Code 的 `PreToolUse` hook，区分源码改动 vs 元数据改动，便于自动 permission-mode 决策。

## 用途

Claude Code 调用 Bash/Write/Edit 工具时，本 hook 判断：
- 改的是源码 (`app/`/`frontend/`/`backend/`) → 全阻塞，需用户授权
- 改的是 CCC 元数据 (`.ccc/plans/`/`.ccc/phases/`/`.ccc/reports/`) → 全通过

## 用法

在 `<workspace>/.claude/settings.json` 配置：

```json
{
    "PreToolUse": [{
        "toolName": "Bash|Write|Edit",
        "command": "bash /Users/apple/program/CCC/scripts/ccc-hook.sh"
    }]
}
```

## Algorithm

```bash
if TOOL_INPUT matches .ccc/{plans,phases,reports,verdicts} → exit 0 (allow)
elif TOOL_INPUT matches .ccc/abnormal-reports/ OR .ccc/profile.md → exit 0 (allow)
elif TOOL_INPUT matches .ccc/*.json (e.g. .ccc/phases/<task>.phases.json) → exit 0 (allow)
else → exit 2 (deny, ask user)
```

## Exit codes

- 0: allow (continue without user prompt)
- 2: deny (ask user before proceeding)

## 关键约束

- 不修改 hook 自身（`scripts/ccc-hook.sh` 必须人工维护，不让 agent 改）
- 不在元数据改动时阻塞 (这是 v0.3.2 引入的核心)
- 默认 deny 源码改动（安全默认）

## 关联

- `references/execution-protocol.md` § Pre-tool hook 设计
- `references/red-lines.md` § 红线 (commit / planner 越界)
- `templates/.ccc-profile.md`
