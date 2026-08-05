# CCC 开发通道（谁改什么）

> **SSOT（2026-08-05 新栈重写）**：席位工具 + 壳 + Engine 谁干什么。  
> 对齐：[`CURSOR.md`](../../CURSOR.md) · `.cursor/rules/loop-engineer-consensus.mdc` · qx-map `ide/tool-roles.md` · R-15  
> **旧文（Hub / sidecar / OpenCode 主线 / 四方 Claude 串台）已作废**，勿再引用 2026-07-31 口径。

---

## 一句话（席位）

| 席位 | 谁干 | 说明 |
|------|------|------|
| **Claude Code**（2017） | 开发 / 维护 / 合入执行体 | Engine 按卡自动拉起；中继 6100；worktree `ccc-dev-ws-tNN` |
| **Codex** | 自研驱动者 + 验收席 | 出卡、把控、独立验收、冲突仲裁；不抢业务执行 |
| **OpenCode** | **已禁用** | 不接主线；仅历史 M1 打包类先例 |
| **Cursor / Trae** | 了解 / 讨论 / 排查 / 文档对齐 | 试运行可接手低风险工作；正式合入不经 Cursor（明确测试卡除外） |
| **CCC Desktop / HTTP 壳** | 任意设备壳 | HTTP 直连 2017 `:7788`；**不是**控制面、不改仓 |
| **Engine** | 薄驱动编排 | 读任务卡 + `executors.json` → 派发 / 收单；自己不写业务代码 |

**双轨（硬）**：**qb**（可挂 CCC 产线）与 **QuantHive**（独立轨道）完全独立；禁止合并、禁止互为别名、禁止用 CCC Engine「接管」QuantHive。

**禁止**：把 Desktop 人格限制写进开发工具身份（或反过来）；在 2017 生产副本手改；提旧拓扑（Hub :7777 / Board :7775 / sidecar / hub-tunnel）。

---

## 自研期标准链路

```text
Codex 出卡（docs/dispatch/TNN-*.md）→ push main
  → 2017 pull → Engine 派发 Claude Code
  → 独立 worktree + 分支 codex/tNN-*
  → 分步 commit+push → Codex 独立验收
  → 合入 main → 2017 pull + 三服务重启 → 关卡
```

业务期（自研成熟后）：老板用壳直聊大脑 Agent；业务任务仍走 Engine 派发 2017 执行体。

---

## 配置与模型

- 生产服务仅 2017：`:7788` + 中继 **6100 / 6102**
- M1 不跑 web-server / Engine；Desktop 只连 2017
- 执行体环境变量与命令以 `server/config/executors.json`（2017 实机）为准；仓内 `executors.example.json` 为模板

---

## 禁止混淆

1. 合入 CCC 主线 = **Claude Code 执行体 + Codex 验收**，不是 Cursor 日常代劳。  
2. Desktop / HTTP = 壳，≠ 平台开发 IDE。  
3. Engine 拉起的 Claude Code = 编排执行器会话，≠ 本机闲聊 Claude。  
4. Codex 知识/聊天 ≠ 开发席写码。  
5. OpenCode 禁用后，文档若仍写「dev=OpenCode」一律当过期。
