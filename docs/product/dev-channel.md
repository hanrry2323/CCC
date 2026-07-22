# CCC 开发通道（谁改什么）

> **SSOT**：平台怎么改、对话用什么模型、编排执行器用什么。  
> 对齐：[`loop-engineer-authority.md`](loop-engineer-authority.md) · R-15  
> 日期：2026-07-22 · **平台开发工具只认 Cursor，不更换。**  
> **人格**：Cursor 平台助手 ≠ Desktop 对话 Agent（独立；见 [`loop-engineer-authority.md`](loop-engineer-authority.md)「双 Agent 人格独立」）。

---

## 一句话

| 面 | 谁干 | 说明 |
|----|------|------|
| **CCC 平台代码**（本仓） | **仅 Cursor** | 唯一开发工具；**完整 IDE 能力**；不换 Claude Code / Trae / Zed / 其它 IDE 改平台 |
| **业务仓编排** | Mac2017 Engine | product/reviewer → Claude CLI→MiniMax；dev → OpenCode→讯飞（**执行器**，不是平台开发工具） |
| **Desktop 对话** | M1 sidecar → loop-code | 默认 MiniMax；对话面 Plan（硬禁写业务仓）；**不是**改 CCC 的入口，**不是** Cursor |

**禁止**：用个人 Claude Code、Trae、Zed、VS Code 插件会话、网页 Hub 聊天改本仓。  
**配置家**：sidecar `CLAUDE_CONFIG_DIR=~/.ccc/loop-code`。Engine：`~/.ccc/engine-claude`（扇出用，非平台开发）。

---

## Desktop 模型

- sidecar 固定 MiniMax；App 内快选逻辑名（默认 `flash` / MiniMax-M3）。  
- 与个人 Claude / shell `ANTHROPIC_*` 无关。

---

## 禁止混淆

1. 改 CCC 平台 = **只在 Cursor** 改本仓（完整能力，不受 Desktop Plan 门禁）。  
2. Desktop 对话 ≠ 平台开发；Desktop Plan 纪律 **只约束** Desktop Agent。  
3. Engine 的 Claude CLI / OpenCode = **编排执行器**，≠ 「换个工具开发 CCC」。  
4. 产品名 Connect–Claude Code ≠ 用 Claude Code 当平台 IDE。  
5. **禁止**把 Desktop 人格/工具限制写进 Cursor 身份，或反过来。
