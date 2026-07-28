# CCC 开发通道（谁改什么）

> **SSOT**：四席工具 + Desktop + Engine 谁干什么。  
> 对齐：[`loop-engineer-authority.md`](loop-engineer-authority.md)「四席工具定位」· R-15  
> 日期：2026-07-28 · **合入权威只认 Cursor**  
> **人格**：Cursor 平台助手 ≠ Desktop 对话 Agent（独立）。

---

## 一句话（四席 + 产线）

| 席位 | 谁干 | 说明 |
|------|------|------|
| **Cursor** | 主力开发 + 合入 | **CCC** 合入；**QuantHive** 开发合入；热更 2017、生产密钥 |
| **Claude Code**（个人 CLI） | 运维双职 | ① 本机 `~/.ccc` / launchd / relay；② **QuantHive 日常维护**；**禁止**当合入 IDE |
| **OpenCode** | **仅** Engine 写码槽 | 2017 `--dir`（**qb** 等走 CCC）；**禁止**当 QuantHive / 个人主力 IDE |
| **Codex**（ChatGPT.app） | **知识管理 + 闲聊** | qb∥QuantHive **分域**；不改权威仓 |
| **CCC Desktop** | 产线控制面 | **qb** 等挂 CCC：意图/看板/下达；**不管** QuantHive 开发主路径 |
| **Engine Claude** | 编排执行器 | product / reviewer 等阶段；≠ 平台 IDE |

**双轨（硬）**：**qb**（CCC 自动化养大）与 **QuantHive**（Cursor+Claude 薄链）**完全独立**，同步对照；禁止合并、禁止互为别名。见 authority「双轨业务」。

**禁止**：Claude Code / Codex / 个人 OpenCode / Trae / Zed 当 CCC 合入工具。  
**禁止**：Desktop Agent 改 CCC 合入；个人 Claude 冒充 Desktop。  
**禁止**：用 CCC Hub/Engine「接管」QuantHive。  
**配置家**：sidecar `CLAUDE_CONFIG_DIR=~/.ccc/loop-code`；Engine：`~/.ccc/engine-claude`。

同模型（Relay `flash`）不改变分工。主机指令：`~/.claude/CLAUDE.md` · `~/.codex/AGENTS.md` · `~/.config/opencode/AGENTS.md`。

---

## 草稿旁路（非主职）

个人 Claude Code **主职是运维**。草稿仅金路径白名单缺陷：

1. Cursor 写 / 更新 `docs/dev-packets/NNN-*.md`  
2. 人转发个人 Claude Code  
3. 人交回分支 / diff  
4. Cursor 审测合入或打回  

模板：[`docs/dev-packets/_TEMPLATE.md`](../dev-packets/_TEMPLATE.md)。

---

## Desktop / 模型

- sidecar 默认 Relay **`flash`**（M1→2017 `:4000`）。  
- Codex 个人席走 `:4002` `/v1/responses`（垫片；非产线主路径）。  
- fail-open：`CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`。  
- 与个人 Claude shell `ANTHROPIC_*` 可共用中转站，**会话身份**与 Desktop 隔离。

---

## 禁止混淆

1. 合入 CCC = **只在 Cursor**。运维 ≠ 合入；草稿 ≠ 合入。  
2. Desktop = 控制面，≠ 平台开发，≠ 知识库主入口。  
3. Engine 的 Claude / OpenCode = **编排执行器**，≠ 个人 IDE。  
4. 产品名 Connect–Claude Code ≠ 用 Claude Code 当合入 IDE。  
5. Codex 知识/聊天 ≠ 开发席。  
6. **禁止**把 Desktop 人格限制写进 Cursor 身份，或反过来。
