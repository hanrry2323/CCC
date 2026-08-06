# CCC 开发通道（谁改什么）

> **SSOT（2026-08-06）**：席位工具 + 壳 + Engine 谁干什么。  
> 对齐：[`CURSOR.md`](../../CURSOR.md) · `.cursor/rules/loop-engineer-consensus.mdc` · qx-map `ide/tool-roles.md` · R-15  
> **旧文（Hub / sidecar /「OpenCode 禁用」误判 / 四方 Claude 串台）已作废**。

---

## 一句话（席位）

| 席位 | 谁干 | 说明 |
|------|------|------|
| **Claude Code** | 可后台 CLI 执行体 | Engine 拉起；中继 **6100 flash**；worktree |
| **OpenCode** | 可后台 CLI 执行体 | Engine 拉起；中继 **6102 code**；与 Claude Code 并列，卡头绑定优先 |
| **Codex** | 自研驱动者 + 验收席 | 出卡、把控、独立验收、冲突仲裁；不抢业务执行 |
| **M1 IDE** | 开发智能中枢 | 打开 CCC 仓 + 已注册能力即可开发（主路径） |
| **Cursor / Trae** | 了解 / 讨论 / 排查 / 文档对齐 | 正式合入以执行体+验收为准（明确测试卡除外） |
| **HTTP 看板/运维** | 人机实时面 | `:7788` 看板五态 + 执行中 dirty 数；主看路径 |
| **Desktop** | 壳（**暂缓**） | 代码保留；不优先自研；功能以 HTTP 为准 |
| **Engine** | 薄驱动编排 | 读任务卡 + `executors.json` → 派发 / 收单 |

**双轨（硬）**：**qb**（可挂 CCC 产线）与 **QuantHive**（独立轨道）完全独立。

**禁止**：把 Desktop 人格限制写进开发工具身份；在 2017 生产副本手改；提旧拓扑（Hub :7777 / Board :7775 / sidecar）。

---

## 自研期标准链路

```text
Codex 出卡（docs/dispatch/TNN-*.md）→ push main
  → 2017 pull → Engine 按卡头绑定派发（Claude Code 或 OpenCode）
  → 独立 worktree + 分支 codex/tNN-*
  → 分步 commit+push → Codex 独立验收
  → 合入 main → 2017 pull + 三服务重启 → 关卡
```

业务期（自研成熟后）：老板用壳直聊大脑 Agent；业务任务仍走 Engine 派发。

---

## 配置与模型

- 生产服务仅 2017：`:7788` + 中继 **6100 / 6102**
- M1 不跑 web-server / Engine；看进度用 HTTP 连 2017
- 执行体以 `server/config/executors.json`（2017 实机）为准；仓内 `executors.example.json` 为双 CLI 模板

---

## 禁止混淆

1. 合入主线 = **注册表 CLI 执行体 + Codex 验收**，不是 Cursor 日常代劳。  
2. HTTP 看板 = 人看流程的主面；Desktop ≠ 必经控制面。  
3. Engine 拉起的会话 ≠ 本机闲聊。  
4. OpenCode **可用**；与 Claude Code 差别主要在模型档（code vs flash），不是「禁用」。
