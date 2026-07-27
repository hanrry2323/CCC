# CCC 开发通道（谁改什么）

> **SSOT**：平台怎么改、对话用什么模型、编排执行器用什么。  
> 对齐：[`loop-engineer-authority.md`](loop-engineer-authority.md) · R-15  
> 日期：2026-07-27 · **合入权威只认 Cursor**；个人 Claude Code CLI 仅草稿工（生产前完善期）。  
> **人格**：Cursor 平台助手 ≠ Desktop 对话 Agent（独立；见 authority「双 Agent 人格独立」）。

---

## 一句话

| 面 | 谁干 | 说明 |
|----|------|------|
| **CCC 合入 / 权威 / 双机** | **仅 Cursor** | 上 main、改 authority、热更 2017、生产密钥；完整 IDE |
| **CCC 草稿量（白名单 packet）** | **个人 Claude Code CLI** + Relay `flash` | 按 [`docs/dev-packets/`](../dev-packets/README.md) 在 feature branch 改码；**禁止**当合入 IDE |
| **业务仓编排** | Mac2017 Engine | product/reviewer → Claude→Relay `flash`；dev → OpenCode→Relay `code`（**执行器**） |
| **Desktop 对话** | M1 sidecar → loop-code | 默认 Relay **`flash`**；**禁止**改 CCC 仓 |

**禁止**：把 Desktop Agent / Trae / Zed 当平台合入工具。  
**禁止**：个人 Claude Code 改权威、强推 main、动生产 plist/密钥。  
**配置家**：sidecar `CLAUDE_CONFIG_DIR=~/.ccc/loop-code`。Engine：`~/.ccc/engine-claude`。

战略：[`docs/briefs/2026-07-27-ccc-production-readiness.md`](../briefs/2026-07-27-ccc-production-readiness.md) —— **先生产级 CCC，再 CCC 做业务生产**。

---

## 草稿工节奏

1. Cursor 写 / 更新 `docs/dev-packets/NNN-*.md`  
2. 人转发个人 Claude Code（中转站）  
3. 人交回分支 / diff  
4. Cursor 审测合入或打回  

模板：[`docs/dev-packets/_TEMPLATE.md`](../dev-packets/_TEMPLATE.md)。

---

## Desktop 模型

- sidecar 默认走 CCC Relay **`flash`**（M1→2017 `:4000`）；App 内快选 `flash`/`Pro`/`code`。  
- fail-open：`CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`（禁硬编码厂商 URL）。  
- 与个人 Claude / shell `ANTHROPIC_*` 可共用中转站，但**会话身份**与 Desktop Agent 隔离。

---

## 禁止混淆

1. 合入 CCC = **只在 Cursor**（完整能力）。草稿 ≠ 合入。  
2. Desktop 对话 ≠ 平台开发；Desktop Plan 纪律 **只约束** Desktop Agent。  
3. Engine 的 Claude CLI / OpenCode = **编排执行器**，≠ 平台 IDE。  
4. 产品名 Connect–Claude Code ≠ 用 Claude Code 当合入 IDE。  
5. **禁止**把 Desktop 人格限制写进 Cursor 身份，或反过来。
