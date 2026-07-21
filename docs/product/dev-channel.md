# CCC 开发通道（谁改什么）

> **SSOT**：平台怎么改、对话用什么模型、个人 Claude Code 扮演什么。  
> 对齐：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) · R-15（[`../../references/red-lines.md`](../../references/red-lines.md)）  
> 日期：2026-07-21

---

## 一句话

| 面 | 谁干 | 说明 |
|----|------|------|
| **CCC 平台代码**（本仓） | **Cursor** | R-15：禁止 Engine 自消费 CCC orch；brief 执行者也是 Cursor |
| **业务仓编排** | Mac2017 Engine | product/reviewer → Claude CLI→MiniMax；dev → OpenCode→讯飞 |
| **Desktop 对话** | M1 sidecar → loop-code | **默认 MiniMax**；M1 上**唯一** Claude 形态产品 |
| **个人 Claude Code** | **M1 已退役**（CLI + `~/.claude` 配置家） | 不劫持为 CCC 开发通道；见 [`loop-code-ownership-cut.md`](loop-code-ownership-cut.md) |

**配置家**：sidecar `CLAUDE_CONFIG_DIR=~/.ccc/loop-code`（Desktop 独享）。  
**CLI**：M1 无 PATH `claude`；对话只认 `vendor/loop-code`。  
**Engine**：2017 `CLAUDE_CONFIG_DIR=~/.ccc/engine-claude`；仍用 x86 原版 Claude CLI（不换 loop-code）。  
一次收口：[`loop-code-ownership-cut-closeout-brief.md`](loop-code-ownership-cut-closeout-brief.md)。
---

## Desktop 模型

- **现在**：sidecar plist 固定 MiniMax（`~/.ccc/minimax-api-key`）。  
- **Desktop 快选（Phase17）**：App 内 Composer/Settings 选逻辑名（默认 **MiniMax-M3** / `flash`），按请求传 sidecar；与个人 Claude Code / `~/.zshenv` 无关。  
- ~~118.ink / ops4.8~~：成本暂停，不作默认；恢复须显式 env + 重装 sidecar（见 [`../executors/loop-code.md`](../executors/loop-code.md)）。

---

## 禁止混淆

1. 改 CCC 平台 ≠ 开 Claude Code 会话改本仓。  
2. Desktop 对话模型 ≠ 个人 Claude Code 的 `ANTHROPIC_*`。  
3. Engine 的 Claude CLI（扇出/审查）≠ 「用 Claude Code 开发 CCC」。
