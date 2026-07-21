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
| **Desktop 对话** | M1 sidecar → loop-code | **默认 MiniMax**；与个人 Claude Code 无关 |
| **个人 Claude Code** | 可选 / 暂不用 | **原版**（Anthropic 登录态）；不劫持为 CCC 开发通道 |

---

## Desktop 模型

- **现在**：sidecar plist 固定 MiniMax（`~/.ccc/minimax-api-key`）。  
- **后续**：在 Desktop **应用内**做大模型快速选择（切换上游/模型）；不靠改 `~/.zshenv` / 个人 Claude settings。  
- ~~118.ink / ops4.8~~：成本暂停，不作默认；恢复须显式 env + 重装 sidecar（见 [`../executors/loop-code.md`](../executors/loop-code.md)）。

---

## 禁止混淆

1. 改 CCC 平台 ≠ 开 Claude Code 会话改本仓。  
2. Desktop 对话模型 ≠ 个人 Claude Code 的 `ANTHROPIC_*`。  
3. Engine 的 Claude CLI（扇出/审查）≠ 「用 Claude Code 开发 CCC」。
