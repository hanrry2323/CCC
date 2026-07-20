# CCC Desktop 产品架构 SSOT

> 版本：2026-07-19 · 与 Cursor/Codex/WorkBuddy 同级的完整产品形态  
> **边界基线**：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)（冲突时以边界契约为准）  
> 另见：[`transfer-gate.md`](transfer-gate.md) / [`executor-plugins.md`](executor-plugins.md) / [`flow-events.md`](flow-events.md)

---

## 一句话

**CCC Desktop** 是用户唯一产品面（对话 + 编排可视化）；**中心机**跑看板与编排引擎（远端开发）。  
差异化：**自由编排 + 多执行面**。方案 Agent **只产 epic**；中间只交信息流。

---

## 对话面 vs 编排面（部署）

| | 对话面 | 编排面 |
|--|--------|--------|
| 现网 | **M1** | **Mac2017** |
| 进程 | Desktop + Sidecar `:7788` + loop-code | Hub `:7777` + Board `:7775` + Engine |
| 产出 | 意图、定稿、`ccc-transfer`、epic | work 扇出、写码、验收、归档 |
| 权威数据 | 本机会话 `Application Support/CCCDesktop` | 业务仓 `.ccc/board` |

```text
Desktop (SwiftUI)  [M1]
  左：项目卡（一项目一对话）+ 看板/运维
  中：方案 Agent（本机 loop-code）→ 定稿 → 转任务
  右：编排流程（本机 boundEpicId 投影 2017 状态）
        │
        ├─ localhost:7788  → 对话热路径（不经 Hub）
        └─ 信息流 → Hub:7777 → Board / Engine（远端开发）
```

网页 Hub：**运维/兼容**，不是主聊天入口。

会话契约：[`project-as-conversation.md`](project-as-conversation.md)（`{projectId}::main`）。

---

## 两 Agent 边界

| | 方案 Agent（对话面） | 编排 Engine（编排面） |
|--|---------------------|----------------------|
| 界面 | Desktop 中栏 | 后台；右栏可视化 |
| 运行时 | **本机** loop-code | 中心机扇出后按卡选执行器 |
| 产出 | **仅**待办大卡 (epic) | work + 远端执行 + 验收 |
| 门禁 | 聊透才能转任务 | 消费合格 epic |

方案 Agent **不**扇出、**不**当执行 agent、**不**以 Hub `/api/chat` 为常态。  
Engine **不**承担主对话。

---

## 三栏 UI（+ 极左活动栏）

| 区 | 作用 |
|----|------|
| **左** | 项目卡（进入该项目唯一对话）+ 重置对话 / 看板 / 运维 |
| **中** | 方案对话；转任务为次级 CTA |
| **右** | 本机 `boundEpicId` 绑定的 epic→works **状态图**（信息流回程） |

右栏 UX：[`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md)。  
连接：[`desktop-connection.md`](desktop-connection.md)。

---

## 对照 OpenCode（会话完善度）

对照对象是 **OpenCode Desktop 的 Agent 会话体验**，不是嵌入 OpenCode 进程。

| 对齐 | CCC 落点 |
|------|----------|
| 按 sessionID 绑 UI | `WindowChatState.threadId` + `threadMessages[tid]` |
| 流式 / 停 / resume | Sidecar `:7788` + `claude_session_id` |
| Fork / Archive / Import-Export | `LocalSessionStore` + `_archive` 墓碑 |
| Model / discuss·engineer | 请求级 `model` + `preferredToolMode` |
| Context / compact | 本会话 token + `/api/session/compact` |
| 本会话用量 vs 上游 | 中栏 tok = sidecar cost；顶栏历史「中转站」统计在 router 退役后可能为空 |

计分 SSOT：[`desktop-opencode-parity.md`](desktop-opencode-parity.md)。  
**明确不做**：嵌 OpenCode、MCP/Provider 大盘、内嵌终端、文件树、云 Share。

---

## 数据实体

| 实体 | 权威落点 | 说明 |
|------|----------|------|
| Thread / Message | **M1 本机**（Hub 可选镜像） | 对话面 |
| Epic / Work | **2017 业务仓看板** | 编排面 |
| Flow 事件 | 2017 `flow-events` → Desktop SSE | 信息流回程 |

---

## 与现有代码关系

- 边界契约：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)
- Board：[`references/board-task-schema.md`](../../references/board-task-schema.md)
- Desktop：[`desktop/`](../../desktop/)
- GO-LIVE：[`../ops/GO-LIVE-DESKTOP.md`](../ops/GO-LIVE-DESKTOP.md)
