# CCC 开发通道（谁改什么）

> **SSOT（2026-08-06）**：席位工具 + 壳 + Engine 谁干什么。  
> 对齐：[`CURSOR.md`](../../CURSOR.md) · `.cursor/rules/loop-engineer-consensus.mdc` · qx-map `ide/tool-roles.md` · R-15  
> **旧文（Hub / sidecar /「OpenCode 禁用」误判 / 四方 Claude 串台）已作废**。

---

## 一句话（席位）

| 席位 | 谁干 | 说明 |
|------|------|------|
| **Claude Code** | 可后台 CLI 执行体（W2 点名） | Engine 拉起；中继 **6100 flash**；worktree |
| **OpenCode** | 可后台 CLI 执行体（日常默认） | Engine 拉起；中继 **6102 code**；与 Claude Code 并列，卡头绑定优先 |
| **Cursor** | **难度开发突击手**（W7） | 硬骨头写码 / 复杂排查修复 / 点名硬任务；不抢日常队列；终验归 Codex |
| **Codex** | 自研驱动者 + 验收席 | 出卡、把控、独立验收、冲突仲裁；不抢业务执行 |
| **M1 IDE** | 开发智能中枢 | 打开 CCC 仓 + 已注册能力即可开发（主路径） |
| **Trae** | 停用（历史） | 角色已移交 |
| **HTTP 看板/运维** | 人机实时面 | `:7788` 看板五态 + 执行中 dirty 数；主看路径 |
| **Desktop** | 壳（**暂缓**） | 代码保留；不优先自研；功能以 HTTP 为准 |
| **Engine** | 薄驱动编排 | 读任务卡 + `executors.json` → 派发 / 收单 |

**双轨（硬）**：**qb**（可挂 CCC 产线）与 **QuantHive**（独立轨道）完全独立。

**禁止**：把 Desktop 人格限制写进开发工具身份；在 2017 生产副本手改；提旧拓扑（Hub :7777 / Board :7775 / sidecar）。

---

## 双模式（M1 打开仓 vs Engine 拉起）

SSOT 正文见根目录 [`CLAUDE.md`](../../CLAUDE.md)「开仓作战卡片」。摘要：

| 模式 | 触发 | 做什么 | 禁止 |
|------|------|--------|------|
| **开发中枢** | 人在 M1 打开 `/Users/apple/program/CCC`（Claude Code / OpenCode） | 聊意图 → 出卡 push；**老板只看板/中继/Δ** | 自写验收区、自置已关闭、跨仓、把 pull/重启甩给老板 |
| **产线执行体** | 2017 Engine `-p` | 白名单改动 → `codex/<id>-*` 分支 → 卡头「已回写」 | 重出卡、改验收区、置已关闭、直推 main、手改 2017 |

工作区铁律：cwd 必须是 CCC 写源；发现 `qx-map` 等其它仓须当面点破。

**自动链（老板不管）**：push → 2017 `CCC_AUTO_PULL`（Engine/看板扫描前对齐）→ 派发 → 已回写。大方案切片见 [`CLAUDE.md`](../../CLAUDE.md)；禁止静默批量拆卡，切片表在对话里点头即可。

---

## 自研期标准链路

```text
（可选）M1 IDE 聊清意图并出卡 → push main
  或 Codex 出卡（docs/dispatch/*.md）→ push main
  → 2017 pull → Engine 按卡头绑定派发（Claude Code 或 OpenCode）
  → 独立 worktree + 分支 codex/<id>-*
  → 分步 commit+push → 卡头「已回写」
  → 验收席独立取证 → 「已关闭」+ 合入 main → 2017 pull + 必要时重启
```

业务期（自研成熟后）：老板用壳直聊大脑 Agent；业务任务仍走 Engine 派发。

---

## 配置与模型

- 生产服务仅 2017：`:7788` + 中继 **6100 / 6102**
- M1 不跑 web-server / Engine；看进度用 HTTP 连 2017
- 执行体以 `server/config/executors.json`（2017 实机）为准；仓内 `executors.example.json` 为双 CLI 模板

---

## 禁止混淆

1. 日常合入主线 = **注册表 CLI 执行体（默认 OpenCode）+ Codex 验收**；Cursor 专打难度突击，不默认代劳全部开发。  
2. HTTP 看板 = 人看流程的主面；Desktop ≠ 必经控制面。  
3. Engine 拉起的会话 ≠ 本机闲聊。  
4. OpenCode **可用**；与 Claude Code 差别主要在模型档（code vs flash），不是「禁用」。
5. Cursor = **难度开发突击手**（qx-map 决策 `Cursor难度开发突击手定位-2026-08-06.md`）。